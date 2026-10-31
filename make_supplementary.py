"""
make_supplementary.py
---------------------
Builds the supplementary tables from a finished results directory:

    S1  the full window schedule (flows, attack share, families present and first seen per window)
    S2  the detection-cost grid for every protocol-policy pair, with per-seed values
    S3  per-window F1, recall and FPR for every replay
    S4  the scaling table (K = 5 ... 100)
    S5  every protocol under every re-training trigger (drift, drift + fallback, ADWIN, KSWIN, DDM, F1-threshold)

Each table is written as CSV under <results>/supplementary/ and all four are collected in one
workbook, <results>/supplementary/Supplementary_Tables.xlsx (one sheet per table).

Usage:
    python3 make_supplementary.py                      # results_sustain/
    SUSTAIN_RESULTS=results_sustain_cic2018 python3 make_supplementary.py
"""
from __future__ import annotations
import glob
import json
import os
import sys

import pandas as pd

RES = os.environ.get("SUSTAIN_RESULTS", "results_sustain")
T = os.path.join(RES, "tables")
OUT = os.path.join(RES, "supplementary")


def main() -> int:
    if not os.path.isdir(T):
        print(f"no tables directory in {RES}; run make_sustain_figures.py first")
        return 1
    os.makedirs(OUT, exist_ok=True)
    sheets: dict[str, pd.DataFrame] = {}

    # ---- S1: window schedule (seed 42, the seed shown in Figure 1) -------------------------------
    wt = pd.read_csv(os.path.join(T, "T_windows.csv"))
    sheets["S1_windows"] = wt

    # ---- S2: detection-cost grid with per-seed values ---------------------------------------------
    per_seed = pd.read_csv(os.path.join(T, "lifecycle_per_seed.csv"))
    keep = ["protocol", "policy", "seed", "stream_f1", "mean_f1", "stream_recall", "stream_fpr",
            "retrains_per_year", "train_cpu_h_per_gw_year", "gb_model_per_gw_year", "gb_raw_per_gw_year",
            "tx_per_year", "kwh_per_gw_year", "kgco2e_per_gw_year", "upkeep_share_of_idle"]
    keep = [c for c in keep if c in per_seed.columns]
    sheets["S2_grid_per_seed"] = per_seed[keep].sort_values(["protocol", "policy", "seed"]).reset_index(drop=True)
    grid = pd.read_csv(os.path.join(T, "T_grid_full.csv"))
    sheets["S2_grid_mean_ci"] = grid

    # ---- S3: per-window metrics of every replay ------------------------------------------------------
    rows = []
    for path in sorted(glob.glob(os.path.join(RES, "replay_*_s*.json"))):
        r = json.load(open(path))
        sm = r["summary"]
        for w in r["per_window"]:
            rows.append(dict(protocol=sm["protocol"], policy=sm["policy"], seed=sm["seed"], window=w["window"],
                             f1=w.get("f1"), recall=w.get("recall"), fpr=w.get("fpr"),
                             attack_share=w.get("attack_share"), retrained_after=w.get("retrained_after")))
    sheets["S3_per_window"] = pd.DataFrame(rows)

    # ---- S5: every protocol under every trigger (the manuscript table shows four protocols) ------
    det = grid[grid.policy.isin(["drift", "drift_fb", "adwin", "kswin", "ddm", "oracle"])] if "policy" in grid.columns else grid.iloc[0:0]
    sheets["S5_triggers_all_protocols"] = det.reset_index(drop=True)

    # ---- S4: scaling with K ------------------------------------------------------------------------------
    sheets["S4_scaling"] = pd.read_csv(os.path.join(T, "T_scaling.csv"))

    for name, df in sheets.items():
        df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
    xlsx = os.path.join(OUT, "Supplementary_Tables.xlsx")
    try:
        with pd.ExcelWriter(xlsx) as xw:
            for name, df in sheets.items():
                df.to_excel(xw, sheet_name=name[:31], index=False)
        print("wrote", xlsx)
    except Exception as e:                      # openpyxl missing: the CSV files are still complete
        print(f"workbook not written ({e}); CSV files are in {OUT}")
    for name, df in sheets.items():
        print(f"  {name}: {len(df)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
