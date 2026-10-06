"""Reviewer 3 (round 1), point 2: FLAME as a baseline.  K = 5, three seeds, the attacks of
Table 9 plus the colluding adaptive attacker (s = 6, opposite), FedAvg / FLAME / LPRA v2.

FLAME itself is implemented in flame_impl.py, step for step after Algorithm 1 of
Nguyen et al. (USENIX Security 2022); see that file for the two round-2 corrections
(cosine distance on the local models W_i rather than on the updates W_i - G, and
lambda = 0.01 -- FLAME's own NIDS value -- as the default, with a sensitivity sweep).

Usage:  python compare_flame.py [--lam 0.01]
Output: flame_comparison_lam<lam>.json (+ _clusterlog); with the default lambda the
        same content is also written to flame_comparison.json, the file the
        manuscript's Section 5.3 and Reviewer 3 Point 2 table are built from.
Earlier runs are kept for the record: *_sklearn_defaults.json (HDBSCAN defaults,
first revised submission) and *_v2.1.0.json (cosine on updates, lambda = 0.001).
"""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split
import flame_impl
from flame_impl import CLUSTER_LOG

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--lam", type=float, default=flame_impl.LAMBDA_DEFAULT)
    a = ap.parse_args(); lam = a.lam
    flame_impl.install(byzantine, lam=lam)

    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    conds = [("none", 0, {}), ("scale", 1, {}), ("flip", 1, {}), ("noise", 1, {}), ("stealth", 1, {}),
             ("adaptive", 2, dict(strength=6.0, direction="opposite"))]
    out = []
    print(f"lambda = {lam}")
    print(f"{'attack':10} {'n_att':>5}  {'FedAvg':>7} {'FLAME':>7} {'LPRA':>7}   {'FLAME att_rej':>13} {'LPRA att_rej':>12}")
    for attack, n_att, kw in conds:
        row = dict(attack=attack, n_att=n_att, lam=lam)
        for agg in ("fedavg", "flame", "lpra"):
            f1s, ar, hr, per_seed = [], 0, 0, []
            for seed in (42, 43, 44):
                n0 = len(CLUSTER_LOG)
                r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=5, rounds=10, regime="non-iid", seed=seed,
                                            attack=attack, n_att=n_att, aggregator=agg, lpra_version="v2", **kw)
                f1s.append(r["mean_last3_f1"]); ar += r["attacker_rejections"]; hr += r["honest_rejections"]
                ps = dict(seed=seed, f1=round(float(r["mean_last3_f1"]), 4), final_f1=round(float(r["final_f1"]), 4),
                          att_rej=r["attacker_rejections"], hon_rej=r["honest_rejections"], caught=r["rounds_all_attackers_rejected"])
                if agg == "flame":
                    log = CLUSTER_LOG[n0:]
                    ps["rounds_with_cluster"] = sum(1 for e in log if e["n_clusters"] > 0)
                    ps["kept_per_round"] = [e["kept"] for e in log]
                per_seed.append(ps)
            row[agg] = dict(f1=round(float(np.mean(f1s)), 4), f1_sd=round(float(np.std(f1s)), 4), att_rej=ar, hon_rej=hr, per_seed=per_seed)
            if agg == "flame":
                log = CLUSTER_LOG[-30:]
                row[agg]["rounds_with_cluster"] = sum(1 for e in log if e["n_clusters"] > 0)
                row[agg]["mean_kept"] = round(float(np.mean([e["kept"] for e in log])), 2)
        out.append(row)
        d = 30 * n_att if n_att else 0
        print(f"{attack:10} {n_att:5}  {row['fedavg']['f1']:7.4f} {row['flame']['f1']:7.4f} {row['lpra']['f1']:7.4f}   "
              f"{row['flame']['att_rej']:>6}/{d:<6} {row['lpra']['att_rej']:>5}/{d:<6}  hon: FLAME {row['flame']['hon_rej']} LPRA {row['lpra']['hon_rej']}"
              f"  kept {row['flame']['mean_kept']}", flush=True)
    tag = f"lam{lam:g}"
    json.dump(out, open(os.path.join(HERE, f"flame_comparison_{tag}.json"), "w"), indent=1)
    json.dump(CLUSTER_LOG, open(os.path.join(HERE, f"flame_comparison_clusterlog_{tag}.json"), "w"))
    if abs(lam - flame_impl.LAMBDA_DEFAULT) < 1e-12:
        json.dump(out, open(os.path.join(HERE, "flame_comparison.json"), "w"), indent=1)
        json.dump(CLUSTER_LOG, open(os.path.join(HERE, "flame_comparison_clusterlog.json"), "w"))
    print(f"\nwrote flame_comparison_{tag}.json")
