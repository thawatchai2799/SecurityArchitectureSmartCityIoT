"""
edge_ids.py
-----------
Layer 2 of the architecture: a lightweight Intrusion Detection System that is
meant to run on a resource-constrained *district gateway* (Raspberry-Pi class).

We benchmark several model families and measure what a deployment paper needs:
    - detection quality  : accuracy, precision, recall, F1, ROC-AUC, FPR
    - resource footprint : training time, model size (pickled bytes),
                           per-flow inference latency (micro-seconds), throughput
Everything is measured on the same machine so *relative* numbers are meaningful.
"""
from __future__ import annotations
import io
import pickle
import time
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix)


def model_zoo(seed: int = 42):
    """Models ordered from lightest to heaviest.  All are edge-deployable."""
    return {
        "LogReg": Pipeline([("sc", StandardScaler()),
                            ("clf", LogisticRegression(max_iter=500, random_state=seed))]),
        "DecisionTree(d=8)": DecisionTreeClassifier(max_depth=8, random_state=seed),
        "RandomForest(20x8)": RandomForestClassifier(n_estimators=20, max_depth=8,
                                                     n_jobs=1, random_state=seed),
        "MLP(32,16)": Pipeline([("sc", StandardScaler()),
                                ("clf", MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=60,
                                                      early_stopping=True, random_state=seed))]),
    }


def _model_size_bytes(model) -> int:
    buf = io.BytesIO(); pickle.dump(model, buf); return buf.getbuffer().nbytes


def _inference_latency(model, X, n_single: int = 300, batch: int = 4096):
    """Per-flow latency (single-sample predict, worst case for the edge) and
    batch throughput (flows/s)."""
    Xs = X[:n_single]
    t0 = time.perf_counter()
    for i in range(len(Xs)):
        model.predict(Xs[i:i + 1])
    single_us = (time.perf_counter() - t0) / len(Xs) * 1e6
    Xb = X[:batch]
    t0 = time.perf_counter(); model.predict(Xb); dt = time.perf_counter() - t0
    return single_us, len(Xb) / dt


def evaluate(model, X_train, y_train, X_test, y_test, name: str = "") -> dict:
    X_train = np.asarray(X_train, dtype=np.float32); X_test = np.asarray(X_test, dtype=np.float32)
    t0 = time.perf_counter(); model.fit(X_train, y_train); train_s = time.perf_counter() - t0
    y_pred = model.predict(X_test)
    try:
        y_score = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_score)
    except Exception:
        auc = float("nan")
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
    single_us, tput = _inference_latency(model, X_test)
    return dict(model=name, accuracy=accuracy_score(y_test, y_pred),
                precision=precision_score(y_test, y_pred, zero_division=0),
                recall=recall_score(y_test, y_pred, zero_division=0),
                f1=f1_score(y_test, y_pred, zero_division=0), roc_auc=auc,
                fpr=fp / max(fp + tn, 1), fnr=fn / max(fn + tp, 1),
                train_time_s=train_s, model_size_kb=_model_size_bytes(model) / 1024,
                latency_us_per_flow=single_us, throughput_flows_per_s=tput,
                n_train=len(y_train), n_test=len(y_test), n_features=X_train.shape[1])


def benchmark(X_train, y_train, X_test, y_test, seed: int = 42, models: dict | None = None):
    models = models or model_zoo(seed)
    return [evaluate(m, X_train, y_train, X_test, y_test, name) for name, m in models.items()]
