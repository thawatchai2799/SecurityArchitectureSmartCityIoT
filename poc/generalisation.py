"""
generalisation.py
-----------------
Two experiments that answer the reviewer question "are the ~0.99 scores real?":

Exp-7  Leave-one-attack-family-out (LOAO).  Train the edge model on normal + all
       attack families except one, then measure recall on the *unseen* family.
       This is the closest thing to a zero-day test a labelled dataset allows and is
       far harder than a random split.  Also reports normal-traffic FPR of that model.

Exp-8  Feature-importance ablation.  Rank native features by permutation-free
       tree importance, then re-train after removing the top-1, top-3, top-5, top-10
       features.  If F1 stays high the detector relies on many weak signals (good);
       if it collapses, one artefact feature was doing all the work (leakage warning).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, recall_score
from sklearn.model_selection import train_test_split


def leave_one_attack_out(X, y_bin, y_multi, seed=42, model_fn=None):
    model_fn = model_fn or (lambda: DecisionTreeClassifier(max_depth=8, random_state=seed))
    fams = sorted(set(y_multi) - {"normal"})
    normal = np.where(y_multi == "normal")[0]
    rng = np.random.default_rng(seed); rng.shuffle(normal)
    n_tr, n_te = normal[: int(0.7 * len(normal))], normal[int(0.7 * len(normal)):]
    rows = []
    for held in fams:
        tr = np.concatenate([n_tr, np.where((y_multi != "normal") & (y_multi != held))[0]])
        te_att = np.where(y_multi == held)[0]
        m = model_fn().fit(X[tr], y_bin[tr])
        rec_unseen = recall_score(np.ones(len(te_att)), m.predict(X[te_att]))
        fpr = m.predict(X[n_te]).mean()
        rows.append(dict(held_out_family=held, n_unseen=int(len(te_att)),
                         recall_on_unseen=float(rec_unseen), fpr_normal=float(fpr)))
    return rows


def feature_ablation(X_df: pd.DataFrame, y_bin, seed=42, ks=(0, 1, 3, 5, 10, 20)):
    X = X_df.values.astype(np.float32); cols = list(X_df.columns)
    tr, te = train_test_split(np.arange(len(y_bin)), test_size=0.3, stratify=y_bin, random_state=seed)
    rf = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=seed, n_jobs=1).fit(X[tr], y_bin[tr])
    order = np.argsort(rf.feature_importances_)[::-1]
    ranking = [dict(feature=cols[i], importance=float(rf.feature_importances_[i])) for i in order[:15]]
    rows = []
    for k in ks:
        keep = order[k:]
        m = DecisionTreeClassifier(max_depth=8, random_state=seed).fit(X[tr][:, keep], y_bin[tr])
        pred = m.predict(X[te][:, keep])
        rows.append(dict(removed_top_k=k, n_features=int(len(keep)), f1=float(f1_score(y_bin[te], pred)),
                         removed=[cols[i] for i in order[:k]]))
    return dict(ranking=ranking, ablation=rows)


def tree_rules(X_df, y_bin, y_multi, seed=42, depth=8, top_n=12):
    """Extract the most-populated leaves of the edge decision tree as human-readable
    rules.  Used for the explainability paragraph and Supplementary Table S5, so that
    the manuscript never hard-codes a rule that the model no longer uses."""
    from collections import Counter
    X = X_df.values.astype(np.float32); cols = list(X_df.columns)
    tr, te = train_test_split(np.arange(len(y_bin)), test_size=0.3, stratify=y_multi, random_state=seed)
    m = DecisionTreeClassifier(max_depth=depth, random_state=seed).fit(X[tr], y_bin[tr])
    tree = m.tree_
    parent = {}
    stack = [0]
    while stack:
        n = stack.pop()
        for child, side in ((tree.children_left[n], "<="), (tree.children_right[n], ">")):
            if child != -1:
                parent[child] = (n, side); stack.append(child)

    def path(node):
        conds, n = [], node
        while n != 0:
            par, side = parent[n]
            conds.append(f"{cols[tree.feature[par]]} {side} {tree.threshold[par]:.3g}")
            n = par
        return list(reversed(conds))

    leaf_of = m.apply(X[te]); counts = Counter(leaf_of)
    n_attack_test = int(y_bin[te].sum())
    rows = []
    for lf, c in counts.most_common(top_n):
        v = tree.value[lf][0]; pred = int(np.argmax(v))
        sub = y_multi[te][leaf_of == lf]
        top = ", ".join(f"{k}" for k, _ in Counter(sub).most_common(2))
        rows.append(dict(test_flows=int(c), prediction="ATTACK" if pred else "normal",
                         purity=float(v[pred] / v.sum()), dominant_types=top,
                         rule=" AND ".join(path(lf))))
    att = [r for r in rows if r["prediction"] == "ATTACK"]
    return dict(n_leaves=int(m.get_n_leaves()), depth=int(m.get_depth()),
                n_attack_test=n_attack_test,
                top_attack_leaf_share=(att[0]["test_flows"] / max(n_attack_test, 1)) if att else 0.0,
                top_attack_rule=att[0]["rule"] if att else "", leaves=rows)
