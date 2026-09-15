"""If the K >= 20 honest-rejection collapse is a partitioning artifact, a
partition without orphan districts should not show it.

Corrected non-IID partition: when K exceeds the number of attack families,
each family's 70% dominant share is split evenly among the ceil(K/9)
districts assigned to it, so every district receives a dominant family and
no district is an orphan.  For K <= 9 this reduces to the original scheme.
Everything else (30% remainder spread evenly, benign spread evenly, seeded
shuffles) is unchanged.
"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine, federated
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

BENIGN = {"normal", "benign", "benigntraffic"}

def partition_no_orphans(y_multi, k, regime, seed=42, dominance=0.7):
    rng = np.random.default_rng(seed)
    if regime == "iid":
        return federated.partition(y_multi, k, regime, seed, dominance)
    types = sorted(set(y_multi) - BENIGN)
    # Round-robin in whichever direction is longer, so that BOTH every family
    # has at least one owner (K < T: original scheme, several families per
    # district) AND every district has at least one family (K > T: several
    # districts per family).  For K = T the two coincide.
    T = len(types)
    owners_of = {t: [] for t in types}
    if k <= T:
        for i, t in enumerate(types):
            owners_of[t].append(i % k)
    else:
        for d in range(k):
            owners_of[types[d % T]].append(d)
    parts = [[] for _ in range(k)]
    for t in types:
        ids = np.where(y_multi == t)[0]; rng.shuffle(ids)
        n_dom = int(len(ids) * dominance)
        for d, chunk in zip(owners_of[t], np.array_split(ids[:n_dom], len(owners_of[t]))):
            parts[d].extend(chunk.tolist())
        for d, chunk in enumerate(np.array_split(ids[n_dom:], k)):
            parts[d].extend(chunk.tolist())
    normal_ids = np.where(np.isin(y_multi, list(BENIGN)))[0]; rng.shuffle(normal_ids)
    for d, chunk in enumerate(np.array_split(normal_ids, k)):
        parts[d].extend(chunk.tolist())
    return [np.sort(np.array(p)) for p in parts]

# byzantine.py imported `partition` by name; patch its reference
_orig_partition = byzantine.partition

def run(part_fn, X, yb, ym, Xt, yt, K, seed, attack, n_att):
    byzantine.partition = part_fn
    try:
        return byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid", seed=seed,
                                       attack=attack, n_att=n_att, aggregator="lpra", lpra_version="v2")
    finally:
        byzantine.partition = _orig_partition

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    out = []
    for K in (5, 10, 20, 50):
        for seed in (42, 43, 44):
            for attack, n_att in (("none", 0), ("scale", 1)):
                a = run(_orig_partition,     X, yb, ym, Xt, yt, K, seed, attack, n_att)
                b = run(partition_no_orphans, X, yb, ym, Xt, yt, K, seed, attack, n_att)
                row = dict(K=K, seed=seed, attack=attack,
                           orig=dict(f1=round(a["mean_last3_f1"],4), hon=a["honest_rejections"], att=a["attacker_rejections"]),
                           fixed=dict(f1=round(b["mean_last3_f1"],4), hon=b["honest_rejections"], att=b["attacker_rejections"]))
                out.append(row)
                print(f"K={K:2} seed={seed} {attack:5}  ORIG F1={row['orig']['f1']:.4f} hon_rej={row['orig']['hon']:3} att_rej={row['orig']['att']:2}"
                      f"   |   FIXED F1={row['fixed']['f1']:.4f} hon_rej={row['fixed']['hon']:3} att_rej={row['fixed']['att']:2}", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_partition_fix.json"), "w"), indent=1)
    print("\nwrote compare_partition_fix.json")
