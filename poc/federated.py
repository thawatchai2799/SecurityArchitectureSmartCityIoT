"""
federated.py
------------
Simulates *privacy-preserving* collaborative learning between K city districts
(each district = one edge gateway holding its own traffic; raw flows never leave
the district).  Only model weights are exchanged with the cloud aggregator
(FedAvg, McMahan et al. 2017).

Two data-partition regimes are simulated:
    iid     : flows randomly split between districts
    non-iid : each district sees a *different mix of attack types*, e.g. the
              transport district is hit mostly by DDoS, the utility district by
              injection/backdoor ... This is the realistic (and hard) case.

Model: a small MLP whose weights (coefs_/intercepts_) can be averaged directly.
The federated result is compared against
    centralised : all data pooled (upper bound, but no privacy)
    local-only  : each district trains alone (lower bound, no collaboration)
"""
from __future__ import annotations
import copy
import time
import hashlib
import json
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, accuracy_score, recall_score

DISTRICTS = ["Transport", "Energy", "Water", "Healthcare", "e-Gov"]


def _bootstrap(y, rng, n=500):
    """Class-balanced bootstrap used only to initialise the global model.
    A purely random draw can contain a single class on very imbalanced datasets,
    which makes the first fit() fail."""
    idx = []
    for c in np.unique(y):
        pool = np.where(y == c)[0]
        idx.append(rng.choice(pool, min(len(pool), max(1, n // max(len(np.unique(y)), 1))),
                              replace=False))
    return np.concatenate(idx)


def _make_mlp(seed, hidden=(32, 16), max_iter=1):
    return MLPClassifier(hidden_layer_sizes=hidden, max_iter=max_iter, warm_start=True,
                         random_state=seed, learning_rate_init=1e-3)


def partition(y_multi: np.ndarray, k: int, regime: str, seed: int = 42, dominance: float = 0.7):
    """Return list of index arrays, one per district."""
    rng = np.random.default_rng(seed)
    n = len(y_multi)
    if regime == "iid":
        idx = rng.permutation(n)
        return [np.sort(a) for a in np.array_split(idx, k)]

    # non-iid: assign each attack type predominantly to one district; normal traffic
    # is spread evenly (every district sees benign traffic).
    types = sorted(set(y_multi) - {"normal", "benign", "benigntraffic"})
    owner = {t: i % k for i, t in enumerate(types)}
    parts = [[] for _ in range(k)]
    for t in types:
        ids = np.where(y_multi == t)[0]; rng.shuffle(ids)
        n_dom = int(len(ids) * dominance)
        parts[owner[t]].extend(ids[:n_dom].tolist())
        rest = np.array_split(ids[n_dom:], k)
        for i in range(k):
            parts[i].extend(rest[i].tolist())
    normal_ids = np.where(np.isin(y_multi, ["normal", "benign", "benigntraffic"]))[0]
    rng.shuffle(normal_ids)
    for i, chunk in enumerate(np.array_split(normal_ids, k)):
        parts[i].extend(chunk.tolist())
    return [np.sort(np.array(p)) for p in parts]


def _weights_of(m):  # flatten model weights
    return [w.copy() for w in m.coefs_], [b.copy() for b in m.intercepts_]


def _set_weights(m, coefs, inters):
    m.coefs_ = [w.copy() for w in coefs]; m.intercepts_ = [b.copy() for b in inters]


def _hash_weights(coefs, inters) -> str:
    h = hashlib.sha256()
    for w in coefs + inters:
        h.update(np.ascontiguousarray(w, dtype=np.float32).tobytes())
    return h.hexdigest()


def run_federated(X, y_bin, y_multi, X_test, y_test, k=5, rounds=15, local_epochs=2,
                  regime="non-iid", seed=42, hidden=(32, 16), ledger=None):
    """
    Returns dict with per-round global metrics, final comparison and (optionally)
    writes model-update hashes to the blockchain ledger for auditability.
    """
    rng = np.random.default_rng(seed)
    # NOTE (disclosed in the paper): the standardiser is fitted on the pooled training
    # set.  In a deployment these statistics would be agreed in advance or computed with
    # secure aggregation; they are 2 x d numbers, not raw flows.
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X).astype(np.float32); Xt = scaler.transform(X_test).astype(np.float32)
    parts = partition(y_multi, k, regime, seed)

    # ---- global model initialised on a tiny public bootstrap sample ------- #
    boot = _bootstrap(y_bin, rng, 500)
    global_m = _make_mlp(seed, hidden); global_m.fit(Xs[boot], y_bin[boot])
    classes = np.array([0, 1])
    history = []
    t_start = time.perf_counter()
    for r in range(rounds):
        client_w, client_n = [], []
        for i, idx in enumerate(parts):
            local = copy.deepcopy(global_m)
            _set_weights(local, *_weights_of(global_m))
            for _ in range(local_epochs):
                local.partial_fit(Xs[idx], y_bin[idx], classes=classes)
            client_w.append(_weights_of(local)); client_n.append(len(idx))
        # ---- FedAvg --------------------------------------------------------- #
        tot = sum(client_n)
        new_c = [sum(cw[0][l] * n / tot for cw, n in zip(client_w, client_n))
                 for l in range(len(client_w[0][0]))]
        new_i = [sum(cw[1][l] * n / tot for cw, n in zip(client_w, client_n))
                 for l in range(len(client_w[0][1]))]
        _set_weights(global_m, new_c, new_i)
        y_pred = global_m.predict(Xt)
        rec = dict(round=r + 1, f1=f1_score(y_test, y_pred), acc=accuracy_score(y_test, y_pred),
                   recall=recall_score(y_test, y_pred), model_hash=_hash_weights(new_c, new_i),
                   bytes_exchanged=int(sum(w.nbytes for w in new_c + new_i) * 2 * k))
        history.append(rec)
        if ledger is not None:   # anchor each global model version on the ledger
            ledger.submit(dict(kind="MODEL_UPDATE", round=r + 1, model_hash=rec["model_hash"],
                               participants=DISTRICTS[:k], f1_reported=round(rec["f1"], 4)),
                          submitter="CloudAggregator")
    fed_time = time.perf_counter() - t_start

    # ---- baselines ------------------------------------------------------- #
    cen = _make_mlp(seed, hidden, max_iter=rounds * local_epochs)
    t0 = time.perf_counter(); cen.fit(Xs, y_bin); cen_time = time.perf_counter() - t0
    cen_f1 = f1_score(y_test, cen.predict(Xt))
    local_f1 = []
    for idx in parts:
        m = _make_mlp(seed, hidden, max_iter=rounds * local_epochs); m.fit(Xs[idx], y_bin[idx])
        local_f1.append(f1_score(y_test, m.predict(Xt)))

    dist_stats = []
    for i, idx in enumerate(parts):
        vals, cnts = np.unique(y_multi[idx], return_counts=True)
        top = sorted(zip(cnts, vals), reverse=True)[:3]
        dist_stats.append(dict(district=DISTRICTS[i], n_flows=int(len(idx)),
                               attack_ratio=float(y_bin[idx].mean()),
                               top_types=[f"{v}:{c}" for c, v in top]))
    return dict(regime=regime, k=k, rounds=rounds, local_epochs=local_epochs,
                history=history, federated_f1=history[-1]["f1"], federated_time_s=fed_time,
                centralised_f1=cen_f1, centralised_time_s=cen_time,
                local_only_f1_mean=float(np.mean(local_f1)), local_only_f1=local_f1,
                raw_bytes_not_shared=int(Xs.nbytes),
                weight_bytes_per_round=history[-1]["bytes_exchanged"], districts=dist_stats)
