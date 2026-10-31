"""
Checks sustain/drift.py against the river library (pip install river) on synthetic streams.
ADWIN and DDM are deterministic and must flag the same drifts within a few samples; KSWIN draws a
random sample and is compared on the number of drifts and their rough position.

    python3 -m pytest tests/test_drift.py -q      (or: python3 tests/test_drift.py)
"""
from __future__ import annotations
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sustain.drift import ADWIN, DDM, KSWIN, feature_statistic   # noqa: E402


def _stream(seed=0, n=3000, shift_at=1500, shift=1.0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, n)
    x[shift_at:] += shift
    return x


def _flags(det, x):
    return [i for i, v in enumerate(x) if det.update(v)]


def test_adwin_matches_river():
    river = __import__("river.drift", fromlist=["ADWIN"])
    for seed in range(5):
        x = _stream(seed)
        ours = _flags(ADWIN(delta=0.002), x)
        ref = river.ADWIN(delta=0.002); theirs = []
        for i, v in enumerate(x):
            ref.update(v)
            if ref.drift_detected:
                theirs.append(i)
        assert ours and theirs, (ours, theirs)
        assert abs(ours[0] - theirs[0]) <= 64, (ours[:3], theirs[:3])          # within two clock ticks
        assert ours[0] >= 1500 and theirs[0] >= 1500


def test_ddm_matches_river():
    river = __import__("river.drift.binary", fromlist=["DDM"])
    rng = np.random.default_rng(1)
    err = np.concatenate([rng.random(2000) < 0.05, rng.random(2000) < 0.40]).astype(int)
    ours = _flags(DDM(), err)
    ref = river.DDM(warm_start=30, warning_threshold=2.0, drift_threshold=3.0); theirs = []
    for i, v in enumerate(err):
        ref.update(bool(v))
        if ref.drift_detected:
            theirs.append(i)
    assert ours and theirs
    assert abs(ours[0] - theirs[0]) <= 2, (ours[:3], theirs[:3])


def test_kswin_statistically_matches_river():
    """KSWIN draws its reference sample at random, so two implementations with different random
    generators flag different streams; over 30 streams the false-alarm count before the shift and
    the detection delay after it must be of the same size."""
    river = __import__("river.drift", fromlist=["KSWIN"])
    fa_o = fa_t = 0; delay_o = []; delay_t = []
    for seed in range(30):
        x = _stream(seed, n=2000, shift_at=1000, shift=1.5)
        ours = _flags(KSWIN(alpha=0.005, window_size=100, stat_size=30, seed=seed), x)
        ref = river.KSWIN(alpha=0.005, window_size=100, stat_size=30, seed=seed); theirs = []
        for i, v in enumerate(x):
            ref.update(v)
            if ref.drift_detected:
                theirs.append(i)
        fa_o += sum(i < 1000 for i in ours); fa_t += sum(i < 1000 for i in theirs)
        d_o = [i for i in ours if i >= 1000]; d_t = [i for i in theirs if i >= 1000]
        assert d_o and d_t, (seed, ours, theirs)
        delay_o.append(d_o[0] - 1000); delay_t.append(d_t[0] - 1000)
    assert abs(np.mean(delay_o) - np.mean(delay_t)) <= 30, (np.mean(delay_o), np.mean(delay_t))
    assert abs(fa_o - fa_t) <= max(5, 0.5 * max(fa_o, fa_t)), (fa_o, fa_t)
    print(f"   kswin: mean delay ours {np.mean(delay_o):.1f} river {np.mean(delay_t):.1f}; false alarms ours {fa_o} river {fa_t}")


def test_feature_statistic_shape():
    X = np.random.default_rng(0).normal(size=(20000, 77)).astype(np.float32)
    s = feature_statistic(X, batch=100)
    assert s.shape == (200,)
    assert abs(float(s.mean()) - 0.798) < 0.02           # E|N(0,1)| = sqrt(2/pi)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
