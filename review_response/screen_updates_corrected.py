"""screen_updates() brought into exact agreement with Algorithm 1 as printed.

Two deviations from the manuscript were present in the released version and
are corrected here.  Both were confirmed by re-executing the paper's full
scalability grid (K in {5,10,20,50}, three seeds, with and without attack,
240 aggregation rounds) under the released code and under this version:
the accepted set was identical in every round, no INCONCLUSIVE round was
ever reached, and every reported F1 and rejection count is unchanged.  The
correction is therefore a matter of making the code say what the paper
says, not of changing any result.

  (a) Majority fallback.  Released code ranked cosine over all K clients and
      took the global top floor(K/2)+1, which could readmit a client that
      the Stage-1 magnitude test had rejected.  Algorithm 1 step (6) selects
      the floor(K/2)+1 highest-cosine clients *of S1*, so a Stage-1
      rejection is never readmitted.  On the reported grid the two never
      chose differently, because a client far enough from the median to
      fail Stage 1 also has low cosine with the median-based reference and
      never ranks into the top -- but the paper's rule is the stronger
      safety property and is what the code now implements.

  (b) INCONCLUSIVE.  Algorithm 1 says that if |S1| <= floor(K/2) the round
      is not aggregated: w_g is kept and the round is anchored as
      INCONCLUSIVE.  The released code instead forced at least one client
      in.  This branch was never reached on the reported grid (a majority
      always survived Stage 1), so no result depends on it; it is added so
      that the failure mode the paper describes is the failure mode the
      code has.

Return value: (accept_mask, stats).  accept_mask is None when the round is
INCONCLUSIVE; callers must keep the current global model in that case.
"""
import numpy as np


def screen_updates(client_vecs: np.ndarray, global_vec: np.ndarray, tau: float = 3.0, gamma: float = 2.5,
                   c_min: float = 0.2, version: str = "v2"):
    K = len(client_vecs)
    med = np.median(client_vecs, axis=0)
    d = np.linalg.norm(client_vecs - med, axis=1)
    mad = 1.4826 * np.median(np.abs(d - np.median(d))) + 1e-9
    thr = max(np.median(d) + tau * mad, gamma * np.median(d))
    S1 = d <= thr                                             # Stage 1 (magnitude)
    deltas = client_vecs - global_vec

    # Algorithm 1 step (6), second clause: too few Stage-1 survivors to form
    # a majority -> do not aggregate, anchor the round as INCONCLUSIVE.
    if S1.sum() <= K // 2:
        return None, dict(dist=d.tolist(), cos=[None] * K, threshold=float(thr),
                          version=version, inconclusive=True, stage1_survivors=int(S1.sum()))

    ref = (deltas[S1].mean(axis=0) if version == "v1"        # v1: mean reference (kept for E17)
           else np.median(deltas[S1], axis=0))                 # v2: coordinate-wise median
    cos = np.array([float(np.dot(x, ref) / (np.linalg.norm(x) * np.linalg.norm(ref) + 1e-12))
                    for x in deltas])
    accept = S1 & (cos >= c_min)                              # Stage 2 (direction), within S1

    # Algorithm 1 step (6), first clause: the accepted set must be a majority;
    # if not, take the floor(K/2)+1 highest-cosine clients OF S1.  Ranking is
    # restricted to S1 so that a Stage-1 rejection is never readmitted.
    if version != "v1" and accept.sum() <= K // 2:
        s1_idx = np.where(S1)[0]
        order = s1_idx[np.argsort(-cos[s1_idx])]
        accept = np.zeros(K, dtype=bool)
        accept[order[:K // 2 + 1]] = True

    return accept, dict(dist=d.tolist(), cos=cos.tolist(), threshold=float(thr),
                        version=version, inconclusive=False, stage1_survivors=int(S1.sum()))
