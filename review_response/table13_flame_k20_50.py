"""Extends table13_perseed.py's protocol (Table 13 / E9, district scaling) to add FLAME at the
district counts where its own clustering has enough clients to be meaningful: K in {20,50},
20% Byzantine (n_att = K // 5) under the "scale" attack, plus the no-attack cost comparison.
Same data, split, rounds, seeds and non-IID regime as table13_perseed.py so the numbers are
directly comparable to the published Table 13 rows for FedAvg and LPRA v2 at the same K.
FLAME implementation is the one in review_response/compare_flame.py (Nguyen et al., NDSS 2022:
HDBSCAN clustering by cosine distance, median-norm clipping, Gaussian noise), unmodified.
"""
import os, sys, json, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "table13_flame_k20_50.json")
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split
from sklearn.cluster import HDBSCAN

def flame(V, ns, gvec, lam=0.001, seed=0):
    K = len(V); deltas = V - gvec
    norms = np.linalg.norm(deltas, axis=1) + 1e-12
    cos_dist = 1 - (deltas @ deltas.T) / np.outer(norms, norms)
    np.fill_diagonal(cos_dist, 0); cos_dist = np.clip(cos_dist, 0, 2)
    # FLAME's reference settings (Nguyen et al., USENIX Security 2022): min_samples = 1 and a single cluster allowed, so the
    # benign majority can form one cluster. scikit-learn's defaults (min_samples = min_cluster_size,
    # allow_single_cluster = False) cannot return that cluster and found none in any round; those runs are
    # kept in *_sklearn_defaults.json for the record.
    labels = HDBSCAN(min_cluster_size=max(2, K // 2 + 1), min_samples=1, allow_single_cluster=True,
                     metric="precomputed").fit(cos_dist).labels_
    if (labels >= 0).sum() == 0:
        keep = np.ones(K, bool)
    else:
        big = np.bincount(labels[labels >= 0]).argmax(); keep = labels == big
    CLUSTER_LOG.append(dict(K=int(K), n_clusters=int(len(set(labels[labels >= 0]))), kept=int(keep.sum())))
    med_norm = np.median(norms)                       # FLAME step 7: S_t = median over ALL n clients' update norms
    clipped = np.array([gvec + d * min(1.0, med_norm / n) for d, n in zip(deltas, norms)])
    w = keep / keep.sum()                             # FLAME step 10: plain mean over the admitted set L
    agg = (clipped * w[:, None]).sum(0)
    FLAME_CALLS[0] += 1
    rng = np.random.default_rng(seed + FLAME_CALLS[0])  # fresh noise every round (a fixed seed would add the same vector each round)
    agg = agg + rng.normal(0, lam * med_norm, size=agg.shape)
    return agg, keep, dict(kept=int(keep.sum()))

FLAME_CALLS = [0]
CLUSTER_LOG = []   # one entry per FLAME aggregation round: how many clusters HDBSCAN found and how many clients were kept
_orig_aggregate = byzantine.aggregate
def aggregate_with_flame(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
    if name == "flame": return flame(V, ns, gvec)
    return _orig_aggregate(name, V, ns, gvec, f, lpra_gamma, lpra_version)
byzantine.aggregate = aggregate_with_flame

ton = load_ton_iot(sample=60000)
Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

out = []
t_start = time.time()
for K in (20, 50):
    for agg in ("fedavg", "flame", "lpra"):
        for attack, n_att in (("none", 0), ("scale", max(1, K // 5))):
            for seed in (42, 43, 44):
                t0 = time.time()
                r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid",
                                            seed=seed, attack=attack, n_att=n_att, aggregator=agg,
                                            lpra_version="v2")
                row = dict(K=K, agg=agg, attack=attack, n_att=n_att, seed=seed,
                          final_f1=round(r["final_f1"], 4), last3=round(r["mean_last3_f1"], 4), last3_raw=float(r["mean_last3_f1"]),
                          hon=r["honest_rejections"], att=r["attacker_rejections"],
                          caught=r["rounds_all_attackers_rejected"])
                if agg == "flame":
                    log = CLUSTER_LOG[-10:]   # the 10 rounds just run
                    row["flame_rounds_no_cluster"] = sum(1 for e in log if e["n_clusters"] == 0)
                    row["flame_rounds_cluster_kept_all"] = sum(1 for e in log if e["n_clusters"] > 0 and e["kept"] == K)
                    row["flame_rounds_cluster_excluded_some"] = sum(1 for e in log if e["n_clusters"] > 0 and e["kept"] < K)
                out.append(row)
                print(row, f"{time.time()-t0:.1f}s", flush=True)
                json.dump(out, open(OUT, "w"), indent=1)
print(f"\nTOTAL TIME: {time.time()-t_start:.1f}s over {len(out)} runs")
json.dump(CLUSTER_LOG, open(OUT.replace(".json", "_clusterlog.json"), "w"))
print("wrote", OUT)
