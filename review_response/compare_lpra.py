"""Quantify Reviewer 1, Comment 1: does the released screen_updates() differ in
outcome from Algorithm 1 as printed, and on which experiments?

Two deviations are confirmed by reading poc/robust_fl.py against the
manuscript's Algorithm 1 step (6):

  (a) The majority fallback ranks cosine over ALL clients and accepts the
      global top floor(K/2)+1, so a client rejected by the Stage-1 magnitude
      test can be readmitted.  The paper says the fallback selects from S1
      only and that "a client rejected at stage 1 is never readmitted."

  (b) The paper's INCONCLUSIVE branch (|S1| <= floor(K/2): do not aggregate,
      keep w_g, anchor the round as INCONCLUSIVE) is absent; the code forces
      at least one client in instead.

This harness implements the algorithm exactly as printed and runs both
versions on the same seeds, partitions and attacks, so the difference in
reported numbers is measured rather than argued about.
"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from poc import robust_fl, byzantine
from poc.data_loader import load_ton_iot

# ---------------------------------------------------------------------------
# Algorithm 1 as printed, step by step.
# ---------------------------------------------------------------------------
def screen_updates_paper(client_vecs, global_vec, tau=3.0, gamma=2.5, c_min=0.2, version="v2"):
    K = len(client_vecs)
    med = np.median(client_vecs, axis=0)
    d = np.linalg.norm(client_vecs - med, axis=1)
    mad = 1.4826 * np.median(np.abs(d - np.median(d))) + 1e-9
    thr = max(np.median(d) + tau * mad, gamma * np.median(d))
    S1 = d <= thr                                            # stage 1 survivors
    deltas = client_vecs - global_vec

    # Paper: |S1| <= floor(K/2) -> INCONCLUSIVE, no aggregation this round.
    if S1.sum() <= K // 2:
        return None, dict(dist=d.tolist(), cos=[None] * K, threshold=float(thr),
                          version=version, inconclusive=True)

    ref = (deltas[S1].mean(axis=0) if version == "v1" else np.median(deltas[S1], axis=0))
    cos = np.array([float(np.dot(x, ref) / (np.linalg.norm(x) * np.linalg.norm(ref) + 1e-12))
                    for x in deltas])
    A = S1 & (cos >= c_min)

    # Paper step (6): fallback selects the floor(K/2)+1 highest-cosine clients
    # OF S1 -- never readmitting a stage-1 rejection.
    if version != "v1" and A.sum() <= K // 2:
        s1_idx = np.where(S1)[0]
        order = s1_idx[np.argsort(-cos[s1_idx])]
        A = np.zeros(K, dtype=bool)
        A[order[:K // 2 + 1]] = True
    return A, dict(dist=d.tolist(), cos=cos.tolist(), threshold=float(thr),
                   version=version, inconclusive=False)


# ---------------------------------------------------------------------------
# The released aggregate() calls screen_updates and assumes it returns a mask.
# Wrap it so an INCONCLUSIVE round keeps w_g (aggregates nothing).
# ---------------------------------------------------------------------------
_released_screen = robust_fl.screen_updates
_released_aggregate = byzantine.aggregate

def aggregate_paper(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
    if name != "lpra":
        return _released_aggregate(name, V, ns, gvec, f, lpra_gamma, lpra_version)
    acc, stats = screen_updates_paper(V, gvec, gamma=lpra_gamma, version=lpra_version)
    if acc is None:                                  # INCONCLUSIVE: keep w_g
        return gvec.copy(), np.zeros(len(V), dtype=bool), stats
    w = ns * acc; w = w / w.sum()
    return (w[:, None] * V).sum(axis=0), acc, stats


def run(mode, **kw):
    """mode='released' uses the repository as shipped; 'paper' uses Algorithm 1."""
    if mode == "paper":
        byzantine.aggregate = aggregate_paper
    else:
        byzantine.aggregate = _released_aggregate
    try:
        r = byzantine.run_byzantine(**kw)
    finally:
        byzantine.aggregate = _released_aggregate
    return r


if __name__ == "__main__":
    print("loading TON_IoT ...", flush=True)
    # Replicate run_advanced.py part_adaptive exactly: 60k sample, 70/30
    # stratified split on the multi-class label, seed 42.
    from sklearn.model_selection import train_test_split
    ton = load_ton_iot(sample=60000)
    Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
    X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]
    print(f"  train {len(X)}  test {len(Xt)}", flush=True)

    # The conditions Reviewer 1 says are affected: the adaptive attack that the
    # v2 repair was built on (2 attackers, strength 6), plus the no-attack case
    # that the paper's "loses nothing when there is no attack" claim rests on.
    conds = [
        dict(label="no attack",              attack="none",     n_att=0, strength=2.0, direction="orthogonal"),
        dict(label="adaptive s=6 opposite",  attack="adaptive", n_att=2, strength=6.0, direction="opposite"),
        dict(label="adaptive s=6 orthogonal",attack="adaptive", n_att=2, strength=6.0, direction="orthogonal"),
        dict(label="adaptive s=3 opposite",  attack="adaptive", n_att=2, strength=3.0, direction="opposite"),
        dict(label="scale x1 attacker",      attack="scale",    n_att=1, strength=2.0, direction="orthogonal"),
    ]
    seeds = [42, 43, 44]
    out = []
    for c in conds:
        for seed in seeds:
            row = dict(cond=c["label"], seed=seed)
            for mode in ("released", "paper"):
                t0 = time.perf_counter()
                r = run(mode, X=X, y_bin=yb, y_multi=ym, X_test=Xt, y_test=yt, k=5, rounds=10, regime="non-iid",
                        seed=seed, attack=c["attack"], n_att=c["n_att"], aggregator="lpra",
                        strength=c["strength"], direction=c["direction"], lpra_version="v2")
                row[mode] = dict(f1=round(r["mean_last3_f1"], 4),
                                 att_rej=r["attacker_rejections"], hon_rej=r["honest_rejections"],
                                 caught=r["rounds_all_attackers_rejected"])
                print(f"  {c['label']:28} seed {seed}  {mode:8}  F1={row[mode]['f1']:.4f}  "
                      f"att_rej={row[mode]['att_rej']} hon_rej={row[mode]['hon_rej']} caught={row[mode]['caught']}  "
                      f"({time.perf_counter()-t0:.0f}s)", flush=True)
            out.append(row)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_released_vs_paper.json"), "w"), indent=1)
    print("\nwrote compare_released_vs_paper.json")
