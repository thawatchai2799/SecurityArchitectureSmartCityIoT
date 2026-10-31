"""
drift.py
--------
Three standard concept-drift detectors, implemented from the original papers so that the replay
needs no extra dependency, used as alternative re-training triggers in chrono.py:

    ADWIN   Bifet & Gavalda, "Learning from time-changing data with adaptive windowing", SDM 2007.
            Adaptive window with an exponential histogram (M buckets per row); drift when the means
            of two sub-windows differ by more than the Hoeffding-type bound eps_cut at confidence
            delta. Label-free here: it watches a per-flow feature statistic.
    KSWIN   Raab, Heusinger & Schleif, "Reactive soft prototype computing for concept drift
            streams", Neurocomputing 2020. Two-sample Kolmogorov-Smirnov test between the most
            recent stat_size points and a random sample of the older part of a sliding window.
            Label-free here, on the same feature statistic.
    DDM     Gama, Medas, Castillo & Rodrigues, "Learning with drift detection", SBIA 2004.
            Tracks the error rate p_t and its standard deviation s_t of the deployed detector;
            drift when p_t + s_t > p_min + 3 s_min. Needs the true label of every flow, so it sits
            with the oracle policy on the label axis of the comparison.

The parameters are the defaults of the river library (ADWIN delta = 0.002; KSWIN alpha = 0.005,
window_size = 100, stat_size = 30; DDM warm-up 30, warning 2 s, drift 3 s) and the implementations
are checked against river in tests/test_drift.py.

All three expose the same tiny interface:
    update(x) -> bool     feed one value, return True when drift is signalled
    reset()               forget everything (called after every re-training)
"""
from __future__ import annotations
import math
import numpy as np


# --------------------------------------------------------------------------------------------- #
#  ADWIN
# --------------------------------------------------------------------------------------------- #
class ADWIN:
    """Adaptive windowing (ADWIN2 of Bifet & Gavalda 2007) with an exponential histogram."""

    def __init__(self, delta: float = 0.002, max_buckets: int = 5, min_window_length: int = 5,
                 grace_period: int = 10, clock: int = 32):
        self.delta, self.M = delta, max_buckets
        self.min_window_length, self.grace_period, self.clock = min_window_length, grace_period, clock
        self.reset()

    def reset(self):
        # rows of buckets; row r holds buckets of 2**r items: (total, variance) per bucket
        self.rows: list[list[tuple[float, float]]] = [[]]
        self.total, self.variance, self.width = 0.0, 0.0, 0
        self.n_seen = 0

    # -- bucket bookkeeping ------------------------------------------------------------------- #
    def _insert(self, x: float):
        self.rows[0].insert(0, (x, 0.0))                  # newest bucket at the front of row 0
        if self.width > 0:
            inc = (self.width / (self.width + 1.0)) * (x - self.total / self.width) ** 2
            self.variance += inc
        self.width += 1; self.total += x
        self._compress()

    def _compress(self):
        r = 0
        while r < len(self.rows):
            row = self.rows[r]
            if len(row) <= self.M:
                break
            # merge the two oldest buckets of this row into one bucket of the next row
            (t1, v1), (t2, v2) = row[-2], row[-1]
            n = float(2 ** r)
            u1, u2 = t1 / n, t2 / n
            merged = (t1 + t2, v1 + v2 + n * n * (u1 - u2) ** 2 / (n + n))
            del row[-2:]
            if r + 1 == len(self.rows):
                self.rows.append([])
            self.rows[r + 1].insert(0, merged)
            r += 1

    def _drop_oldest(self):
        r = len(self.rows) - 1
        while r >= 0 and not self.rows[r]:
            r -= 1
        t, v = self.rows[r].pop()
        n = 2 ** r
        self.width -= n; self.total -= t
        u = t / n
        if self.width > 0:
            self.variance -= v + n * self.width / (n + self.width) * (u - self.total / self.width) ** 2
            self.variance = max(self.variance, 0.0)
        else:
            self.variance = 0.0
        while len(self.rows) > 1 and not self.rows[-1]:
            self.rows.pop()

    # -- the test --------------------------------------------------------------------------------- #
    def update(self, x: float) -> bool:
        self.n_seen += 1
        self._insert(float(x))
        if self.n_seen % self.clock != 0 or self.width < self.grace_period:
            return False
        drift = False
        reduce = True
        while reduce:
            reduce = False
            n1 = 0.0; u1 = 0.0
            n0 = float(self.width); u0 = self.total
            # walk from the oldest bucket (largest row, last element) towards the newest
            for r in range(len(self.rows) - 1, -1, -1):
                row = self.rows[r]
                size = float(2 ** r)
                for j in range(len(row) - 1, -1, -1):
                    t, _ = row[j]
                    n0 -= size; u0 -= t; n1 += size; u1 += t
                    if n0 < self.min_window_length or n1 < self.min_window_length:
                        continue
                    if r == 0 and j == 0:               # never cut off the newest bucket
                        continue
                    m0, m1 = u0 / n0, u1 / n1
                    if self._cut(n0, n1, abs(m0 - m1)):
                        reduce = True; drift = True
                        self._drop_oldest()
                        break
                if reduce:
                    break
            if self.width < 2 * self.min_window_length:
                reduce = False
        return drift

    def _cut(self, n0: float, n1: float, diff: float) -> bool:
        n = float(self.width)
        var = self.variance / n if n > 0 else 0.0
        dd = math.log(2.0 * math.log(n) / self.delta) if n > 1 else 0.0
        m = 1.0 / (n0 - self.min_window_length + 1) + 1.0 / (n1 - self.min_window_length + 1)
        eps = math.sqrt(2.0 * m * var * dd) + 2.0 / 3.0 * dd * m
        return diff > eps

    @property
    def estimation(self) -> float:
        return self.total / self.width if self.width else 0.0


# --------------------------------------------------------------------------------------------- #
#  KSWIN
# --------------------------------------------------------------------------------------------- #
class KSWIN:
    """Kolmogorov-Smirnov windowing (Raab et al. 2020)."""

    def __init__(self, alpha: float = 0.005, window_size: int = 100, stat_size: int = 30, seed: int = 42):
        if not 0 < alpha < 1 or window_size <= stat_size:
            raise ValueError("need 0 < alpha < 1 and window_size > stat_size")
        self.alpha, self.window_size, self.stat_size = alpha, window_size, stat_size
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self):
        self.window: list[float] = []
        self.p_value = 1.0

    def update(self, x: float) -> bool:
        from scipy.stats import ks_2samp
        self.window.append(float(x))
        if len(self.window) <= self.window_size:
            return False
        self.window.pop(0)
        recent = np.asarray(self.window[-self.stat_size:])
        older = np.asarray(self.window[:-self.stat_size])
        sample = self.rng.choice(older, size=self.stat_size, replace=False)
        st, p = ks_2samp(sample, recent)
        self.p_value = float(p)
        if p <= self.alpha and st > 0.1:
            self.window = self.window[-self.stat_size:]
            return True
        return False


# --------------------------------------------------------------------------------------------- #
#  DDM
# --------------------------------------------------------------------------------------------- #
class DDM:
    """Drift detection method (Gama et al. 2004) on a 0/1 error stream."""

    def __init__(self, warm_start: int = 30, warning_threshold: float = 2.0, drift_threshold: float = 3.0):
        self.warm_start, self.w_thr, self.d_thr = warm_start, warning_threshold, drift_threshold
        self.reset()

    def reset(self):
        self.n = 0; self.p = 1.0; self.s = 0.0
        self.p_min = float("inf"); self.s_min = float("inf"); self.ps_min = float("inf")
        self.warning = False

    def update(self, error) -> bool:
        self.n += 1
        e = float(error)
        self.p += (e - self.p) / self.n
        self.s = math.sqrt(self.p * (1.0 - self.p) / self.n)
        if self.n < self.warm_start:
            return False
        if self.p + self.s <= self.ps_min:
            self.p_min, self.s_min, self.ps_min = self.p, self.s, self.p + self.s
        if self.p + self.s > self.p_min + self.d_thr * self.s_min:
            self.reset()
            return True
        self.warning = self.p + self.s > self.p_min + self.w_thr * self.s_min
        return False

    def update_batch(self, errors: np.ndarray) -> bool:
        """Feed a whole window of 0/1 errors; True if drift was signalled anywhere in it."""
        drift = False
        for e in errors:
            if self.update(e):
                drift = True
        return drift


def feature_statistic(Xs_window: np.ndarray, batch: int = 100) -> np.ndarray:
    """The label-free per-flow statistic fed to ADWIN and KSWIN: the mean absolute standardised
    feature value of each flow, averaged over consecutive mini-batches of `batch` flows (so that
    a 20,000-flow window becomes a stream of 200 points). The last partial batch is dropped."""
    s = np.abs(Xs_window).mean(axis=1)
    n = (len(s) // batch) * batch
    if n == 0:
        return s.mean(keepdims=True)
    return s[:n].reshape(-1, batch).mean(axis=1)
