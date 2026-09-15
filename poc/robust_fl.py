"""
robust_fl.py
------------
Contribution-specific extensions to the federated layer:

(1) Ledger-anchored, poisoning-resilient aggregation (LPRA)
    Every district submits (weights, hash) each round.  Before FedAvg the cloud
    aggregator screens client updates with two cheap statistics:
        d_i  = ||w_i - median_j(w_j)||_2           (distance to coordinate-wise median)
        quarantine if d_i > max(median(d) + tau*MAD(d), gamma*median(d))  (tau=3, gamma=2.5)
        then c_i computed against the mean delta of stage-1 survivors; quarantine if c_i < 0.2
        c_i  = cos(w_i - w_g, mean_j(w_j - w_g))   (direction agreement with the crowd)
    A client is quarantined for the round if the robust z-score test fails or c_i < c_min.
    The *decision* (accepted / quarantined, with the statistics) and the hash of the
    accepted global model are written to the permissioned ledger, so that a
    district can later prove it was (or was not) excluded, and so that the model
    provenance is auditable by all agencies.

    Attacks simulated on the Byzantine district:
        scale : sends  w_g + lambda * (w_i - w_g)     (boosted update, lambda = 10)
        flip  : trains on flipped labels (label-flipping poisoning)
        noise : sends Gaussian noise weights

(2) Personalised FL (pFL)
    After the global model converges each district fine-tunes one local epoch on its
    own data (FedAvg + local adaptation).  Reported per district on that district's
    OWN test distribution, which is what a district CISO actually cares about.
"""
from __future__ import annotations
import copy
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
from .federated import (partition, _bootstrap_within, _make_mlp, _weights_of, _set_weights, _hash_weights,
                        _bootstrap, DISTRICTS)


def _flat(coefs, inters):
    return np.concatenate([w.ravel() for w in coefs] + [b.ravel() for b in inters])


def _unflat(vec, template_c, template_i):
    out_c, out_i, k = [], [], 0
    for w in template_c:
        out_c.append(vec[k:k + w.size].reshape(w.shape)); k += w.size
    for b in template_i:
        out_i.append(vec[k:k + b.size].reshape(b.shape)); k += b.size
    return out_c, out_i


def screen_updates(client_vecs: np.ndarray, global_vec: np.ndarray, tau: float = 3.0, gamma: float = 2.5,
                   c_min: float = 0.2, version: str = "v2"):
    K = len(client_vecs)
    med = np.median(client_vecs, axis=0)
    d = np.linalg.norm(client_vecs - med, axis=1)
    mad = 1.4826 * np.median(np.abs(d - np.median(d))) + 1e-9
    thr = max(np.median(d) + tau * mad, gamma * np.median(d))
    S1 = d <= thr                                             # Stage 1 (magnitude)
    deltas = client_vecs - global_vec

    # Algorithm 1 step (6), second clause: too few Stage-1 survivors to form
    # a majority -> do not aggregate, anchor the round as INCONCLUSIVE.
    if S1.sum() <= K // 2:
        return None, dict(dist=d.tolist(), cos=[None] * K, threshold=float(thr),
                          version=version, inconclusive=True, stage1_survivors=int(S1.sum()))

    ref = (deltas[S1].mean(axis=0) if version == "v1"        # v1: mean reference (kept for E17)
           else np.median(deltas[S1], axis=0))                 # v2: coordinate-wise median
    cos = np.array([float(np.dot(x, ref) / (np.linalg.norm(x) * np.linalg.norm(ref) + 1e-12))
                    for x in deltas])
    accept = S1 & (cos >= c_min)                              # Stage 2 (direction), within S1

    # Algorithm 1 step (6), first clause: the accepted set must be a majority;
    # if not, take the floor(K/2)+1 highest-cosine clients OF S1.  Ranking is
    # restricted to S1 so that a Stage-1 rejection is never readmitted.
    if version != "v1" and accept.sum() <= K // 2:
        s1_idx = np.where(S1)[0]
        order = s1_idx[np.argsort(-cos[s1_idx])]
        accept = np.zeros(K, dtype=bool)
        accept[order[:K // 2 + 1]] = True

    return accept, dict(dist=d.tolist(), cos=cos.tolist(), threshold=float(thr),
                        version=version, inconclusive=False, stage1_survivors=int(S1.sum()))

def run_robust_fl(X, y_bin, y_multi, X_test, y_test, k=5, rounds=15, local_epochs=2, regime="non-iid",
                  seed=42, hidden=(32, 16), attack="scale", byzantine=0, defense=True, ledger=None,
                  personalise=True, screen_version="v2"):
    rng = np.random.default_rng(seed)
    scaler = StandardScaler().fit(X)      # pooled statistics; see note in federated.py
    Xs = scaler.transform(X).astype(np.float32); Xt = scaler.transform(X_test).astype(np.float32)
    parts = partition(y_multi, k, regime, seed)
    # per-district local test sets (same distribution as the district's data): hold out 20 %
    loc_tr, loc_te = [], []
    for idx in parts:
        idx = rng.permutation(idx); cut = int(0.8 * len(idx)); loc_tr.append(idx[:cut]); loc_te.append(idx[cut:])
    # Initialise the global model from ONE district's own data (district 0),
    # so no training flow crosses a district boundary at any point.  A
    # pooled draw was used here originally; see CHANGELOG (Reviewer 1, C3).
    boot = _bootstrap_within(y_bin, parts[0], rng, 500)
    g = _make_mlp(seed, hidden); g.fit(Xs[boot], y_bin[boot]); classes = np.array([0, 1])
    tc, ti = _weights_of(g)
    history, quarantine_log = [], []
    for r in range(rounds):
        gvec = _flat(*_weights_of(g)); vecs, ns = [], []
        for i, idx in enumerate(loc_tr):
            m = copy.deepcopy(g); _set_weights(m, *_weights_of(g))
            yb = y_bin[idx].copy()
            if i == byzantine and attack == "flip":
                yb = 1 - yb
            for _ in range(local_epochs):
                m.partial_fit(Xs[idx], yb, classes=classes)
            v = _flat(*_weights_of(m))
            if i == byzantine and attack == "scale":
                v = gvec + 10.0 * (v - gvec)
            elif i == byzantine and attack == "noise":
                v = gvec + rng.normal(0, 1.0, size=v.shape)
            vecs.append(v); ns.append(len(idx))
        vecs = np.stack(vecs); ns = np.array(ns, dtype=float)
        if defense:
            accept, stats = screen_updates(vecs, gvec, version=screen_version)
        else:
            accept, stats = np.ones(k, dtype=bool), {}
        w = ns * accept; w = w / w.sum()
        new = (vecs * w[:, None]).sum(axis=0)
        nc, ni = _unflat(new, tc, ti); _set_weights(g, nc, ni)
        f1 = f1_score(y_test, g.predict(Xt)); h = _hash_weights(nc, ni)
        history.append(dict(round=r + 1, f1=f1, accepted=[DISTRICTS[i] for i in range(k) if accept[i]],
                            quarantined=[DISTRICTS[i] for i in range(k) if not accept[i]], model_hash=h))
        if defense and (~accept).any():
            quarantine_log.append(dict(round=r + 1, quarantined=[DISTRICTS[i] for i in range(k) if not accept[i]],
                                       dist=[round(x, 3) for x in stats["dist"]], cos=[round(x, 3) for x in stats["cos"]]))
        if ledger is not None:
            ledger.submit(dict(kind="MODEL_UPDATE", round=r + 1, model_hash=h,
                               accepted=history[-1]["accepted"], quarantined=history[-1]["quarantined"],
                               screening=stats), submitter="CloudAggregator")
    out = dict(attack=attack if byzantine is not None else "none", defense=defense, regime=regime,
               global_f1=history[-1]["f1"], history=history, quarantine_log=quarantine_log,
               byzantine_caught_rounds=sum(1 for q in quarantine_log if DISTRICTS[byzantine] in q["quarantined"]) if byzantine is not None else 0)
    # ---- personalised FL: local fine-tune, evaluate on each district's own test set ---- #
    if personalise:
        per = []
        for i in range(k):
            gl = f1_score(y_bin[loc_te[i]], g.predict(Xs[loc_te[i]]))
            m = copy.deepcopy(g); _set_weights(m, *_weights_of(g))
            m.partial_fit(Xs[loc_tr[i]], y_bin[loc_tr[i]], classes=classes)
            pf = f1_score(y_bin[loc_te[i]], m.predict(Xs[loc_te[i]]))
            per.append(dict(district=DISTRICTS[i], global_f1_local_test=gl, personalised_f1_local_test=pf))
        out["personalised"] = per
    return out
