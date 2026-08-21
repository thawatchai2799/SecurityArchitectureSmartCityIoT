"""
byzantine.py
------------
Head-to-head evaluation of LPRA against standard Byzantine-robust aggregators,
with 1 or 2 attackers out of K districts, four attacks including an adaptive
"stealth" attack that stays inside the honest norm envelope.

Aggregators
    fedavg        sample-weighted mean (no defence)
    median        coordinate-wise median
    trimmed_mean  coordinate-wise trimmed mean (beta = #attackers assumed)
    krum          Krum (Blanchard et al. 2017), f = #attackers assumed
    multi_krum    Multi-Krum, m = K - f selected then averaged
    lpra          ours: median/MAD distance + cosine screen, then weighted mean,
                  decision + hash anchored on ledger (auditable)

Attacks (attacker districts = the first `n_att` districts)
    scale    w_g + 10 (w_i - w_g)
    flip     trained on flipped labels
    noise    Gaussian noise weights
    stealth  "a little is enough" (Baruch et al. 2019): mean_honest - z * std_honest,
             z = 1.0  -> stays within honest spread, defeats norm-based screens
    adaptive an attacker that KNOWS the defence: it places its update at a chosen multiple `strength`
             of the honest median distance, i.e. exactly where it wants to sit relative to LPRA's
             stage-1 threshold (gamma = 2.5 by default), and picks the direction that hurts most:
                 opposite   - anti-parallel to the honest mean update (maximum damage, but a cosine
                              test can see it)
                 orthogonal - perpendicular to the honest mean update (invisible to a cosine test,
                              so only the distance test can stop it)
             Sweeping `strength` traces the boundary of what LPRA can and cannot stop.
"""
from __future__ import annotations
import copy
import time
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
from .federated import (partition, _make_mlp, _weights_of, _set_weights, _hash_weights,
                        _bootstrap, DISTRICTS)
from .robust_fl import _flat, _unflat, screen_updates

AGGREGATORS = ["fedavg", "median", "trimmed_mean", "krum", "multi_krum", "lpra"]
ATTACKS = ["none", "scale", "flip", "noise", "stealth", "adaptive"]


def _krum_scores(V, f):
    n = len(V); D = ((V[:, None, :] - V[None, :, :]) ** 2).sum(-1)
    m = n - f - 2
    scores = []
    for i in range(n):
        d = np.sort(np.delete(D[i], i))[:max(m, 1)]
        scores.append(d.sum())
    return np.array(scores)


def aggregate(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
    """Return (new_vec, accepted_mask, info)."""
    n = len(V); ns = np.asarray(ns, float)
    if name == "fedavg":
        w = ns / ns.sum(); return (V * w[:, None]).sum(0), np.ones(n, bool), {}
    if name == "median":
        return np.median(V, 0), np.ones(n, bool), {}
    if name == "trimmed_mean":
        b = min(f, (n - 1) // 2); S = np.sort(V, 0)
        return S[b:n - b].mean(0), np.ones(n, bool), {"beta": b}
    if name == "krum":
        s = _krum_scores(V, f); i = int(np.argmin(s)); acc = np.zeros(n, bool); acc[i] = True
        return V[i], acc, {"krum_scores": s.round(3).tolist()}
    if name == "multi_krum":
        s = _krum_scores(V, f); m = max(n - f, 1); sel = np.argsort(s)[:m]
        acc = np.zeros(n, bool); acc[sel] = True; return V[sel].mean(0), acc, {"krum_scores": s.round(3).tolist()}
    if name == "lpra":
        acc, stats = screen_updates(V, gvec, gamma=lpra_gamma, version=lpra_version); w = ns * acc; w = w / w.sum()
        return (V * w[:, None]).sum(0), acc, stats
    raise ValueError(name)


def run_byzantine(X, y_bin, y_multi, X_test, y_test, k=5, rounds=10, local_epochs=2, seed=42,
                  hidden=(32, 16), attack="scale", n_att=1, aggregator="lpra", f_assumed=None, ledger=None,
                  regime="non-iid", lpra_gamma=2.5, lpra_version="v2", strength=2.0, direction="orthogonal"):
    rng = np.random.default_rng(seed)
    scaler = StandardScaler().fit(X)      # pooled statistics; see note in federated.py
    Xs = scaler.transform(X).astype(np.float32); Xt = scaler.transform(X_test).astype(np.float32)
    parts = partition(y_multi, k, regime, seed)
    attackers = set(range(n_att)) if attack != "none" else set()
    f = f_assumed if f_assumed is not None else max(n_att, 1)
    boot = _bootstrap(y_bin, rng, 500)
    g = _make_mlp(seed, hidden); g.fit(Xs[boot], y_bin[boot]); classes = np.array([0, 1])
    tc, ti = _weights_of(g)
    hist, caught, quarantined_total, honest_quarantined = [], 0, 0, 0
    t0 = time.perf_counter()
    for r in range(rounds):
        gvec = _flat(*_weights_of(g)); vecs, ns = [], []
        for i, idx in enumerate(parts):
            m = copy.deepcopy(g); _set_weights(m, *_weights_of(g))
            yb = y_bin[idx].copy()
            if i in attackers and attack == "flip":
                yb = 1 - yb
            for _ in range(local_epochs):
                m.partial_fit(Xs[idx], yb, classes=classes)
            vecs.append(_flat(*_weights_of(m))); ns.append(len(idx))
        V = np.stack(vecs)
        if attackers:
            honest = np.array([i for i in range(k) if i not in attackers])
            for i in attackers:
                if attack == "scale":
                    V[i] = gvec + 10.0 * (V[i] - gvec)
                elif attack == "noise":
                    V[i] = gvec + rng.normal(0, 1.0, size=gvec.shape)
                elif attack == "stealth":   # a little is enough
                    mu, sd = V[honest].mean(0), V[honest].std(0)
                    V[i] = mu - 1.0 * sd
                elif attack == "adaptive":
                    # the attacker reproduces the defender's own statistic from the honest updates
                    # it can observe (the global model of the previous round plus its own training),
                    # then places itself at `strength` x median distance from the median.
                    med = np.median(V[honest], axis=0)
                    d_h = np.linalg.norm(V[honest] - med, axis=1)
                    scale_len = strength * float(np.median(d_h))
                    crowd = V[honest].mean(0) - gvec           # where the honest updates are going
                    if direction == "opposite":
                        r = -crowd
                    else:                                       # orthogonal to the crowd
                        r = rng.normal(0, 1.0, size=gvec.shape)
                        r -= crowd * float(np.dot(r, crowd) / (np.dot(crowd, crowd) + 1e-12))
                    r = r / (np.linalg.norm(r) + 1e-12)
                    V[i] = med + scale_len * r
        new, acc, info = aggregate(aggregator, V, ns, gvec, f, lpra_gamma, lpra_version)
        nc, ni = _unflat(new, tc, ti); _set_weights(g, nc, ni)
        f1 = f1_score(y_test, g.predict(Xt))
        att_rej = [i for i in attackers if not acc[i]]; hon_rej = [i for i in range(k) if i not in attackers and not acc[i]]
        caught += len(att_rej) == len(attackers) and len(attackers) > 0
        quarantined_total += len(att_rej); honest_quarantined += len(hon_rej)
        hist.append(dict(round=r + 1, f1=f1, accepted=[DISTRICTS[i] if i < 5 else f"D{i}" for i in range(k) if acc[i]]))
        if ledger is not None:
            ledger.submit(dict(kind="MODEL_UPDATE", round=r + 1, model_hash=_hash_weights(nc, ni),
                               aggregator=aggregator, accepted=int(acc.sum()), info=info), submitter="CloudAggregator")
    return dict(aggregator=aggregator, lpra_version=lpra_version, attack=attack, n_att=n_att, k=k, seed=seed, rounds=rounds,
                strength=strength if attack == "adaptive" else None,
                direction=direction if attack == "adaptive" else None,
                final_f1=hist[-1]["f1"], mean_last3_f1=float(np.mean([h["f1"] for h in hist[-3:]])),
                rounds_all_attackers_rejected=int(caught),
                attacker_rejections=int(quarantined_total), honest_rejections=int(honest_quarantined),
                time_s=time.perf_counter() - t0, history=hist)
