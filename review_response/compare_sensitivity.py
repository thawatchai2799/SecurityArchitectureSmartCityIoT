"""Corrected joint sensitivity sweep for Reviewer 1, Comment 4(c).

A first attempt passed c_min to run_byzantine(), which does not accept it --
screen_updates() was called with its default c_min=0.2 throughout, so the
"sweep" varied nothing and produced identical rows.  This version patches
screen_updates directly so c_min is actually varied, and sweeps it jointly
with gamma, under no attack and under a direction-based attack where the
cosine test is the binding constraint.
"""
import os, sys, json, functools
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine, robust_fl
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

_orig_screen = robust_fl.screen_updates

def patched(c_min):
    @functools.wraps(_orig_screen)
    def inner(client_vecs, global_vec, tau=3.0, gamma=2.5, c_min_ignored=0.2, version="v2"):
        return _orig_screen(client_vecs, global_vec, tau=tau, gamma=gamma, c_min=c_min, version=version)
    return inner

def sweep(X, yb, ym, Xt, yt, attack, n_att, c_min, gamma, seeds=(42, 43, 44)):
    byzantine.screen_updates = patched(c_min)
    try:
        f1s, hon, att = [], 0, 0
        for seed in seeds:
            r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=5, rounds=10, regime="non-iid",
                                        seed=seed, attack=attack, n_att=n_att, aggregator="lpra",
                                        lpra_version="v2", lpra_gamma=gamma,
                                        strength=6.0, direction="opposite")
            f1s.append(r["mean_last3_f1"]); hon += r["honest_rejections"]; att += r["attacker_rejections"]
        return float(np.mean(f1s)), hon, att
    finally:
        byzantine.screen_updates = _orig_screen

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    out = []
    for label, attack, n_att, denom_h, denom_a in (
            ("no attack",          "none",     0, 150, 0),
            ("adaptive s=6 opp.",  "adaptive", 2,  90, 60)):
        print(f"\n=== {label} ===")
        print(f"  {'c_min':>6} {'gamma':>6}   {'F1':>7}  {'hon_rej':>9}  {'att_rej':>9}")
        for c_min in (0.0, 0.1, 0.2, 0.4, 0.6, 0.8):
            for gamma in (1.5, 2.5, 4.0):
                f1, hon, att = sweep(X, yb, ym, Xt, yt, attack, n_att, c_min, gamma)
                out.append(dict(regime=label, c_min=c_min, gamma=gamma, f1=round(f1, 4),
                                hon=hon, att=att, hon_denom=denom_h, att_denom=denom_a))
                a = f"{att:3}/{denom_a}" if denom_a else "   n/a"
                print(f"  {c_min:6.1f} {gamma:6.1f}   {f1:.4f}  {hon:4}/{denom_h}  {a}", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "threshold_sensitivity.json"), "w"), indent=1)
    print("\nwrote threshold_sensitivity.json")
