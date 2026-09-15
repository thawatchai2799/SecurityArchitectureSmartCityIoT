"""Reviewer 1, Comment 6(b): partition() assigns the 9 TON_IoT attack
families to districts by (family index mod K).  For K > 9, districts 9..K-1
receive no dominant family -- only the 30% non-dominant remainder of every
family, spread evenly, plus benign traffic.  They are effectively a diluted
IID mix, structurally unlike districts 0..8.

Hypothesis: at K = 20 the ~80 honest rejections per 10 rounds are not
"LPRA rejecting heterogeneous honest clients" in general, but the 9
family-owner districts being rejected round after round, because the 11
orphan districts form the majority and drag the median-based reference
toward the generic mixture.  9 owners x ~9 rounds ~ 80.

Test: log which district indices LPRA rejects each round at K = 10, 20, 50
and count rejections by district class (owner vs orphan).
"""
import os, sys, json, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine
from poc.federated import partition
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

_orig_aggregate = byzantine.aggregate
_rej_log = []

def _logging_aggregate(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
    new, acc, info = _orig_aggregate(name, V, ns, gvec, f, lpra_gamma, lpra_version)
    _rej_log.append([i for i in range(len(acc)) if not acc[i]])
    return new, acc, info

byzantine.aggregate = _logging_aggregate

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]
    types = sorted(set(ym) - {"normal", "benign", "benigntraffic"})

    out = []
    for K in (10, 20, 50):
        owners = sorted({i % K for i in range(len(types))})
        orphans = [d for d in range(K) if d not in owners]
        for seed in (42, 43, 44):
            _rej_log.clear()
            r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid", seed=seed,
                                        attack="none", n_att=0, aggregator="lpra", lpra_version="v2")
            per_district = np.zeros(K, int)
            for rej in _rej_log:
                for d in rej: per_district[d] += 1
            owner_rej = int(per_district[owners].sum()); orphan_rej = int(per_district[orphans].sum())
            row = dict(K=K, seed=seed, n_owner=len(owners), n_orphan=len(orphans),
                       total_rej=int(per_district.sum()), owner_rej=owner_rej, orphan_rej=orphan_rej,
                       owner_rej_rate=round(owner_rej / (len(owners) * 10), 3),
                       orphan_rej_rate=round(orphan_rej / max(len(orphans) * 10, 1), 3),
                       per_district=per_district.tolist(), f1=round(r["mean_last3_f1"], 4))
            out.append(row)
            print(f"K={K:2} seed={seed}  total_rej={row['total_rej']:3}  "
                  f"owners({len(owners)}) rejected {owner_rej:3} [{row['owner_rej_rate']:.0%} of their rounds]  "
                  f"orphans({len(orphans)}) rejected {orphan_rej:3} [{row['orphan_rej_rate']:.0%}]", flush=True)
        print(f"     per-district rejections (seed 42): {out[-3]['per_district']}")
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rejection_by_district_class.json"), "w"), indent=1)
    print("\nwrote rejection_by_district_class.json")
