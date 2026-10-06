"""Round 2 (after Reviewer 1, C2): what FLAME's clustering parameters admit when the
models are (near-)identical.

With min_cluster_size = n/2 + 1, min_samples = 1 and a single cluster allowed -- the
parameterisation of FLAME's reference implementation -- HDBSCAN's condensed tree can
never split the root, and the single-cluster labelling admits only the n/2 + 1 densest
points.  So the admitted set is about floor(n/2) + 1 by construction, even when all n
models are the same up to noise; heterogeneity decides WHICH models are dropped, not
HOW MANY.  This script shows that on synthetic inputs with both scikit-learn's HDBSCAN
(used by flame_impl.py) and the `hdbscan` library (used by FLAME's reference code), and
is the evidence behind the sentence in Section 5.3 that FLAME's no-attack cost is a
property of its clustering stage.  Output: flame_cluster_property.json.
"""
import os, json, numpy as np, warnings
warnings.filterwarnings("ignore")
from sklearn.cluster import HDBSCAN as SK
try:
    import hdbscan as HL
except ImportError:
    HL = None

def cos_dist(V):
    n = np.linalg.norm(V, axis=1); D = 1 - (V @ V.T) / np.outer(n, n); np.fill_diagonal(D, 0); return np.clip(D, 0, 2)

def admitted(D, lib):
    K = len(D); kw = dict(min_cluster_size=max(2, K // 2 + 1), min_samples=1, allow_single_cluster=True, metric="precomputed")
    lab = (SK(**kw).fit(D).labels_ if lib == "sklearn" else HL.HDBSCAN(**kw).fit(D.astype(np.float64)).labels_)
    if (lab >= 0).sum() == 0: return K
    return int((lab == np.bincount(lab[lab >= 0]).argmax()).sum())

if __name__ == "__main__":
    rng = np.random.default_rng(0); G = rng.normal(0, 1, 2000); out = []
    def tight(n, s=1e-3): return [G + rng.normal(0, s, 2000) for _ in range(n)]
    def outl(n, s=0.5): return [G + rng.normal(0, s, 2000) for _ in range(n)]
    cases = [("5 near-identical", tight(5)), ("5: 4 tight + 1 outlier", tight(4) + outl(1)),
             ("9 near-identical", tight(9)), ("20 near-identical", tight(20)), ("20: 16 tight + 4 outliers", tight(16) + outl(4)),
             ("50 near-identical", tight(50)), ("50: 40 tight + 10 outliers", tight(40) + outl(10))]
    for name, V in cases:
        V = np.stack(V); D = cos_dist(V); K = len(V)
        row = dict(case=name, n=K, floor=K // 2 + 1, sklearn_admitted=admitted(D, "sklearn"),
                   hdbscan_lib_admitted=(admitted(D, "lib") if HL is not None else None), max_cos_dist=float(D.max()))
        out.append(row); print(row)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "flame_cluster_property.json"), "w"), indent=1)
