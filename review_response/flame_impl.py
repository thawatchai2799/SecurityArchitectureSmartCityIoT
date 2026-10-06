"""FLAME aggregation (Nguyen et al., USENIX Security 2022), Algorithm 1, shared by
compare_flame.py (K = 5) and table13_flame_k20_50.py (K = 20, 50).

Line 6   c_ij = 1 - cos(W_i, W_j) on the submitted LOCAL MODELS W_i themselves
         (v2.1.0 clustered the updates W_i - G_{t-1} instead; cosine distance is not
         invariant to that translation -- round 2, Reviewer 1, C2(a)).
Line 7   HDBSCAN on the precomputed distances, min_cluster_size = n/2 + 1 (floor(K/2)+1),
         min_samples = 1, a single cluster allowed; the admitted set L is the largest
         cluster (all clients if HDBSCAN returns no cluster).
Line 8-9 e_i = ||W_i - G_{t-1}||_2, S_t = median over ALL n clients.
Line 10-11 W^c_i = G_{t-1} + (W_i - G_{t-1}) * min(1, S_t / e_i) for the admitted models.
Line 12  G_t = mean over L of W^c_i (equal weights).
Line 13-14 sigma = lambda * S_t, G*_t = G_t + N(0, sigma^2), fresh noise every round.

lambda.  FLAME derives lambda = (1/eps) * sqrt(2 ln(1.25/delta)) from a per-scenario privacy
budget and used lambda = 0.001 for image classification and word prediction and
lambda = 0.01 for its network-intrusion-detection scenario.  The paper's task is NIDS, so
0.01 is the default here; compare_flame.py --lam runs the sensitivity {0.001, 0.01, 0.1}
(round 2, Reviewer 1, C2(b)-(c)).  v2.1.0 used 0.001.
"""
import hashlib
import numpy as np
from sklearn.cluster import HDBSCAN

LAMBDA_DEFAULT = 0.01
CLUSTER_LOG = []   # one entry per FLAME aggregation round


def flame(V, ns, gvec, lam=LAMBDA_DEFAULT):
    K = len(V)
    wn = np.linalg.norm(V, axis=1) + 1e-12
    cos_dist = 1.0 - (V @ V.T) / np.outer(wn, wn)                 # line 6: on W_i, not on W_i - G
    np.fill_diagonal(cos_dist, 0.0); cos_dist = np.clip(cos_dist, 0.0, 2.0)
    labels = HDBSCAN(min_cluster_size=max(2, K // 2 + 1), min_samples=1, allow_single_cluster=True,
                     metric="precomputed").fit(cos_dist).labels_   # line 7
    if (labels >= 0).sum() == 0:
        keep = np.ones(K, bool)
    else:
        big = np.bincount(labels[labels >= 0]).argmax(); keep = labels == big
    deltas = V - gvec
    e = np.linalg.norm(deltas, axis=1) + 1e-12                    # line 8
    S_t = float(np.median(e))                                      # line 9: median over all n
    clipped = np.array([gvec + d * min(1.0, S_t / ei) for d, ei in zip(deltas, e)])   # lines 10-11
    agg = clipped[keep].mean(axis=0)                               # line 12: equal weights over L
    # Noise seeded from the previous global model, so a cell is reproducible on its own
    # (v2.1.0 seeded from a global call counter, which made a single cell depend on how
    # many FLAME rounds had run before it in the same process).
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(gvec.astype(np.float64).tobytes()).digest()[:8], "little"))
    agg = agg + rng.normal(0.0, lam * S_t, size=agg.shape)         # lines 13-14
    CLUSTER_LOG.append(dict(K=int(K), n_clusters=int(len(set(labels[labels >= 0]))), kept=int(keep.sum()),
                            kept_ids=[int(i) for i in np.where(keep)[0]], S_t=S_t,
                            max_cos_dist=float(cos_dist.max())))
    return agg, keep, dict(kept=int(keep.sum()))


def install(byzantine_module, lam=LAMBDA_DEFAULT):
    """Route aggregator name 'flame' to flame() with the given lambda."""
    orig = byzantine_module.aggregate
    if getattr(byzantine_module, "_flame_orig_aggregate", None) is None:
        byzantine_module._flame_orig_aggregate = orig
    base = byzantine_module._flame_orig_aggregate

    def aggregate_with_flame(name, V, ns, gvec, f, lpra_gamma=2.5, lpra_version="v2"):
        if name == "flame":
            return flame(V, ns, gvec, lam=lam)
        return base(name, V, ns, gvec, f, lpra_gamma, lpra_version)
    byzantine_module.aggregate = aggregate_with_flame
    return aggregate_with_flame
