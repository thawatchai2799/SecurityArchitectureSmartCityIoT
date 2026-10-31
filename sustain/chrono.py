"""
chrono.py
---------
The operational cost of keeping a smart-city intrusion detector alive, measured on a
chronological stream.

The previous article (Chomsiri & Phunsa 2026) showed (E14) that a detector trained once detects essentially nothing
two days later, and (E15) that the *inference* energy of the deployed tree is negligible
(0.002 kWh per gateway-year). What it did not measure is the cost of the thing that keeps the
detector useful: re-training, and -- in the federated design -- the model traffic and ledger
anchoring that every re-training round generates. This module replays the capture week window by
window, lets a *re-training policy* decide when to re-train, and charges every re-training to the
protocol that performed it.

Protocols (who learns, and what crosses the district boundary)
    tree_local   depth-8 decision tree per district, re-fitted on the district's own full history.
                 Nothing leaves the district. (The edge model of the article.)
    tree_cap     the same tree re-fitted on at most the district's last 160,000 flows (one capture
                 day): bounds the refit cost that otherwise grows with the age of the deployment.
    mlp_local    MLP(32,16) per district, continued (warm-start) on the flows seen since the last
                 re-training. Nothing leaves the district.
    fedavg       one global MLP(32,16); each re-training is R FedAvg rounds over the K districts,
                 each round one pass of local_epochs over the new flows. Weights cross the boundary
                 (up and down), raw flows do not.
    lpra         fedavg + the LPRA screen of the article (poc.robust_fl.screen_updates), with
                 the accept / quarantine decision recorded for anchoring.
    central      raw flows exported to the cloud, one MLP continued there. Raw flows cross the
                 boundary; no weights do.

Re-training policies (when)
    static       never (the "deploy and forget" model of E14)
    every_p      after every p-th window
    trigger      label-free, output-based: re-train when the detector's own alert rate on the
                 window just scored moves by more than `delta` from the previous window
                 (an operator can compute this without any label)
    drift        label-free, input-based: re-train when the window's standardised feature-mean
                 vector is farther from the initial-training reference than `drift_z` times the
                 window-to-window spread observed inside the initial training period
                 (a feature-distribution drift detector; sees traffic change even when the
                 detector raises no alert)
    oracle       re-train when the true F1 on the window just scored fell below `f1_floor`
                 (needs labels; an upper bound for any trigger)
    adwin        label-free, input-based: ADWIN (Bifet & Gavalda 2007) on the per-flow feature
                 statistic of drift.feature_statistic (mini-batches of 100 flows); re-train after
                 a window in which it signalled, then reset
    kswin        label-free, input-based: KSWIN (Raab et al. 2020) on the same statistic
    ddm          label-using, output-based: DDM (Gama et al. 2004) on the 0/1 error of the
                 deployed detector on every flow of the window (needs the labels, like oracle)
    drift_fb     the drift trigger with a clock-driven fallback: re-train when the drift trigger fires
                 or when `fallback` windows (default 8, one capture day) have passed since the last
                 re-training, whichever comes first
    The three standard detectors cost CPU time of their own; it is measured per window
    (trigger_cpu_s) and reported next to the re-training cost.

Every policy is charged the same way. At each test window t the current model(s) score the
window first (that is what is reported), then the policy decides whether to re-train on the
flows of windows (last_retrain, t]; labels for those flows are assumed available at that point,
the same assumption the rolling protocol of E14 makes.

What is measured directly (per re-training event)
    cpu_s            process CPU time of the training computation, single-threaded
    bytes_up/down    model traffic across the district boundary (weights, float32)
    raw_bytes        raw flow features exported (central only; features x 4 bytes + 1 label byte)
    tx               ledger transactions the design generates (model-version anchors, and for the
                     federated protocols one per client update plus one per global model per round)
    gflop            arithmetic of the training computation, counted analytically from the model
                     (hardware-independent; used to calibrate to edge-class boards)

Energy is NOT computed here: lifecycle.py turns CPU-seconds and bytes into joules and CO2e with
stated, adjustable assumptions, exactly as E15 did.
"""
from __future__ import annotations
import os
import time
import copy
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, precision_score, recall_score, confusion_matrix

from poc.federated import _weights_of, _set_weights, _hash_weights, DISTRICTS


def _make_mlp(seed, hidden=(32, 16)):
    # same architecture / optimiser settings as poc.federated._make_mlp, but warm_start=False:
    # partial_fit is incremental on its own, and sklearn refuses warm_start when a batch holds one class
    return MLPClassifier(hidden_layer_sizes=hidden, max_iter=1, warm_start=False, random_state=seed,
                         learning_rate_init=1e-3)
from poc.robust_fl import screen_updates, _flat, _unflat

from .drift import ADWIN, KSWIN, DDM, feature_statistic

PROTOCOLS = ["tree_local", "tree_cap", "mlp_local", "fedavg", "lpra", "central"]
POLICIES = ["static", "every_1", "every_2", "every_4", "every_8", "trigger", "drift", "oracle",
            "adwin", "kswin", "ddm", "drift_fb"]
FALLBACK_WINDOWS = 8          # drift_fb: re-train at least once per capture day (8 flow-count windows)
DETECTOR_POLICIES = ("adwin", "kswin", "ddm")
TREE_CAP_FLOWS = 160000      # tree_cap: refit on at most the last 160,000 flows (= one capture day)
CLASSES = np.array([0, 1])


# --------------------------------------------------------------------------------------------- #
#  accounting helpers
# --------------------------------------------------------------------------------------------- #
def _n_params(hidden, d):
    sizes = [d, *hidden, 1]
    return sum(a * b + b for a, b in zip(sizes[:-1], sizes[1:]))


def _mlp_train_gflop(n_samples, epochs, hidden, d):
    # forward ~2 FLOP per weight, backward ~4 FLOP per weight (Adam update not counted): 6 x params
    return 6.0 * _n_params(hidden, d) * n_samples * epochs / 1e9


def _tree_train_gflop(n_samples, d, depth):
    # sklearn's best-split search evaluates every (feature, threshold) at every node; an upper
    # bound of ~n log n per feature per level; we count n x d x depth x ~log2(n) comparisons.
    return n_samples * d * depth * max(np.log2(max(n_samples, 2)), 1) / 1e9


def _score(y, p):
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    return dict(f1=float(f1_score(y, p, zero_division=0)),
                precision=float(precision_score(y, p, zero_division=0)),
                recall=float(recall_score(y, p, zero_division=0)),
                fpr=float(fp / max(fp + tn, 1)), tp=int(tp), fp=int(fp), fn=int(fn), tn=int(tn),
                alert_rate=float(p.mean()), attack_share=float(np.mean(y)), n=int(len(y)))


class _Cpu:
    """CPU-time stopwatch (process_time: all threads of this process; the runner pins BLAS to one)."""
    def __enter__(self):
        self.t0 = time.process_time(); self.w0 = time.perf_counter(); return self
    def __exit__(self, *a):
        self.cpu = time.process_time() - self.t0; self.wall = time.perf_counter() - self.w0


# --------------------------------------------------------------------------------------------- #
#  the learners
# --------------------------------------------------------------------------------------------- #
class Learner:
    """One protocol. Holds the model state and charges each retrain to an accounting record."""

    def __init__(self, protocol: str, k: int, d: int, seed: int, hidden=(32, 16), rounds=5,
                 local_epochs=2, tree_depth=8, history_cap: int | None = None):
        self.p, self.k, self.d, self.seed = protocol, k, d, seed
        self.hidden, self.rounds, self.local_epochs, self.depth = hidden, rounds, local_epochs, tree_depth
        self.history_cap = history_cap
        self.param_bytes = _n_params(hidden, d) * 4
        self.models = None
        self.hist_X = [[] for _ in range(k)]        # tree_local keeps history (it cannot warm-start)
        self.hist_y = [[] for _ in range(k)]
        self.n_retrain = 0

    # ---- (re)training on new flows per district -------------------------------------------- #
    def train(self, Xd: list[np.ndarray], yd: list[np.ndarray], first: bool) -> dict:
        """Xd[i], yd[i]: the NEW flows of district i since the last retraining (standardised)."""
        rec = dict(cpu_s=0.0, wall_s=0.0, bytes_up=0, bytes_down=0, raw_bytes=0, tx=0, gflop=0.0,
                   n_flows=int(sum(len(y) for y in yd)), rounds=0, quarantined=0, inconclusive=0)
        p = self.p
        if p == "tree_local":
            with _Cpu() as c:
                self.models = []
                for i in range(self.k):
                    self.hist_X[i].append(Xd[i]); self.hist_y[i].append(yd[i])
                    X = np.concatenate(self.hist_X[i]); y = np.concatenate(self.hist_y[i])
                    if self.history_cap and len(y) > self.history_cap:
                        X, y = X[-self.history_cap:], y[-self.history_cap:]
                    m = DecisionTreeClassifier(max_depth=self.depth, random_state=self.seed)
                    m.fit(X, y); self.models.append(m)
                    rec["gflop"] += _tree_train_gflop(len(y), self.d, self.depth)
            rec["tx"] = self.k                                   # one model-version anchor per district
        elif p == "mlp_local":
            with _Cpu() as c:
                if first:
                    self.models = [_make_mlp(self.seed + i, self.hidden) for i in range(self.k)]
                for i in range(self.k):
                    if len(yd[i]) == 0:
                        continue
                    for _ in range(self.local_epochs * (self.rounds if first else 1)):
                        self.models[i].partial_fit(Xd[i], yd[i], classes=CLASSES)
                    rec["gflop"] += _mlp_train_gflop(len(yd[i]), self.local_epochs * (self.rounds if first else 1),
                                                     self.hidden, self.d)
            rec["tx"] = self.k
        elif p in ("fedavg", "lpra"):
            with _Cpu() as c:
                if first:
                    # initialise from one district's own data (no pooled draw), as in the article
                    g = _make_mlp(self.seed, self.hidden)
                    i0 = int(np.argmax([len(y) for y in yd]))
                    rng = np.random.default_rng(self.seed)
                    boot = rng.choice(len(yd[i0]), min(500, len(yd[i0])), replace=False)
                    if len(np.unique(yd[i0][boot])) < 2:          # need both classes to initialise
                        pos = np.where(yd[i0] == 1)[0]; neg = np.where(yd[i0] == 0)[0]
                        boot = np.concatenate([rng.choice(pos, min(250, len(pos)), replace=False),
                                               rng.choice(neg, min(250, len(neg)), replace=False)])
                    g.fit(Xd[i0][boot], yd[i0][boot]); self.models = g
                g = self.models
                tc, ti = _weights_of(g)
                for r in range(self.rounds):
                    gvec = _flat(*_weights_of(g)); vecs, ns = [], []
                    for i in range(self.k):
                        if len(yd[i]) == 0:
                            continue
                        m = copy.deepcopy(g); _set_weights(m, *_weights_of(g))
                        for _ in range(self.local_epochs):
                            m.partial_fit(Xd[i], yd[i], classes=CLASSES)
                        vecs.append(_flat(*_weights_of(m))); ns.append(len(yd[i]))
                        rec["gflop"] += _mlp_train_gflop(len(yd[i]), self.local_epochs, self.hidden, self.d)
                    if not vecs:
                        break
                    vecs = np.stack(vecs); ns = np.array(ns, dtype=float)
                    if p == "lpra":
                        accept, stats = screen_updates(vecs, gvec)
                        if accept is None:
                            rec["inconclusive"] += 1; accept = np.zeros(len(ns), bool)
                        rec["quarantined"] += int((~accept).sum())
                        if accept.sum() == 0:
                            new = gvec
                        else:
                            w = ns * accept; w = w / w.sum(); new = (vecs * w[:, None]).sum(axis=0)
                    else:
                        w = ns / ns.sum(); new = (vecs * w[:, None]).sum(axis=0)
                    nc, ni = _unflat(new, tc, ti); _set_weights(g, nc, ni)
                    rec["rounds"] += 1
                    rec["bytes_up"] += len(ns) * self.param_bytes      # each participating client uploads
                    rec["bytes_down"] += len(ns) * self.param_bytes    # and receives the new global
                    rec["tx"] += len(ns) + 1                           # client-update hashes + global hash
            rec["model_hash"] = _hash_weights(*_weights_of(g))
        elif p == "central":
            with _Cpu() as c:
                X = np.concatenate([x for x in Xd if len(x)]); y = np.concatenate([v for v in yd if len(v)])
                if first:
                    self.models = _make_mlp(self.seed, self.hidden)
                ep = self.local_epochs * self.rounds
                for _ in range(ep):
                    self.models.partial_fit(X, y, classes=CLASSES)
                rec["gflop"] += _mlp_train_gflop(len(y), ep, self.hidden, self.d)
            rec["raw_bytes"] = int(sum(len(v) for v in yd) * (self.d * 4 + 1))
            rec["tx"] = 1
        else:
            raise ValueError(p)
        rec["cpu_s"], rec["wall_s"] = c.cpu, c.wall
        self.n_retrain += 1
        return rec

    # ---- scoring --------------------------------------------------------------------------- #
    def predict(self, Xd: list[np.ndarray]) -> list[np.ndarray]:
        if self.p in ("tree_local", "mlp_local"):
            return [self.models[i].predict(Xd[i]) if len(Xd[i]) else np.zeros(0, int) for i in range(self.k)]
        return [self.models.predict(Xd[i]) if len(Xd[i]) else np.zeros(0, int) for i in range(self.k)]


# --------------------------------------------------------------------------------------------- #
#  the replay
# --------------------------------------------------------------------------------------------- #
def replay(data: dict, protocol: str, policy: str, w_init: int = 16, seed: int = 42,
           rounds: int = 5, local_epochs: int = 2, delta: float = 0.05, f1_floor: float = 0.5,
           drift_z: float = 3.0, history_cap: int | None = None, verbose: bool = False,
           standardise_inplace: bool = False) -> dict:
    """Replay the stream with one protocol under one re-training policy.

    policy: one of POLICIES
    w_init: windows used for the initial training (16 = Monday + Tuesday)
    standardise_inplace: overwrite data["X"] with its standardised values instead of allocating a
        second copy (the parallel runner loads a fresh cache per replay, so it passes True; a
        caller that reuses `data` for several replays must leave it False)
    """
    X, y, win, dist = data["X"], data["y"], data["win"], data["district"]
    k, n_win, d = data["meta"]["k"], data["meta"]["n_windows"], X.shape[1]

    # standardiser on the initial training windows (pooled statistics, as in the article);
    # applied in float32 blocks so that no float64 copy of the whole stream is ever allocated
    init = win < w_init
    scaler = StandardScaler().fit(X[init])
    mu = scaler.mean_.astype(np.float32); sd = scaler.scale_.astype(np.float32)
    Xs = X if (standardise_inplace and X.dtype == np.float32 and X.flags.writeable) else np.empty_like(X, dtype=np.float32)
    for a0 in range(0, len(X), 200000):
        blk = X[a0:a0 + 200000]
        Xs[a0:a0 + 200000] = (blk - mu) / sd

    def by_district(mask):
        return ([Xs[mask & (dist == i)] for i in range(k)], [y[mask & (dist == i)] for i in range(k)])

    learner_protocol = protocol
    if protocol == "tree_cap":
        learner_protocol, history_cap = "tree_local", TREE_CAP_FLOWS
    L = Learner(learner_protocol, k, d, seed, rounds=rounds, local_epochs=local_epochs, history_cap=history_cap)
    events, per_window = [], []
    Xd, yd = by_district(init)
    rec = L.train(Xd, yd, first=True); rec.update(window=w_init - 1, kind="initial"); events.append(rec)
    last_retrain = w_init - 1
    prev_alert = None
    # drift reference: per-window feature means during initial training, and their spread
    init_means = np.stack([Xs[win == t].mean(axis=0) for t in range(w_init)])
    ref_mean = init_means.mean(axis=0)
    init_dist = np.linalg.norm(init_means - ref_mean, axis=1)
    drift_thr = init_dist.mean() + drift_z * init_dist.std()
    period = int(policy.split("_")[1]) if policy.startswith("every_") else None
    detector = None
    if policy == "adwin":
        detector = ADWIN()
    elif policy == "kswin":
        detector = KSWIN(seed=seed)
    elif policy == "ddm":
        detector = DDM()
    elif policy not in ("static", "trigger", "drift", "drift_fb", "oracle") and period is None:
        raise ValueError(policy)

    for t in range(w_init, n_win):
        m = win == t
        Xd, yd = by_district(m)
        with _Cpu() as c:
            preds = L.predict(Xd)
        pooled = _score(np.concatenate(yd), np.concatenate(preds))
        pooled.update(window=t, day=str(data["day"][m][0]), infer_cpu_s=c.cpu,
                      windows_since_retrain=t - last_retrain)
        for i in range(k):
            if len(yd[i]):
                s = _score(yd[i], preds[i]); pooled[f"f1_d{i}"] = s["f1"]; pooled[f"recall_d{i}"] = s["recall"]
        per_window.append(pooled)

        # ---- policy decision, using only what is observable after scoring window t --------- #
        retrain = False
        if policy == "static":
            retrain = False
        elif period is not None:
            retrain = ((t - w_init + 1) % period == 0)
        elif policy == "trigger":
            a = pooled["alert_rate"]
            retrain = prev_alert is not None and abs(a - prev_alert) > delta
            prev_alert = a
        elif policy in ("drift", "drift_fb"):
            dist_t = float(np.linalg.norm(Xs[m].mean(axis=0) - ref_mean))
            pooled["drift_distance"] = dist_t
            retrain = dist_t > drift_thr
            if policy == "drift_fb" and (t - last_retrain) >= FALLBACK_WINDOWS:
                retrain = True                                   # clock-driven fallback
        elif policy == "oracle":
            retrain = pooled["attack_share"] > 0 and pooled["f1"] < f1_floor
        elif policy in ("adwin", "kswin"):
            with _Cpu() as c:
                stat = feature_statistic(Xs[m])
                retrain = any(detector.update(v) for v in stat)
            pooled["trigger_cpu_s"] = c.cpu
        elif policy == "ddm":
            with _Cpu() as c:
                err = (np.concatenate(preds) != np.concatenate(yd)).astype(np.int8)
                retrain = detector.update_batch(err)
            pooled["trigger_cpu_s"] = c.cpu
        pooled.setdefault("trigger_cpu_s", 0.0)
        pooled["retrained_after"] = bool(retrain)
        if retrain:
            mm = (win > last_retrain) & (win <= t)
            Xn, yn = by_district(mm)
            rec = L.train(Xn, yn, first=False); rec.update(window=t, kind="retrain"); events.append(rec)
            last_retrain = t
            if detector is not None:
                detector.reset()
            if verbose:
                print(f"    retrain after w{t}: cpu {rec['cpu_s']:.2f}s  bytes {rec['bytes_up']+rec['bytes_down']+rec['raw_bytes']:,}  tx {rec['tx']}")

    test = [r for r in per_window]
    f1s = np.array([r["f1"] for r in test]); att = np.array([r["attack_share"] for r in test])
    tp = sum(r["tp"] for r in test); fn = sum(r["fn"] for r in test); fp = sum(r["fp"] for r in test); tn = sum(r["tn"] for r in test)
    ev = [e for e in events if e["kind"] == "retrain"]
    summary = dict(protocol=protocol, policy=policy, seed=seed, w_init=w_init, rounds=rounds,
                   local_epochs=local_epochs, n_test_windows=len(test), n_windows=int(n_win), n_feats=int(d),
                   dataset=str(data["meta"].get("dataset", "cic2017")),
                   mean_f1=float(f1s.mean()),                            # equal weight per window
                   mean_f1_attack_windows=float(f1s[att > 0].mean()) if (att > 0).any() else float("nan"),
                   stream_f1=float(2 * tp / max(2 * tp + fp + fn, 1)),   # micro over the whole stream
                   stream_recall=float(tp / max(tp + fn, 1)), stream_fpr=float(fp / max(fp + tn, 1)),
                   missed_attacks=int(fn), false_alarms=int(fp),
                   n_retrain=len(ev),
                   retrain_cpu_s=float(sum(e["cpu_s"] for e in ev)),
                   retrain_wall_s=float(sum(e["wall_s"] for e in ev)),
                   retrain_gflop=float(sum(e["gflop"] for e in ev)),
                   bytes_up=int(sum(e["bytes_up"] for e in ev)), bytes_down=int(sum(e["bytes_down"] for e in ev)),
                   raw_bytes=int(sum(e["raw_bytes"] for e in ev)), tx=int(sum(e["tx"] for e in ev)),
                   fl_rounds=int(sum(e["rounds"] for e in ev)),
                   quarantined=int(sum(e["quarantined"] for e in ev)),
                   init_cpu_s=float(events[0]["cpu_s"]), init_gflop=float(events[0]["gflop"]),
                   infer_cpu_s=float(sum(r["infer_cpu_s"] for r in test)),
                   trigger_cpu_s=float(sum(r.get("trigger_cpu_s", 0.0) for r in test)),
                   param_bytes=int(L.param_bytes))
    return dict(summary=summary, per_window=per_window, events=events)
