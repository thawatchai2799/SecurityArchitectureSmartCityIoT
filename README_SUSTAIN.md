# Operational-cost study of the deployed detector (`sustain/`)

Experiments on what it costs to keep the intrusion detector of this repository alive on a
chronological stream: re-training policies, CPU time, model traffic, ledger records, and the energy,
carbon and storage they imply per gateway-year. Nothing in `poc/` is changed; the new package imports
the released models, district partition and LPRA screen.

```
run_everything.py         ONE command: windows -> all replays (parallel, resumable) -> tables, figures, facts
sustain/windows.py        CIC-IDS2017 as 40 chronological windows (8 per day), 5 non-IID districts
sustain/chrono.py         replay engine: 6 protocols x 12 re-training policies, cost accounting
sustain/drift.py          ADWIN, KSWIN and DDM (from the original papers; checked against river in tests/)
sustain/lifecycle.py      CPU-s / bytes / tx -> kWh, CO2e, GB per gateway-year; ASSUMPTIONS + SWEEPS
sustain/anchoring.py      per-record vs per-round vs per-event Merkle anchoring (measured Merkle cost)
make_sustain_figures.py   tables, figures, sustain_facts.json (called by run_everything.py)
paper_src/make_sustain_facts.py   formatted manuscript facts (called by run_everything.py)
make_supplementary.py     supplementary tables S1-S4, CSV + one workbook (called by run_everything.py)
run_sustain.py            one seed at a time (the building block run_everything.py parallelises)
tools/verify_row_order.py evidence that the MachineLearningCVE rows are in capture order
```

## Install (Ubuntu / WSL2)

```bash
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv && source .venv/bin/activate
pip install numpy pandas scikit-learn matplotlib tabulate scipy openpyxl   # openpyxl: the supplementary workbook
```

## Run everything

```bash
python run_everything.py --cicids-dir /path/to/MachineLearningCVE
```

That is the whole study: five seeds x 6 protocols x 12 policies = 360 replays, then every table,
figure and `sustain_facts.json`. The console shows, after every finished replay and at least every
30 seconds, the percentage done, the elapsed time, the estimated remaining time and the clock time
at which the run should finish; the same lines go to `results_sustain/run_everything.log`.

- About 3-4 hours with 2 workers (the full-history edge tree dominates); `--workers 4` roughly
  halves it on a machine with 8 or more logical CPUs. Memory: each worker holds one seed's stream
  (about 0.6 GB for the 2017 stream, 1.3 GB for the 2018 stream) plus the tree history it is
  refitting; on a machine with 8 GB use `--workers 2` for the 2018 stream. If WSL2 runs out of
  memory it restarts the whole VM without a message; the run is resumable, so simply run the same
  command again with fewer workers.
- Twelve re-training policies: never, four clock cadences, the alert-rate and feature-mean drift
  triggers, the drift trigger with a one-day clock fallback, the F1-threshold reference policy, and three standard drift detectors used as triggers (ADWIN, KSWIN on the
  feature statistic; DDM on the detector's error stream). `sustain/drift.py` implements the three
  from the original papers; `python3 tests/test_drift.py` checks them against the river library
  (`pip install river`, only needed for the test).
- Resumable: stop it at any time (Ctrl-C) and run the same command again; finished replays are kept
  and only the missing ones run. `--force` re-runs everything.
- `--quick` is a 3-minute smoke test (2 seeds, 16,000 flows per day, 3 protocols x 5 policies)
  that exercises every step including the figures; run it first.
- `--seeds 42 43` limits the seeds; `--results-dir` chooses the output folder.
- Keep the terminal (or a `tmux` session) open: WSL stops background processes when the last
  shell closes.

A smoke test on the data files first, in a few seconds:

```bash
python tools/verify_row_order.py /path/to/MachineLearningCVE
```

## Second stream: CSE-CIC-IDS2018

The same study on the ten-day CSE-CIC-IDS2018 capture (80 windows, first two days for the initial
training). The ten "Processed Traffic Data for ML Algorithms" CSV files (6.9 GB) are on AWS Open Data:

```bash
pip install awscli      # or: sudo apt install awscli
mkdir -p ~/work/cic2018
aws s3 sync --no-sign-request --region ap-southeast-1 "s3://cse-cic-ids2018/Processed Traffic Data for ML Algorithms/" ~/work/cic2018
python run_everything.py --dataset cic2018 --cicids-dir ~/work/cic2018
```

Expect ten files, 6.5 GB in all (sizes as listed on S3): Wednesday-14-02 (342 MB), Thursday-15-02 (359 MB),
Friday-16-02 (319 MB), Thuesday-20-02 (3.8 GB; the misspelling is the release's), Wednesday-21-02 (314 MB),
Thursday-22-02 (365 MB), Friday-23-02 (366 MB), Wednesday-28-02 (200 MB), Thursday-01-03 (103 MB),
Friday-02-03 (337 MB). If S3 is slow from your region, try `--region us-east-1`.

Results go to `results_sustain_cic2018/`. The loader reads each file once for all seeds in chunks
(the Tuesday-20-02 file is 3.8 GB and carries four extra identifier columns, which are dropped),
samples 160,000 flows per day and sorts them by the Timestamp column, so the windows follow the
clock. Expect about 10 minutes of loading and 2.7x the replay time of the 2017 stream (64 held-out
windows instead of 24); use `--workers 2` on an 8 GB machine (see the memory note above).

## Reference results

`results_reference/` holds the authors' replay files, tables and figures for the 2017 stream (and, when
present, `results_reference_cic2018/` for the 2018 stream). They are shipped for comparison only; your own
runs write to `results_sustain*/` and never touch them. To check a run against the reference:

```bash
python tools/compare_results.py results_sustain results_reference
```

## Outputs (results_sustain/)

| File | Content |
|---|---|
| replay_<protocol>_<policy>_s<seed>.json | per-window metrics, per-event costs, summary, machine stamp |
| summary.csv | one row per replay (rebuilt from the JSON files) |
| window_table_s<seed>.csv | window schedule: day, flows, attack share, families, first seen |
| tables/T_grid.csv, T_grid_full.csv | detection x cost grid, mean +/- 95 % CI over seeds |
| tables/T_scaling.csv | per-city-year energy, CO2e, ledger growth vs K |
| tables/T_anchoring.csv | anchoring granularity comparison |
| tables/T_sensitivity.csv | one-at-a-time sweep of every assumption |
| figures/figS1..figS5 | figures, PNG 600 dpi + PDF |
| sustain_facts.json, paper_facts_sustain.json | every headline number by name |
| supplementary/S1_windows.csv .. S4_scaling.csv, Supplementary_Tables.xlsx | the supplementary tables (S3 = per-window metrics of every replay) |
| merkle_measure.json | Merkle root/proof/verify timings of the machine that ran the study (reused when tables are rebuilt elsewhere) |
| run_everything.log | the console log of every run |

## Replacing the hardware assumptions after an on-device measurement

Edit `ASSUMPTIONS` in `sustain/lifecycle.py` (`edge_slowdown`, `P_edge_W`, `gateway_idle_W`) and run
`python run_everything.py --cicids-dir ...` again: no replay is repeated (they store CPU-seconds, bytes
and transactions, not energy), only the tables, figures and facts are regenerated.

## Reproducibility notes

- Detection metrics, bytes and transaction counts are deterministic for a given seed and reproduce
  exactly across machines. CPU-seconds are machine-dependent; compare them within one run.
- BLAS is pinned to one thread inside the runner so that CPU-seconds measure the computation and not
  thread spin-up; one replay uses one core.
- Every result file carries the Python version, platform, CPU count and run date of the machine that
  produced it.
