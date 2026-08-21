"""
temporal.py
-----------
Chronological evaluation, the question a random split cannot answer: how does a detector that was
trained on the traffic of one period behave on the traffic of the next?

CIC-IDS2017 is captured over five consecutive working days and released as one CSV per day, so it
supports a genuine temporal protocol without any extra data:

    static      train once on the first `n_train` days, then test on each later day separately.
                This is the "deploy and forget" model.
    rolling     before testing day d, re-train on every day up to d-1.
                This is the "keep learning" model that the federated layer implements.

The gap between the two curves is the value of continuous re-training, measured rather than asserted.

Note for the paper: later days also contain attack families that the earlier days do not (the capture
introduces web attacks and infiltration on Thursday, botnet/port-scan/DDoS on Friday). That is not a
confound to be removed — it is what temporal deployment actually looks like, and it is stated as such.
"""
from __future__ import annotations
import os
import re
import glob
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, confusion_matrix

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]
DROP = ["Flow ID", "Source IP", "Destination IP", "Source Port", "Destination Port",
        "Timestamp", "Protocol"]


def _day_of(path: str) -> str | None:
    b = os.path.basename(path).lower()
    for d in DAY_ORDER:
        if d in b:
            return d
    return None


def load_by_day(pattern: str, sample_per_file: int | None = 120000, seed: int = 42) -> pd.DataFrame:
    """Read the per-day CIC-IDS2017 CSVs and return one frame with a `__day` column."""
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"no CIC-IDS2017 day files matched {pattern!r}. Point --cicids-dir at the folder that "
            f"contains Monday-WorkingHours.pcap_ISCX.csv etc.")
    frames = []
    for f in files:
        day = _day_of(f)
        if day is None:
            print(f"  skipping {os.path.basename(f)} (no weekday in the file name)")
            continue
        try:
            df = pd.read_csv(f, low_memory=False, skipinitialspace=True, encoding="utf-8-sig")
        except UnicodeDecodeError:                       # some CIC releases are latin-1 encoded
            df = pd.read_csv(f, low_memory=False, skipinitialspace=True, encoding="latin-1")
        df.columns = [str(c).strip() for c in df.columns]
        if sample_per_file and len(df) > sample_per_file:
            df = df.sample(n=sample_per_file, random_state=seed)
        df["__day"] = day
        # the capture is released with several files per day (morning / afternoon); keep the order
        df["__file"] = os.path.basename(f)
        frames.append(df)
        print(f"  {os.path.basename(f):58s} {day:9s} {len(df):>8,} rows")
    d = pd.concat(frames, ignore_index=True)
    lab = "Label" if "Label" in d.columns else "label"
    d = d.loc[d[lab].astype(str).str.strip().str.lower() != "label"].reset_index(drop=True)
    d["__y"] = (d[lab].astype(str).str.strip().str.upper() != "BENIGN").astype(int)
    # CIC labels contain a non-ASCII dash ("Web Attack \x96 XSS"); normalise it so the class names
    # are readable in the paper and identical across releases
    d["__type"] = (d[lab].astype(str).str.strip().str.lower()
                     .str.replace(r"[^\x20-\x7e]+", "-", regex=True)
                     .str.replace(r"\s*-\s*", " - ", regex=True).str.replace(r"\s+", " ", regex=True))
    X = (d.drop(columns=[c for c in DROP + [lab, "__day", "__file", "__y", "__type"] if c in d.columns])
          .apply(pd.to_numeric, errors="coerce")
          .replace([np.inf, -np.inf], np.nan).fillna(0).astype(np.float32))
    out = X.copy()
    out["__day"] = d["__day"]; out["__y"] = d["__y"]; out["__type"] = d["__type"]
    return out


def _model(kind: str, seed: int):
    if kind == "dt":
        return DecisionTreeClassifier(max_depth=8, random_state=seed)
    return RandomForestClassifier(n_estimators=20, max_depth=8, n_jobs=1, random_state=seed)


def _score(m, X, y):
    p = m.predict(X)
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    return dict(f1=float(f1_score(y, p, zero_division=0)),
                precision=float(precision_score(y, p, zero_division=0)),
                recall=float(recall_score(y, p, zero_division=0)),
                fpr=float(fp / max(fp + tn, 1)), n=int(len(y)),
                attack_ratio=float(np.mean(y)))


def run_temporal(df: pd.DataFrame, n_train_days: int = 3, kind: str = "dt", seed: int = 42):
    """Return per-day results for the static and rolling protocols, plus a random-split control."""
    days = [d for d in DAY_ORDER if d in set(df["__day"])]
    if len(days) < n_train_days + 1:
        raise ValueError(f"need at least {n_train_days + 1} days, found {days}")
    feats = [c for c in df.columns if not c.startswith("__")]
    Xall, yall = df[feats].values, df["__y"].values
    day_idx = {d: np.where(df["__day"].values == d)[0] for d in days}

    # ---- control: random split over the whole week (what a random-split paper reports) ---------
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(yall)); cut = int(0.7 * len(perm))
    m = _model(kind, seed).fit(Xall[perm[:cut]], yall[perm[:cut]])
    control = _score(m, Xall[perm[cut:]], yall[perm[cut:]])

    # ---- static: train once on the first n_train_days ----------------------------------------
    tr = np.concatenate([day_idx[d] for d in days[:n_train_days]])
    static_model = _model(kind, seed).fit(Xall[tr], yall[tr])
    rows = []
    for d in days:
        s = _score(static_model, Xall[day_idx[d]], yall[day_idx[d]])
        s.update(day=d, protocol="static", in_training=d in days[:n_train_days])
        rows.append(s)

    # ---- rolling: before testing day d, re-train on everything before it ----------------------
    for i, d in enumerate(days):
        if i < n_train_days:
            continue
        tr_i = np.concatenate([day_idx[x] for x in days[:i]])
        mi = _model(kind, seed).fit(Xall[tr_i], yall[tr_i])
        s = _score(mi, Xall[day_idx[d]], yall[day_idx[d]])
        s.update(day=d, protocol="rolling", in_training=False, train_days=i)
        rows.append(s)

    # ---- what is new on each test day (reported, not hidden) ---------------------------------
    seen = set()
    novelty = {}
    for i, d in enumerate(days):
        types = set(df.loc[df["__day"] == d, "__type"]) - {"benign"}
        novelty[d] = sorted(types - seen)
        seen |= types
    return dict(days=days, n_train_days=n_train_days, model=kind, control=control,
                rows=rows, novel_types=novelty)
