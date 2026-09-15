"""Reviewer 1 Comment 6 points at K=20 (80/200 honest rejections) as where
LPRA misbehaves.  That is also exactly where the two deviations in
screen_updates() could stop being no-ops:

  * with many districts, more clients fail Stage 1, so |S1| can approach
    floor(K/2) and the paper's INCONCLUSIVE branch can fire;
  * when the fallback fires, the released code's global top-(K/2+1) by
    cosine can include a Stage-1 rejection that the paper's S1-restricted
    fallback would exclude.

So the K=5 identity found earlier does not settle Comment 1.  This runs the
scalability grid from Table 13 under both implementations and reports, per
K and seed: F1, honest rejections, attacker rejections, and -- the decisive
number -- how many rounds' accepted sets actually differ between the two.
"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.argv = ["x"]
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_lpra.py")).read().split('if __name__ == "__main__":')[0])

from sklearn.model_selection import train_test_split

# Count rounds where the two implementations accepted a different set, by
# instrumenting the aggregate() the harness swaps in.
_acc_log = {"released": [], "paper": []}

def _wrap(mode, fn):
    def inner(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
        new, acc, info = fn(name, V, ns, gvec, f, lpra_gamma, lpra_version)
        _acc_log[mode].append(tuple(int(x) for x in np.asarray(acc)))
        return new, acc, info
    return inner

def run_logged(mode, **kw):
    _acc_log[mode].clear()
    fn = aggregate_paper if mode == "paper" else _released_aggregate
    byzantine.aggregate = _wrap(mode, fn)
    try:
        r = byzantine.run_byzantine(**kw)
    finally:
        byzantine.aggregate = _released_aggregate
    return r, list(_acc_log[mode])

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    out = []
    # Table 13's grid: K in {5,10,20,50}, one attacker (scale), non-iid.  Seed
    # 42 is the paper's; 43 and 44 added because Reviewer 1 asks for more.
    for K in (5, 10, 20, 50):
        for seed in (42, 43, 44):
            for attack, n_att in (("none", 0), ("scale", 1)):
                res = {}
                for mode in ("released", "paper"):
                    t0 = time.perf_counter()
                    r, accs = run_logged(mode, X=X, y_bin=yb, y_multi=ym, X_test=Xt, y_test=yt,
                                         k=K, rounds=10, regime="non-iid", seed=seed, attack=attack,
                                         n_att=n_att, aggregator="lpra", lpra_version="v2")
                    res[mode] = dict(f1=r["mean_last3_f1"], hon=r["honest_rejections"],
                                     att=r["attacker_rejections"], accs=accs, t=time.perf_counter()-t0)
                diff_rounds = sum(1 for a, b in zip(res["released"]["accs"], res["paper"]["accs"]) if a != b)
                inconcl = sum(1 for a in res["paper"]["accs"] if sum(a) == 0)
                row = dict(K=K, seed=seed, attack=attack,
                           f1_rel=round(res["released"]["f1"], 4), f1_pap=round(res["paper"]["f1"], 4),
                           hon_rel=res["released"]["hon"], hon_pap=res["paper"]["hon"],
                           att_rel=res["released"]["att"], att_pap=res["paper"]["att"],
                           rounds_differ=diff_rounds, inconclusive_rounds=inconcl)
                out.append(row)
                flag = "  <-- DIFFERS" if diff_rounds else ""
                print(f"K={K:2} seed={seed} {attack:5}  F1 rel={row['f1_rel']:.4f} pap={row['f1_pap']:.4f}  "
                      f"hon_rej rel={row['hon_rel']:3} pap={row['hon_pap']:3}  "
                      f"rounds_differ={diff_rounds} inconcl={inconcl}{flag}", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_scalability.json"), "w"), indent=1)
    print("\nwrote compare_scalability.json")
