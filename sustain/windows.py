"""
windows.py
----------
Chronological *windows* of CIC-IDS2017 for the operational-sustainability study.

The previous article (Chomsiri & Phunsa 2026, E14) evaluated per capture day (two held-out days). The question
asked here -- how often must a detector be re-trained, and what does each re-training cost --
needs a finer clock. The MachineLearningCVE release carries no timestamp column, but the rows
of each per-day file are written in capture order: the attack families appear in the file in
exactly the order of the published capture schedule (Wednesday: slowloris -> Slowhttptest ->
Hulk -> GoldenEye -> Heartbleed; Tuesday: FTP-Patator -> SSH-Patator; Thursday morning:
Brute Force -> XSS -> SQL Injection), which we verified on the released files before relying on
it (tools/verify_row_order.py). We therefore cut every capture day into `windows_per_day`
consecutive blocks of equal flow count. With 8 blocks per day a window is roughly one hour of
the 09:00-17:00 capture; we call them "windows", not hours, because they are equal in flows,
not in wall-clock time.

Sampling: `sample_per_file` rows are drawn at random from each file (seed-controlled, the same
protocol and default as E14) and then *restored to file order*, so that sampling thins the
stream without reordering it.

Districts: the same non-IID partition as the federated experiments of the article
(poc.federated.partition): each attack family has owner districts that receive 70 % of its
flows, benign traffic is spread evenly. The partition is drawn once over the whole week, so a
district keeps its traffic profile across windows -- the Transport district is still the
Transport district on Friday.
"""
from __future__ import annotations
import os
import re
import glob
import numpy as np
import pandas as pd

from poc.federated import partition, DISTRICTS

# chronological file order of the MachineLearningCVE release
FILE_ORDER = [
    ("monday",    "Monday-WorkingHours.pcap_ISCX.csv"),
    ("tuesday",   "Tuesday-WorkingHours.pcap_ISCX.csv"),
    ("wednesday", "Wednesday-workingHours.pcap_ISCX.csv"),
    ("thursday",  "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv"),
    ("thursday",  "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv"),
    ("friday",    "Friday-WorkingHours-Morning.pcap_ISCX.csv"),
    ("friday",    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv"),
    ("friday",    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv"),
]
DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]
DROP = ["Flow ID", "Source IP", "Destination IP", "Source Port", "Destination Port",
        "Timestamp", "Protocol"]


def _read_file(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, low_memory=False, skipinitialspace=True, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, low_memory=False, skipinitialspace=True, encoding="latin-1")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _row_counts(cicids_dir: str) -> dict:
    out = {}
    for _, fname in FILE_ORDER:
        with open(os.path.join(cicids_dir, fname), "rb") as f:
            out[fname] = sum(1 for _ in f) - 1
    return out


def load_windows(cicids_dir: str, sample_per_day: int | None = 160000, windows_per_day: int = 8,
                 seed: int = 42, k: int = 5, verbose: bool = True) -> dict:
    """Return dict(X, y, ytype, day, win, district, feats, meta).

    `sample_per_day` flows are drawn per capture day, allocated to that day's files in proportion
    to their size, so every window of the week holds the same number of flows
    (sample_per_day / windows_per_day) and per-window costs are directly comparable."""
    rng = np.random.default_rng(seed)
    counts = _row_counts(cicids_dir)
    day_tot = {d: sum(counts[f] for dd, f in FILE_ORDER if dd == d) for d in DAY_ORDER}
    frames = []
    for day, fname in FILE_ORDER:
        path = os.path.join(cicids_dir, fname)
        if not os.path.exists(path):
            hits = glob.glob(os.path.join(cicids_dir, fname.split("-")[0] + "*"))
            raise FileNotFoundError(f"{fname} not found in {cicids_dir} (found {hits})")
        df = _read_file(path)
        n_full = len(df)
        if sample_per_day:
            quota = int(round(sample_per_day * counts[fname] / day_tot[day]))
            if quota < len(df):
                keep = np.sort(rng.choice(len(df), quota, replace=False))   # thin, keep order
                df = df.iloc[keep]
        df = df.reset_index(drop=True)
        df["__day"] = day
        df["__file"] = fname
        frames.append(df)
        if verbose:
            print(f"  {fname:58s} {day:9s} {len(df):>8,} of {n_full:>9,} rows (file order kept)")
    return _finish(pd.concat(frames, ignore_index=True), DAY_ORDER, windows_per_day, seed, k, sample_per_day,
                   "cic2017", verbose)


def _finish(d: pd.DataFrame, day_order: list, windows_per_day: int, seed: int, k: int, sample_per_day,
            dataset: str, verbose: bool) -> dict:
    """Labels, features, equal-count windows inside each day, one non-IID district partition."""
    lab = "Label" if "Label" in d.columns else "label"
    d = d.loc[d[lab].astype(str).str.strip().str.lower() != "label"].reset_index(drop=True)
    y = (d[lab].astype(str).str.strip().str.upper() != "BENIGN").astype(np.int8).values
    ytype = (d[lab].astype(str).str.strip().str.lower()
               .str.replace(r"[^\x20-\x7e]+", "-", regex=True)
               .str.replace(r"\s*-\s*", " - ", regex=True).str.replace(r"\s+", " ", regex=True)).values
    X = (d.drop(columns=[c for c in DROP + DROP_2018 + [lab, "__day", "__file", "__row"] if c in d.columns])
          .apply(pd.to_numeric, errors="coerce")
          .replace([np.inf, -np.inf], np.nan).fillna(0).astype(np.float32))
    feats = list(X.columns)
    X = X.values
    day = d["__day"].values

    # ---- windows: equal-count consecutive blocks inside each day ----------------------------
    win = np.empty(len(d), dtype=np.int16)
    w0 = 0
    for dname in day_order:
        idx = np.where(day == dname)[0]           # already in capture order
        if len(idx) == 0:
            raise ValueError(f"day {dname!r} has no rows after sampling")
        for j, blk in enumerate(np.array_split(idx, windows_per_day)):
            win[blk] = w0 + j
        w0 += windows_per_day
    n_win = w0

    # ---- districts: one non-IID partition over the whole capture ----------------------------
    parts = partition(ytype, k, "non-iid", seed)
    district = np.empty(len(d), dtype=np.int8)
    for i, p in enumerate(parts):
        district[p] = i

    meta = dict(n_rows=int(len(d)), n_feats=len(feats), windows_per_day=windows_per_day,
                n_windows=int(n_win), k=k, seed=seed, sample_per_day=sample_per_day,
                districts=DISTRICTS[:k], dataset=dataset, day_order=list(day_order))
    if verbose:
        print(f"  {len(d):,} rows, {len(feats)} features, {n_win} windows, {k} districts")
    return dict(X=X, y=y, ytype=ytype, day=day, win=win, district=district, feats=feats, meta=meta)


# ------------------------------------------------------------------------------------------------
#  CSE-CIC-IDS2018: ten per-day files with a Timestamp column
# ------------------------------------------------------------------------------------------------
DROP_2018 = ["Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp"]
_DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


def _day_key_2018(fname: str) -> str:
    """'Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv' -> '2018-02-14' (sortable day id)."""
    m = _DATE_RE.search(fname)
    if not m:
        raise ValueError(f"no dd-mm-yyyy date in file name {fname!r}")
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"


def _count_rows(path: str) -> int:
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return max(n - 1, 0)


def _sample_file_chunked(path: str, keep_idx: np.ndarray, chunksize: int = 50000) -> pd.DataFrame:
    """Read only the data rows whose 0-based record index is in keep_idx, in chunks, so a 4 GB file
    never has to fit in memory. Feature columns are converted to float32 as they are read (text
    columns cost ~50x more memory); 'Timestamp' and 'Label' stay text. Blank lines are NOT skipped,
    so record indices equal physical line numbers (what _count_rows counts); the returned frame
    carries the record index in '__row'. Repeated header rows inside the file are dropped by the
    caller (their Label is the word 'Label')."""
    want = np.sort(np.asarray(keep_idx))
    parts, offset, j = [], 0, 0
    reader = pd.read_csv(path, chunksize=chunksize, low_memory=False, skipinitialspace=True,
                         encoding="latin-1", dtype=str, skip_blank_lines=False)
    for chunk in reader:
        n = len(chunk)
        lo, hi = offset, offset + n
        k0 = j
        while j < len(want) and want[j] < hi:
            j += 1
        sel = want[k0:j] - lo
        if len(sel):
            c = chunk.iloc[sel]
            c.columns = [str(x).strip() for x in c.columns]
            keep_text = [x for x in ("Timestamp", "Label") if x in c.columns]
            feat_cols = [x for x in c.columns if x not in keep_text and x not in DROP_2018 and x not in DROP]
            num = c[feat_cols].apply(pd.to_numeric, errors="coerce").astype(np.float32)
            part = pd.concat([c[keep_text].reset_index(drop=True), num.reset_index(drop=True)], axis=1)
            part.insert(0, "__row", want[k0:j])
            parts.append(part)
        offset = hi
        if j >= len(want):
            break
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _parse_timestamps(col: pd.Series) -> pd.Series:
    """'14/02/2018 08:31:01' (the release format); rows that do not match it are given a second,
    lenient day-first parse so that a stray '14/02/2018 8:31:01' is kept rather than dropped."""
    txt = col.astype(str).str.strip()
    ts = pd.to_datetime(txt, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    miss = ts.isna() & txt.ne("") & txt.ne("nan")
    if miss.any():
        ts.loc[miss] = pd.to_datetime(txt[miss], dayfirst=True, errors="coerce", format="mixed")
    return ts


def load_windows_2018(cicids_dir: str, sample_per_day: int | None = 160000, windows_per_day: int = 8,
                      seed: int = 42, k: int = 5, verbose: bool = True, seeds: list | None = None):
    """CSE-CIC-IDS2018 'Processed Traffic Data for ML Algorithms': one CSV per capture day with a
    Timestamp column ('14/02/2018 08:31:01'). Rows are sampled per file (chunked) and then sorted
    by Timestamp inside the day, so the windows follow the clock rather than the file order.
    The Tuesday-20-02 file carries four extra identifier columns; they are dropped with the rest.

    `seeds=[42, 43, ...]` draws the samples of several seeds in ONE pass over each file (the files
    are large) and returns {seed: data}; each seed's sample is identical to a single-seed call."""
    multi = seeds is not None
    seeds = list(seeds) if multi else [seed]
    rngs = {sd: np.random.default_rng(sd) for sd in seeds}
    files = sorted(glob.glob(os.path.join(cicids_dir, "*.csv")), key=lambda p: _day_key_2018(os.path.basename(p)))
    if not files:
        raise FileNotFoundError(f"no CSV files in {cicids_dir}")
    day_order = [_day_key_2018(os.path.basename(p)) for p in files]
    if len(set(day_order)) != len(day_order):
        raise ValueError(f"two files map to the same day: {day_order}")
    frames = {sd: [] for sd in seeds}
    for path, day in zip(files, day_order):
        fname = os.path.basename(path)
        n_full = _count_rows(path)
        n_keep = min(sample_per_day, n_full) if sample_per_day else n_full
        keep = {}
        for sd in seeds:                                   # same draw order as a single-seed call
            keep[sd] = np.sort(rngs[sd].choice(n_full, n_keep, replace=False)) if n_keep < n_full else np.arange(n_full)
        union = np.unique(np.concatenate(list(keep.values())))
        df = _sample_file_chunked(path, union)
        if "Timestamp" not in df.columns or "Label" not in df.columns:
            raise ValueError(f"{fname}: expected 'Timestamp' and 'Label' columns, found {list(df.columns)[:8]}...")
        pos = {int(r): i for i, r in enumerate(df["__row"].values)}   # file record -> position in the frame
        ts_all = _parse_timestamps(df["Timestamp"])
        is_hdr = df["Label"].astype(str).str.strip().str.lower() == "label"
        for sd in seeds:
            rows = np.array([pos[int(r)] for r in keep[sd] if int(r) in pos], dtype=int)
            sub = df.iloc[rows]; ts = ts_all.iloc[rows]; hdr = is_hdr.iloc[rows]
            ok = ts.notna().values & ~hdr.values
            blank = sub["Label"].isna().values | (sub["Label"].astype(str).str.strip() == "").values
            bad = int(((~ts.notna().values) & ~hdr.values & ~blank).sum())      # real rows with no usable time
            skipped = int((hdr.values | blank).sum())
            sub = sub.loc[ok]; ts = ts.loc[ok]
            order = np.argsort(ts.values, kind="stable")                               # clock order
            sub = sub.iloc[order].reset_index(drop=True)
            sub["__day"] = day
            sub["__file"] = fname
            frames[sd].append(sub)
            if verbose and sd == seeds[0]:
                print(f"  {fname:52s} {day} {len(sub):>8,} of {n_full:>10,} rows, sorted by Timestamp"
                      + (f", {skipped} blank/header lines skipped" if skipped else "")
                      + (f", {bad} rows with unparsable timestamps dropped" if bad else "")
                      + (f" (x{len(seeds)} seeds in one pass)" if multi else ""))
    out = {sd: _finish(pd.concat(frames[sd], ignore_index=True), day_order, windows_per_day, sd, k,
                       sample_per_day, "cic2018", verbose) for sd in seeds}
    return out if multi else out[seed]


def load_windows_any(dataset: str, cicids_dir: str, **kw) -> dict:
    if dataset == "cic2017":
        return load_windows(cicids_dir, **kw)
    if dataset == "cic2018":
        return load_windows_2018(cicids_dir, **kw)
    raise ValueError(f"unknown dataset {dataset!r} (cic2017 | cic2018)")


def window_table(data: dict) -> pd.DataFrame:
    """Per-window summary: day, flows, attack share, families present and first seen."""
    rows, seen = [], set()
    for w in range(data["meta"]["n_windows"]):
        m = data["win"] == w
        types = set(data["ytype"][m]) - {"benign"}
        new = sorted(types - seen); seen |= types
        rows.append(dict(window=w, day=data["day"][m][0], flows=int(m.sum()),
                         attack_share=float(data["y"][m].mean()),
                         families=", ".join(sorted(types)), first_seen=", ".join(new)))
    return pd.DataFrame(rows)
