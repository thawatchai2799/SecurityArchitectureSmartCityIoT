#!/usr/bin/env python3
"""
verify_row_order.py -- are the rows of the MachineLearningCVE files in capture order?

The release has no timestamp column, so the chronological windows of sustain/windows.py rest on
row order. This script prints, per file and per attack family, the row positions (min / 5th /
50th / 95th percentile / max) at which the family occurs. If the families occupy nearly disjoint
row ranges in the order of the published capture schedule, row order is capture order.

    python tools/verify_row_order.py /path/to/MachineLearningCVE
"""
import sys, os, glob
import numpy as np
import pandas as pd

SCHEDULE = {   # published CIC-IDS2017 attack schedule (Sharafaldin et al. 2018), local time
    "Tuesday": ["FTP-Patator 09:20-10:20", "SSH-Patator 14:00-15:00"],
    "Wednesday": ["DoS slowloris 09:47-10:10", "DoS Slowhttptest 10:14-10:35", "DoS Hulk 10:43-11:00",
                  "DoS GoldenEye 11:10-11:23", "Heartbleed 15:12-15:32"],
    "Thursday-Morning": ["Web Attack Brute Force 09:20-10:00", "Web Attack XSS 10:15-10:35",
                         "Web Attack Sql Injection 10:40-10:42"],
    "Thursday-Afternoon": ["Infiltration 14:19-15:45"],
    "Friday-Morning": ["Bot 10:02-11:02"], "Friday-PortScan": ["PortScan 13:55-15:29"],
    "Friday-DDos": ["DDoS 15:56-16:16"],
}


def main(d):
    for f in sorted(glob.glob(os.path.join(d, "*.csv"))):
        df = pd.read_csv(f, usecols=lambda c: c.strip() == "Label", skipinitialspace=True, encoding="latin-1")
        lab = df.iloc[:, 0].astype(str).str.strip()
        n = len(lab)
        print(f"== {os.path.basename(f)}  n={n:,}")
        for L in lab.unique():
            if L == "BENIGN":
                continue
            idx = np.where(lab.values == L)[0]
            q = np.percentile(idx, [0, 5, 50, 95, 100]).astype(int)
            print(f"   {L.encode('ascii', 'replace').decode():30s} n={len(idx):>7}  row p0/p5/p50/p95/p100 = "
                  f"{q.tolist()}  ({q[1]/n:.2f}..{q[3]/n:.2f} of file)")
    print("\nPublished schedule for comparison:")
    for k, v in SCHEDULE.items():
        print(f"   {k:20s} {' -> '.join(v)}")


if __name__ == "__main__":
    main(sys.argv[1])
