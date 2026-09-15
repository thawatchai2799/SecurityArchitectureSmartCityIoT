"""Reviewer 1, Comment 5(a) and 5(b).

(a) Table 9 runs Krum with K = 5 and f = 2.  Krum's resilience condition is
    n > 2f + 2, i.e. n >= 7 for f = 2.  At n = 5 the condition fails, and
    the code shows why it is not a formality: _krum_scores uses
    m = n - f - 2 = 1 nearest neighbour, so each client's score is its
    distance to its single closest peer.  Two colluding attackers placing
    identical updates are each other's nearest neighbour at distance ~0 and
    therefore win.  This runs Krum in regime (K = 7, 9 with f = 2) to show
    it is not Krum that fails in Table 9, but Krum used outside its bound.

(b) The "honest rejections" column is not comparable across aggregators.
    LPRA's accepted mask is a quarantine decision.  Krum's is a selection:
    aggregate() marks exactly one client accepted, so K-1 honest clients are
    counted as "rejected" every round by construction, whatever they did.
    This separates the two properties the paper conflates: global-model
    robustness (F1) and malicious-client identification.
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

    print("Krum resilience condition n > 2f + 2:")
    for K in (5, 7, 9):
        print(f"  K={K}, f=2 -> {K} > 6 is {K > 6}   (m = n-f-2 = {K-2-2} nearest neighbours used)")
    print()

    out = []
    for K in (5, 7, 9):
        for seed in (42, 43, 44):
            for agg in ("krum", "multi_krum", "lpra"):
                r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid",
                                            seed=seed, attack="scale", n_att=2, aggregator=agg,
                                            lpra_version="v2")
                # attackers are districts 0..n_att-1; honest are the rest
                honest = K - 2
                row = dict(K=K, seed=seed, agg=agg, in_regime=bool(K > 6),
                           f1=round(r["mean_last3_f1"], 4),
                           att_rej=r["attacker_rejections"], hon_rej=r["honest_rejections"],
                           caught=r["rounds_all_attackers_rejected"],
                           hon_rej_rate=round(r["honest_rejections"] / (honest * 10), 3))
                out.append(row)
                print(f"  K={K} seed={seed} {agg:11} in-regime={str(row['in_regime']):5}  "
                      f"F1={row['f1']:.4f}  attackers_rejected={row['att_rej']:2}/20  "
                      f"honest_'rejected'={row['hon_rej']:3}/{honest*10} ({row['hon_rej_rate']:.0%})  "
                      f"caught={row['caught']}/10", flush=True)
        print()
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "krum_regime.json"), "w"), indent=1)
    print("wrote krum_regime.json")
