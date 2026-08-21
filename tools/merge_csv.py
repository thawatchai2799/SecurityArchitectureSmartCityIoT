#!/usr/bin/env python3
"""Merge many CSV part files (same header) into one, optionally sub-sampling rows.

Usage
  python tools/merge_csv.py "CICIoT2023_parts/*.csv" data/CICIoT2023.csv --sample 300000
  python tools/merge_csv.py part1.csv part2.csv data/out.csv

Windows note: cmd.exe and PowerShell do NOT expand wildcards, so a pattern such as
*.csv arrives here as literal text.  This script therefore expands globs itself,
which means the quoted form above works identically on Windows, WSL, macOS and Linux.
"""
import sys, os, glob
import pandas as pd

def main(argv):
    args = list(argv); sample = None
    if "--sample" in args:
        i = args.index("--sample"); sample = int(args[i + 1]); del args[i:i + 2]
    if len(args) < 2:
        print(__doc__); return 1
    *patterns, out = args
    parts = []
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if not hits and os.path.exists(pat):
            hits = [pat]
        if not hits:
            print(f"WARNING: no file matches {pat}")
        parts.extend(hits)
    if not parts:
        print("ERROR: no input files found."); return 2
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    per_file = None if not sample else max(1, sample // len(parts))
    frames, total = [], 0
    for pth in parts:
        df = pd.read_csv(pth, low_memory=False)
        if per_file and len(df) > per_file:
            df = df.sample(n=per_file, random_state=42)   # proportional, keeps the class mix
        frames.append(df); total += len(df)
        print(f"  {os.path.basename(pth):45s} {len(df):>9,} rows")
    merged = pd.concat(frames, ignore_index=True)
    merged.to_csv(out, index=False, encoding="utf-8")
    print(f"-> {out}: {len(merged):,} rows, {merged.shape[1]} columns")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
