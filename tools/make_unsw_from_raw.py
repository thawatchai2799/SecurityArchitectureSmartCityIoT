#!/usr/bin/env python3
"""
make_unsw_from_raw.py -- build data/UNSW_NB15_training-set.csv from the RAW UNSW-NB15
release (UNSW-NB15_1.csv ... _4.csv), which has 49 columns and NO header row.

Usage
  python tools/make_unsw_from_raw.py "C:/path/to/UNSW_NB15/UNSW-NB15_*.csv" [--sample 200000]

What it does
  * assigns the official column names (NUSW-NB15_features.csv order);
  * drops the identifier columns srcip/sport/dstip/dsport and the timestamps Stime/Ltime
    (bias-aware schema, as in the paper);
  * normalises attack_cat: blank -> "normal", strips stray spaces, merges the known spelling
    variants ("Backdoors"->"backdoor", "Fuzzers "->"fuzzers");
  * renames Spkts/Dpkts/Label to the names the loader expects (spkts/dpkts/label);
  * writes a stratified-ish sample (proportional per file) to data/UNSW_NB15_training-set.csv.
"""
import sys, os, glob
import pandas as pd

COLS = ["srcip","sport","dstip","dsport","proto","state","dur","sbytes","dbytes","sttl","dttl",
        "sloss","dloss","service","sload","dload","spkts","dpkts","swin","dwin","stcpb","dtcpb",
        "smeansz","dmeansz","trans_depth","res_bdy_len","sjit","djit","stime","ltime","sintpkt",
        "dintpkt","tcprtt","synack","ackdat","is_sm_ips_ports","ct_state_ttl","ct_flw_http_mthd",
        "is_ftp_login","ct_ftp_cmd","ct_srv_src","ct_srv_dst","ct_dst_ltm","ct_src_ltm",
        "ct_src_dport_ltm","ct_dst_sport_ltm","ct_dst_src_ltm","attack_cat","label"]
DROP = ["srcip","sport","dstip","dsport","stime","ltime"]      # identifiers / timestamps
FIX = {"backdoors": "backdoor", "": "normal", "nan": "normal", "none": "normal"}


def main(argv):
    args = list(argv); sample = 200000
    if "--sample" in args:
        i = args.index("--sample"); sample = int(args[i + 1]); del args[i:i + 2]
    if not args:
        print(__doc__); return 1
    files = []
    for pat in args:
        hits = sorted(glob.glob(pat))
        files.extend(hits if hits else ([pat] if os.path.exists(pat) else []))
    files = [f for f in files if "features" not in os.path.basename(f).lower()]
    if not files:
        print("ERROR: no raw UNSW-NB15 files matched."); return 2
    per_file = max(1, sample // len(files))
    frames = []
    for f in files:
        df = pd.read_csv(f, header=None, names=COLS, low_memory=False,
                         encoding="latin-1", on_bad_lines="skip")
        if len(df) > per_file:
            df = df.sample(n=per_file, random_state=42)
        frames.append(df)
        print(f"  {os.path.basename(f):24s} {len(df):>8,} rows kept")
    d = pd.concat(frames, ignore_index=True)
    d = d.drop(columns=[c for c in DROP if c in d.columns])
    ac = d["attack_cat"].astype(str).str.strip().str.lower()
    ac = ac.where(~ac.isin(["", "nan", "none", "na"]), "normal")
    d["attack_cat"] = ac.replace(FIX)
    # a raw row can be labelled 0 (normal) yet carry a stale attack_cat, and vice versa
    d.loc[pd.to_numeric(d["label"], errors="coerce").fillna(0) == 0, "attack_cat"] = "normal"
    d["label"] = pd.to_numeric(d["label"], errors="coerce").fillna(0).astype(int)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                       "UNSW_NB15_training-set.csv")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    d.to_csv(out, index=False, encoding="utf-8")
    print(f"-> {out}: {len(d):,} rows, {d.shape[1]} columns")
    print("   attack ratio:", round(d.label.mean(), 3))
    print("   classes:", d.attack_cat.value_counts().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
