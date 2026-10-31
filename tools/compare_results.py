#!/usr/bin/env python3
"""
compare_results.py -- compare two results folders replay by replay.

    python tools/compare_results.py results_sustain results_reference

Detection, traffic and transaction figures are deterministic for a given seed and must agree exactly
(differences at the 1e-12 level come from CSV rounding); CPU-seconds are machine-dependent and are
reported as a ratio. A replay present in only one folder, or produced with different settings, is listed.
"""
import os, sys, json, glob
import numpy as np
import pandas as pd

EXACT = ["stream_f1", "mean_f1", "stream_recall", "stream_fpr", "n_retrain", "bytes_up", "bytes_down",
         "raw_bytes", "tx", "fl_rounds", "quarantined", "missed_attacks", "false_alarms"]
SETTINGS = ["sample_per_day", "windows_per_day", "w_init", "rounds", "local_epochs", "delta", "dataset"]


def load(folder):
    rows = {}
    for p in glob.glob(os.path.join(folder, "replay_*_s*.json")):
        r = json.load(open(p))
        s, a = r["summary"], r.get("args", {})
        key = (s["protocol"], s["policy"], int(s["seed"]))
        rows[key] = dict(s, **{"_" + k: a.get(k, "cic2017" if k == "dataset" else None) for k in SETTINGS})
    return rows


def main(a, b):
    A, B = load(a), load(b)
    common = sorted(set(A) & set(B))
    print(f"{a}: {len(A)} replays | {b}: {len(B)} replays | common: {len(common)}")
    for k in sorted(set(A) ^ set(B)):
        print("  only in", a if k in A else b, ":", k)
    diff_settings = [k for k in common if any(A[k]["_" + s] != B[k]["_" + s] for s in SETTINGS)]
    for k in diff_settings:
        print("  different settings:", k, {s: (A[k]["_" + s], B[k]["_" + s]) for s in SETTINGS if A[k]["_" + s] != B[k]["_" + s]})
    same = [k for k in common if k not in diff_settings]
    if not same:
        print("nothing comparable"); return 1
    da = pd.DataFrame([A[k] for k in same]); db = pd.DataFrame([B[k] for k in same])
    ok = True
    for c in EXACT:
        d = float((da[c].astype(float) - db[c].astype(float)).abs().max())
        flag = "ok" if d < 1e-9 else "DIFFERS"
        ok &= d < 1e-9
        print(f"  {c:15s} max |diff| = {d:.3g}  {flag}")
    ratio = (da["retrain_cpu_s"] / db["retrain_cpu_s"]).replace([np.inf, -np.inf], np.nan).dropna()
    if len(ratio):
        print(f"  retrain CPU-seconds, {a} / {b}: median {ratio.median():.2f} (machine-dependent, not compared)")
    print("RESULT:", "identical detection/traffic/transaction figures" if ok else "DIFFERENCES FOUND")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
