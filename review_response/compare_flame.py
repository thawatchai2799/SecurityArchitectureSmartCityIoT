"""Reviewer 3, point 2: no FLAME comparison, though FLAME is the standard
clustering-based defence.  This implements FLAME's three steps as
described in Nguyen et al. (NDSS 2022):

  1  cluster client updates by pairwise cosine distance (HDBSCAN with
     min_cluster_size = K/2 + 1); keep the largest cluster
  2  clip every kept update to the median L2 norm of the kept set
  3  add Gaussian noise (sigma = lambda * median norm) to the aggregate

and runs it beside LPRA v2 and FedAvg on the attacks in the paper plus the
sign-flip attack from the Comment 4 response, K=5, three seeds.
sklearn's HDBSCAN is used; with K=5 the clustering degenerates to
"largest group by cosine", which is the regime FLAME's authors note it is
weakest in, so this is a fair-but-unflattering setting for FLAME too.
"""
import os, sys, json, copy
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split
from sklearn.cluster import HDBSCAN

_orig_aggregate = byzantine.aggregate

def flame(V, ns, gvec, lam=0.001, seed=0):
    K = len(V); deltas = V - gvec
    norms = np.linalg.norm(deltas, axis=1) + 1e-12
    cos_dist = 1 - (deltas @ deltas.T) / np.outer(norms, norms)
    np.fill_diagonal(cos_dist, 0); cos_dist = np.clip(cos_dist, 0, 2)
    labels = HDBSCAN(min_cluster_size=max(2, K // 2 + 1), metric="precomputed").fit(cos_dist).labels_
    if (labels >= 0).sum() == 0:
        keep = np.ones(K, bool)                         # no cluster found: keep all
    else:
        big = np.bincount(labels[labels >= 0]).argmax(); keep = labels == big
    med_norm = np.median(norms[keep])
    clipped = np.array([gvec + d * min(1.0, med_norm / n) for d, n in zip(deltas, norms)])
    w = ns * keep; w = w / w.sum()
    agg = (clipped * w[:, None]).sum(0)
    rng = np.random.default_rng(seed)
    agg = agg + rng.normal(0, lam * med_norm, size=agg.shape)
    return agg, keep, dict(kept=int(keep.sum()))

def aggregate_with_flame(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
    if name == "flame":
        return flame(V, ns, gvec)
    return _orig_aggregate(name, V, ns, gvec, f, lpra_gamma, lpra_version)

byzantine.aggregate = aggregate_with_flame

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    conds = [("none", 0, {}), ("scale", 1, {}), ("flip", 1, {}), ("noise", 1, {}), ("stealth", 1, {}),
             ("adaptive", 2, dict(strength=6.0, direction="opposite"))]
    out = []
    print(f"{'attack':10} {'n_att':>5}  {'FedAvg':>7} {'FLAME':>7} {'LPRA':>7}   {'FLAME att_rej':>13} {'LPRA att_rej':>12}")
    for attack, n_att, kw in conds:
        row = dict(attack=attack, n_att=n_att)
        for agg in ("fedavg", "flame", "lpra"):
            f1s, ar, hr = [], 0, 0
            for seed in (42, 43, 44):
                r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=5, rounds=10, regime="non-iid", seed=seed,
                                            attack=attack, n_att=n_att, aggregator=agg, lpra_version="v2", **kw)
                f1s.append(r["mean_last3_f1"]); ar += r["attacker_rejections"]; hr += r["honest_rejections"]
            row[agg] = dict(f1=round(float(np.mean(f1s)), 4), att_rej=ar, hon_rej=hr)
        out.append(row)
        d = 30 * n_att if n_att else 0
        print(f"{attack:10} {n_att:5}  {row['fedavg']['f1']:7.4f} {row['flame']['f1']:7.4f} {row['lpra']['f1']:7.4f}   "
              f"{row['flame']['att_rej']:>6}/{d:<6} {row['lpra']['att_rej']:>5}/{d:<6}  hon: FLAME {row['flame']['hon_rej']} LPRA {row['lpra']['hon_rej']}", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "flame_comparison.json"), "w"), indent=1)
    print("\nwrote flame_comparison.json")
