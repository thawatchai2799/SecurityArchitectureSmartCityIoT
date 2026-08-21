"""
data_loader.py  (v05)
---------------------
Loads public IDS datasets and maps them onto a *unified, bias-aware* feature
schema so that models can be trained on one dataset and tested on another
(cross-dataset generalisation).

Design decisions (defensible in the paper):
  * IP addresses, port numbers and timestamps are DROPPED.  In testbed data they
    identify the attacker machine and inflate accuracy (Sommer & Paxson 2010;
    Ring et al. 2019; Dharini et al., Sci. Rep. 2026, 16:7763).
  * Three feature views are produced per dataset:
      X_native  - every remaining numeric / flag / one-hot feature of that dataset
      X_common  - 9 *directional* semantic flow features (duration, src/dst bytes,
                  src/dst packets, bytes-per-packet each way, packet ratio, byte ratio)
      X_dirfree - 4 *direction-free* features (duration, total bytes, total packets,
                  bytes per packet).  These are well defined even for datasets that
                  do not separate the two directions (CICIoT2023), so cross-dataset
                  transfer involving such datasets is measured on this view.
  * Every loader validates its expected columns and raises a *readable* error that
    lists what was found, instead of silently producing garbage features.

Supported datasets (drop the CSV in ./data, names as in DATASETS.md):
  ton_iot    : TON_IoT Train_Test_Network.csv  (UNSW Canberra)   <- shipped with the code
  ciciot2023 : CICIoT2023.csv   (merged part files, CIC/UNB)
  cicids2017 : CICIDS2017.csv   (merged MachineLearningCVE, CIC/UNB)
  unsw_nb15  : UNSW_NB15_training-set.csv  (UNSW)
  firewall   : log2.csv         (UCI Internet Firewall Data Set)  -- supplement only
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))

# 9 directional semantic features (used when both directions exist)
COMMON_FEATURES = ["duration", "src_bytes", "dst_bytes", "src_pkts", "dst_pkts",
                   "bytes_per_pkt_src", "bytes_per_pkt_dst", "pkt_ratio", "byte_ratio"]
# 4 direction-free features (defined for every dataset, incl. CICIoT2023)
DIRFREE_FEATURES = ["duration", "tot_bytes", "tot_pkts", "bytes_per_pkt"]

FILES = {"ton_iot": "TON_IoT_Train_Test_Network.csv", "ciciot2023": "CICIoT2023.csv",
         "cicids2017": "CICIDS2017.csv", "unsw_nb15": "UNSW_NB15_training-set.csv",
         "firewall": "log2.csv"}

EPS = 1e-6


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _read(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found.\nSee DATASETS.md for the download link and the exact file "
            f"name expected in {DATA_DIR}.")
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig", skipinitialspace=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _require(df: pd.DataFrame, cols, dataset: str):
    """Fail loudly (and helpfully) instead of silently producing garbage features."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"[{dataset}] missing expected column(s): {missing}\n"
            f"Columns found in the file ({len(df.columns)}): {list(df.columns)}\n"
            f"If your copy of the dataset uses different names, edit the mapping in "
            f"poc/data_loader.py (function load_{dataset}).")


def _num(df: pd.DataFrame, col) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def _drop_repeated_headers(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    """Concatenating CSV parts by hand can leave header rows inside the data."""
    bad = df[label_col].astype(str).str.strip().str.lower().isin({label_col.strip().lower(), "label"})
    return df.loc[~bad].reset_index(drop=True) if bad.any() else df


def _find_col(df: pd.DataFrame, candidates, dataset: str) -> str:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    _require(df, [candidates[0]], dataset)   # raises with a helpful message
    return candidates[0]


def _derive_views(df: pd.DataFrame) -> pd.DataFrame:
    """Requires src_bytes/dst_bytes/src_pkts/dst_pkts/duration to already exist."""
    df["bytes_per_pkt_src"] = df["src_bytes"] / (df["src_pkts"] + EPS)
    df["bytes_per_pkt_dst"] = df["dst_bytes"] / (df["dst_pkts"] + EPS)
    df["pkt_ratio"] = df["src_pkts"] / (df["dst_pkts"] + EPS)
    df["byte_ratio"] = df["src_bytes"] / (df["dst_bytes"] + EPS)
    df["tot_bytes"] = df["src_bytes"] + df["dst_bytes"]
    df["tot_pkts"] = df["src_pkts"] + df["dst_pkts"]
    df["bytes_per_pkt"] = df["tot_bytes"] / (df["tot_pkts"] + EPS)
    return df


def _top_dummies(df: pd.DataFrame, cols, top: int = 20) -> pd.DataFrame:
    """One-hot encode categoricals, keeping only the `top` most frequent levels
    (UNSW-NB15's `proto` alone has >130 levels, most of them singletons)."""
    frames = []
    for c in cols:
        if c not in df.columns:
            continue
        s = df[c].astype(str).str.strip().str.lower()
        keep = s.value_counts().index[:top]
        s = s.where(s.isin(keep), other="__other__")
        frames.append(pd.get_dummies(s, prefix=c, dtype=int))
    return pd.concat(frames, axis=1) if frames else pd.DataFrame(index=df.index)


def _finish(name, df, X_native, y_bin, y_multi, direction_proxy=False, extra=None):
    X_native = X_native.replace([np.inf, -np.inf], 0).fillna(0)
    out = dict(name=name, X_native=X_native,
               X_common=df[COMMON_FEATURES].replace([np.inf, -np.inf], 0).fillna(0).copy(),
               X_dirfree=df[DIRFREE_FEATURES].replace([np.inf, -np.inf], 0).fillna(0).copy(),
               y_bin=np.asarray(y_bin).astype(int), y_multi=np.asarray(y_multi).astype(str),
               direction_proxy=direction_proxy)
    if extra:
        out.update(extra)
    return out


def _maybe_sample(out, sample, seed):
    """Sub-sample every DataFrame in `out` consistently with the label arrays."""
    n = len(out["y_bin"])
    if sample and sample < n:
        rng = np.random.default_rng(seed)
        idx = np.sort(rng.choice(n, sample, replace=False))
        for k, v in list(out.items()):
            if isinstance(v, pd.DataFrame):
                out[k] = v.iloc[idx].reset_index(drop=True)
            elif isinstance(v, np.ndarray) and len(v) == n:
                out[k] = v[idx]
    return out


# --------------------------------------------------------------------------- #
# TON_IoT  (primary IoT dataset, shipped with the code)
# --------------------------------------------------------------------------- #
def load_ton_iot(path: str | None = None, sample: int | None = None, seed: int = 42):
    df = _read(path or os.path.join(DATA_DIR, FILES["ton_iot"]))
    cat_cols = ["proto", "service", "conn_state"]
    num_cols = ["duration", "src_bytes", "dst_bytes", "missed_bytes", "src_pkts",
                "src_ip_bytes", "dst_pkts", "dst_ip_bytes", "dns_qclass", "dns_qtype",
                "dns_rcode", "http_trans_depth", "http_request_body_len",
                "http_response_body_len", "http_status_code"]
    flag_cols = ["dns_AA", "dns_RD", "dns_RA", "dns_rejected", "ssl_resumed",
                 "ssl_established", "weird_notice"]
    _require(df, num_cols + cat_cols + flag_cols + ["label", "type", "ssl_version",
                                                    "http_method", "dns_query"], "ton_iot")
    df = _drop_repeated_headers(df, "label")
    for c in num_cols:
        df[c] = _num(df, c)
    for c in flag_cols:
        df[c] = df[c].astype(str).str.strip().str.upper().map({"T": 1, "F": 0}).fillna(0).astype(int)
    df["has_ssl"] = (df["ssl_version"].astype(str).str.strip() != "-").astype(int)
    df["has_http"] = (df["http_method"].astype(str).str.strip() != "-").astype(int)
    df["has_dns"] = (df["dns_query"].astype(str).str.strip() != "-").astype(int)
    df = _derive_views(df)

    X_native = pd.concat([df[num_cols + flag_cols + ["has_ssl", "has_http", "has_dns"]
                             + COMMON_FEATURES[5:]],
                          pd.get_dummies(df[cat_cols].astype(str), prefix=cat_cols, dtype=int)], axis=1)
    y_bin = _num(df, "label").astype(int).values
    y_multi = df["type"].astype(str).str.strip().str.lower().values
    return _maybe_sample(_finish("TON_IoT", df, X_native, y_bin, y_multi), sample, seed)


# --------------------------------------------------------------------------- #
# CICIoT2023  (per-window packet statistics; NO directional split)
# --------------------------------------------------------------------------- #
def load_ciciot2023(path: str | None = None, sample: int | None = None, seed: int = 42):
    """CICIoT2023 aggregates a window of packets and does not report the two
    directions separately.  We therefore map:
        duration   <- flow_duration
        tot_bytes  <- 'Tot sum'   (sum of packet lengths in the window)
        tot_pkts   <- 'Number'    (packet count of the window)
        bytes/pkt  <- 'Tot size'  (mean packet length)
    and fill the *directional* fields with the aggregate values (src_*) and zeros
    (dst_*) purely so that the 9-feature common view keeps the right shape.  The
    flag direction_proxy=True marks this: cross-dataset experiments that involve
    CICIoT2023 must use X_dirfree, not X_common (run_poc.py enforces this)."""
    df = _read(path or os.path.join(DATA_DIR, FILES["ciciot2023"]))
    lab = _find_col(df, ["label", "Label"], "ciciot2023")
    _require(df, ["flow_duration", "Tot sum", "Number", "Tot size"], "ciciot2023")
    df = _drop_repeated_headers(df, lab)
    df["duration"] = _num(df, "flow_duration")
    df["src_bytes"] = _num(df, "Tot sum")
    df["src_pkts"] = _num(df, "Number").clip(lower=0)
    df["dst_bytes"] = 0.0
    df["dst_pkts"] = 0.0
    df = _derive_views(df)
    mean_size = _num(df, "Tot size")
    df["bytes_per_pkt"] = np.where(mean_size > 0, mean_size, df["tot_bytes"] / (df["tot_pkts"] + EPS))
    label = df[lab].astype(str).str.strip()
    y_bin = (~label.str.lower().str.startswith("benign")).astype(int).values
    y_multi = label.str.split("-").str[0].str.lower().values
    X_native = df.drop(columns=[lab]).select_dtypes(include=[np.number])
    return _maybe_sample(_finish("CICIoT2023", df, X_native, y_bin, y_multi,
                                 direction_proxy=True), sample, seed)


# --------------------------------------------------------------------------- #
# CIC-IDS2017  (MachineLearningCVE merged CSV)
# --------------------------------------------------------------------------- #
def load_cicids2017(path: str | None = None, sample: int | None = None, seed: int = 42):
    df = _read(path or os.path.join(DATA_DIR, FILES["cicids2017"]))
    lab = _find_col(df, ["Label", "label"], "cicids2017")
    _require(df, ["Flow Duration", "Total Length of Fwd Packets", "Total Length of Bwd Packets",
                  "Total Fwd Packets", "Total Backward Packets"], "cicids2017")
    df = _drop_repeated_headers(df, lab)
    df["duration"] = _num(df, "Flow Duration") / 1e6           # microseconds -> seconds
    df["src_bytes"] = _num(df, "Total Length of Fwd Packets")
    df["dst_bytes"] = _num(df, "Total Length of Bwd Packets")
    df["src_pkts"] = _num(df, "Total Fwd Packets")
    df["dst_pkts"] = _num(df, "Total Backward Packets")
    df = _derive_views(df)
    label = df[lab].astype(str).str.strip()
    y_bin = (label.str.upper() != "BENIGN").astype(int).values
    y_multi = label.str.lower().values
    drop = [c for c in ["Flow ID", "Source IP", "Destination IP", "Source Port",
                        "Destination Port", "Timestamp", "Protocol", lab] if c in df.columns]
    X_native = df.drop(columns=drop).select_dtypes(include=[np.number])
    return _maybe_sample(_finish("CIC-IDS2017", df, X_native, y_bin, y_multi), sample, seed)


# --------------------------------------------------------------------------- #
# UNSW-NB15  (training-set CSV)
# --------------------------------------------------------------------------- #
def load_unsw_nb15(path: str | None = None, sample: int | None = None, seed: int = 42):
    df = _read(path or os.path.join(DATA_DIR, FILES["unsw_nb15"]))
    lab = _find_col(df, ["label", "Label"], "unsw_nb15")
    cat = _find_col(df, ["attack_cat", "Attack_cat"], "unsw_nb15")
    _require(df, ["dur", "sbytes", "dbytes", "spkts", "dpkts"], "unsw_nb15")
    df = _drop_repeated_headers(df, lab)
    df["duration"] = _num(df, "dur"); df["src_bytes"] = _num(df, "sbytes")
    df["dst_bytes"] = _num(df, "dbytes"); df["src_pkts"] = _num(df, "spkts")
    df["dst_pkts"] = _num(df, "dpkts")
    df = _derive_views(df)
    y_bin = _num(df, lab).astype(int).values
    y_multi = (df[cat].astype(str).str.strip().str.lower()
                 .replace({"": "normal", "nan": "normal", "none": "normal"}).values)
    num = df.drop(columns=[c for c in ["id", lab, cat] if c in df.columns]).select_dtypes(include=[np.number])
    X_native = pd.concat([num, _top_dummies(df, ["proto", "service", "state"], top=20)], axis=1)
    return _maybe_sample(_finish("UNSW-NB15", df, X_native, y_bin, y_multi), sample, seed)


# --------------------------------------------------------------------------- #
# Internet Firewall Data Set (UCI id 542)  -- supplementary perimeter experiment
# --------------------------------------------------------------------------- #
def load_firewall(path: str | None = None, sample: int | None = None, seed: int = 42):
    df = _read(path or os.path.join(DATA_DIR, FILES["firewall"]))
    need = ["Action", "Bytes", "Bytes Sent", "Bytes Received", "Packets",
            "Elapsed Time (sec)", "pkts_sent", "pkts_received",
            "Destination Port", "NAT Destination Port"]
    _require(df, need, "firewall")
    df = _drop_repeated_headers(df, "Action")
    df["duration"] = _num(df, "Elapsed Time (sec)")
    df["src_bytes"] = _num(df, "Bytes Sent"); df["dst_bytes"] = _num(df, "Bytes Received")
    df["src_pkts"] = _num(df, "pkts_sent"); df["dst_pkts"] = _num(df, "pkts_received")
    df = _derive_views(df)
    action = df["Action"].astype(str).str.lower().str.strip()
    y_bin = (action != "allow").astype(int).values      # 1 = blocked (deny/drop/reset)
    native_cols = ["Bytes", "Bytes Sent", "Bytes Received", "Packets", "Elapsed Time (sec)",
                   "pkts_sent", "pkts_received"] + COMMON_FEATURES[5:]
    for c in native_cols:
        df[c] = _num(df, c)
    X_ports = df[["Destination Port", "NAT Destination Port"] + native_cols].apply(
        pd.to_numeric, errors="coerce").fillna(0)
    return _maybe_sample(_finish("InternetFirewall", df, df[native_cols].copy(), y_bin,
                                 action.values, extra=dict(X_ports=X_ports)), sample, seed)


LOADERS = {"ton_iot": load_ton_iot, "ciciot2023": load_ciciot2023,
           "cicids2017": load_cicids2017, "unsw_nb15": load_unsw_nb15,
           "firewall": load_firewall}


def available_datasets():
    return {k: os.path.exists(os.path.join(DATA_DIR, v)) for k, v in FILES.items()}


if __name__ == "__main__":
    print("data dir:", DATA_DIR)
    print("available:", available_datasets())
    for key, ok in available_datasets().items():
        if not ok:
            continue
        d = LOADERS[key]()
        print(f"{d['name']:16s} rows={len(d['y_bin']):>8,}  native={d['X_native'].shape[1]:>3}  "
              f"attack_ratio={d['y_bin'].mean():.3f}  direction_proxy={d['direction_proxy']}  "
              f"types={len(set(d['y_multi']))}")
