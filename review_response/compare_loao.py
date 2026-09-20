"""Reviewer 1, Comment 7: E12/E14 fit one centralised DecisionTree and never
run the federated system, so "FedAvg/LPRA under shift" is asserted, not
tested.  CIC-IDS2017 is not shipped with the repository, so the temporal
protocol cannot be re-run here; but the same question -- does the federated
system generalise to a distribution it did not train on? -- can be asked on
the shipped TON_IoT data with leave-one-attack-out, which generalisation.py
already does for the centralised tree.

For each held-out family F:
  centralised   one DecisionTree(max_depth=8) on all other families, as E12
  federated     LPRA v2, K=5, non-iid partition of the other families, the
                paper's actual federated model (MLP 32-16), 10 rounds
Both are tested on F's flows (attack) plus a held-out benign slice, so the
metric is "can the system flag an attack family it never saw."

This tests the federated system under shift, which is what the comment asks
for, on the data that is available.
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc import byzantine
from poc.federated import _make_mlp
from poc.data_loader import load_ton_iot
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, recall_score
from sklearn.model_selection import train_test_split

BENIGN = {"normal", "benign", "benigntraffic"}

if __name__ == "__main__":
    ton = load_ton_iot(sample=60000)
    X, yb, ym = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    fams = sorted(set(ym) - BENIGN)
    rng = np.random.default_rng(42)
    benign_idx = np.where(np.isin(ym, list(BENIGN)))[0]
    b_tr, b_te = train_test_split(benign_idx, test_size=0.3, random_state=42)

    out = []
    print(f"{'held-out family':16} {'n_test':>7}  {'centralised DT':>16}  {'federated LPRA':>16}")
    for F in fams:
        # training pool: every other family + benign train slice
        tr = np.concatenate([np.where((ym != F) & ~np.isin(ym, list(BENIGN)))[0], b_tr])
        te = np.concatenate([np.where(ym == F)[0], b_te])
        rng.shuffle(tr)

        # centralised, as E12
        dt = DecisionTreeClassifier(max_depth=8, random_state=42).fit(X[tr], yb[tr])
        rec_c = recall_score(yb[te], dt.predict(X[te]))          # recall on the unseen family
        f1_c = f1_score(yb[te], dt.predict(X[te]))

        # the same (32,16) MLP the federated layer uses, trained centrally by
        # partial_fit for 31 epochs = 1 bootstrap epoch + 15 rounds x 2 local
        # epochs (the E3 budget); this is the middle column of Table S5, which
        # separates the model-class part of the gap from the federation part
        sc = StandardScaler().fit(X[tr])
        Xs = sc.transform(X[tr]).astype(np.float32); Xte = sc.transform(X[te]).astype(np.float32)
        mlp = _make_mlp(42)
        for _ in range(31):
            mlp.partial_fit(Xs, yb[tr], classes=np.array([0, 1]))
        f1_m = f1_score(yb[te], mlp.predict(Xte))

        # federated: the paper's own system
        r = byzantine.run_byzantine(X[tr], yb[tr], ym[tr], X[te], yb[te], k=5, rounds=10,
                                    regime="non-iid", seed=42, attack="none", n_att=0,
                                    aggregator="lpra", lpra_version="v2")
        f1_f = r["final_f1"]
        # recall specifically on the held-out family requires the model; recompute
        # from the run's final F1 is not enough, so rebuild the scaler+eval path:
        # run_byzantine returns only F1, so we report F1 for both and recall for DT.
        out.append(dict(family=F, n_test=int(len(te)), dt_f1=round(f1_c, 4), dt_recall=round(rec_c, 4),
                        mlp_central_f1=round(float(f1_m), 4), mlp_central_epochs=31, lpra_f1=round(f1_f, 4)))
        print(f"{F:16} {len(te):7}  F1={f1_c:.4f} rec={rec_c:.3f}   MLPc F1={f1_m:.4f}   F1={f1_f:.4f}", flush=True)

    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "loao_federated.json"), "w"), indent=1)
    dt_m = np.mean([o["dt_f1"] for o in out]); ml_m = np.mean([o["mlp_central_f1"] for o in out]); fl_m = np.mean([o["lpra_f1"] for o in out])
    print(f"\nmean F1 on unseen family:  centralised DT {dt_m:.4f}   centralised MLP {ml_m:.4f}   federated LPRA {fl_m:.4f}")
    print("wrote loao_federated.json")
