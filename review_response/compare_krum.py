"""Reviewer 1, Comment 5(a)/(b) -- corrected version.

The earlier run tested Krum in and out of regime under the SCALE attack, but
the 0.677 +- 0.456 instability the paper reports (Table 9) is under FLIP with
two attackers.  This runs both attacks so the in-regime claim is supported
for the attack that actually showed the instability.

Krum's condition is n > 2f + 2; for f = 2 that means K >= 7.  At K = 5
_krum_scores() uses m = n - f - 2 = 1 nearest neighbour.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    out = []
    for attack in ("flip", "scale"):
        print(f"\n=== attack = {attack}, f = 2 ===")
        for K in (5, 7, 9):
            for agg in ("krum", "multi_krum", "lpra"):
                f1s, att, hon, caught = [], [], [], []
                for seed in (42, 43, 44):
                    r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid",
                                                seed=seed, attack=attack, n_att=2, aggregator=agg, lpra_version="v2")
                    f1s.append(r["mean_last3_f1"]); att.append(r["attacker_rejections"])
                    hon.append(r["honest_rejections"]); caught.append(r["rounds_all_attackers_rejected"])
                row = dict(K=K, attack=attack, agg=agg, in_regime=bool(K > 6), f1_mean=round(float(np.mean(f1s)), 4),
                           f1_sd=round(float(np.std(f1s)), 4), att_rej=att, hon_rej=hon, caught=caught, honest_n=K - 2)
                out.append(row)
                print(f"  K={K} {agg:11} in-regime={str(row['in_regime']):5}  F1={row['f1_mean']:.4f} \u00b1 {row['f1_sd']:.4f}  "
                      f"att_rej={att}/20  hon_rej={hon}/{(K-2)*10}  caught={caught}/10", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "krum_regime.json"), "w"), indent=1)
    print("\nwrote evidence/krum_regime.json")
