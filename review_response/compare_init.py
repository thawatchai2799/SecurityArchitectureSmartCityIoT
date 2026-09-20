"""Reviewer 1, Comment 3: the global model is initialised on a 500-example
class-balanced bootstrap drawn from the POOLED training set, contradicting
"raw training flows never leave the districts."  The docstring of
_bootstrap() says the draw exists only so sklearn's first fit() sees both
classes (partial_fit needs an architecture-establishing fit first).

Does the pooled draw actually help the reported numbers, or is it a
technical convenience?  Three initialisations, same everything else:

  pooled     -- as released: 500 examples from all districts combined
  district0  -- 500 examples from district 0's own partition only.  A
                standard FL bootstrap: one client volunteers initial
                weights; nothing crosses a district boundary.
  minimal    -- 2 examples (one per class) from district 0: just enough to
                establish the MLP, essentially data-free.

If F1 is the same under all three, the pooled draw leaked nothing that the
results depend on, and the fix is to switch the code to district0 and say
so.  If F1 falls, the pooled initialisation was doing real work and must be
disclosed as such.
"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine, federated
from poc.federated import partition
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

_POOL = {"idx": None, "n": 500}
_orig_within = byzantine._bootstrap_within

def _bootstrap_variant(y, idx_pool, rng, n=500):
    """Replaces byzantine._bootstrap_within for the duration of one run.
    'pooled'    -> the submitted behaviour: class-balanced draw over ALL indices
    'district0' -> the v2 behaviour: draw from district 0 only (n = 500)
    'minimal'   -> district 0, two examples (one per class)
    The v2.0 code calls _bootstrap_within(y, parts[0], rng, 500), so patching
    that name is what varies the initialisation; the first version of this
    script (run against the v1.0 code) patched byzantine._bootstrap instead."""
    if _POOL["idx"] is None:                        # pooled
        return byzantine._bootstrap(y, rng, n)
    return _orig_within(y, _POOL["idx"], rng, _POOL["n"])

byzantine._bootstrap_within = _bootstrap_variant

def run(init, X, yb, ym, Xt, yt, K, seed, attack, n_att):
    if init == "pooled":
        _POOL["idx"], _POOL["n"] = None, 500
    else:
        parts = partition(ym, K, "non-iid", seed)
        _POOL["idx"] = parts[0]                     # district 0 only
        _POOL["n"] = 500 if init == "district0" else 2
    return byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid", seed=seed,
                                   attack=attack, n_att=n_att, aggregator="lpra", lpra_version="v2")

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

    out = []
    for K in (5, 10, 20):
        for seed in (42, 43, 44):
            for attack, n_att in (("none", 0), ("scale", 1)):
                row = dict(K=K, seed=seed, attack=attack)
                for init in ("pooled", "district0", "minimal"):
                    r = run(init, X, yb, ym, Xt, yt, K, seed, attack, n_att)
                    row[init] = dict(f1=round(r["mean_last3_f1"], 4), hon=r["honest_rejections"],
                                     att=r["attacker_rejections"], r1=round(r["history"][0]["f1"], 4))
                out.append(row)
                print(f"K={K:2} seed={seed} {attack:5}  "
                      f"pooled={row['pooled']['f1']:.4f}  district0={row['district0']['f1']:.4f}  "
                      f"minimal={row['minimal']['f1']:.4f}   (round-1 F1: "
                      f"{row['pooled']['r1']:.3f}/{row['district0']['r1']:.3f}/{row['minimal']['r1']:.3f})", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_init.json"), "w"), indent=1)
    print("\nwrote compare_init.json")
