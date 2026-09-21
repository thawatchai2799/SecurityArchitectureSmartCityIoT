# review_response/

Comparison harnesses and their outputs from the peer-review revision.  Each
script re-runs a reported experiment under the released code and under the
corrected code (or a baseline the reviewers asked for), on the shipped
TON_IoT data, so the effect of each fix on the paper's numbers is measured.
Every script writes its JSON next to itself; the committed JSONs are the runs
cited in the response to reviewers.

Run from this directory with the repository's Python environment.  All use
the 60,000-flow sample and 70/30 stratified split of `run_advanced.py`.

| script | question | reviewer |
|---|---|---|
| `compare_lpra.py` | released `screen_updates` vs Algorithm 1 as printed, K=5 adaptive sweep | R1 C1 |
| `compare_scale.py` | same, on the K in {5,10,20,50} grid, counting rounds whose accepted set differs | R1 C1 |
| `compare_init.py` | pooled vs district-only vs 2-example initialisation | R1 C3 |
| `compare_partition.py` | which districts LPRA rejects at K>9, owner vs orphan | R1 C6 |
| `compare_partition_fix.py` | original vs orphan-free partition, full grid | R1 C6 |
| `compare_krum.py` | Krum in and out of n > 2f+2; honest-"rejection" incomparability | R1 C5 |
| `compare_ledger_latency.py` | submission vs commit latency on the emulated ledger | R1 C2c |
| `compare_independent_attacks.py` | four attacks not used in LPRA v2's development | R1 C4 |
| `compare_sensitivity.py` | joint c_min x gamma sweep, no attack and under attack | R1 C4c |
| `compare_loao.py` | leave-one-family-out: DT-central vs MLP-central vs MLP-federated | R1 C7, R3 3 |
| `table13_perseed.py` | Table 13 (20% Byzantine, K in {5,10,20,50}) with every per-seed value kept | R1 C6 |
| `exp3_exp9_rerun.py` | Exp-3 and Exp-9 (Tables 6–8) under the v2.1 code, to measure the initialisation change | R1 C3 |
| `compare_tamper.py` | five tamper attacks incl. truncation and quorum re-signing | R3 4 |
| `compare_flame.py` | FLAME baseline beside LPRA and FedAvg | R3 2 |
| `table13_flame_k20_50.py` | FLAME added to the Table 13 grid at K = 20 and 50 (Table S11); per-round HDBSCAN cluster log | authors, pre-resubmission |

`compare_flame.py` and `table13_flame_k20_50.py` run HDBSCAN with FLAME's own settings (min_samples = 1,
single cluster allowed). Their first runs used scikit-learn's defaults, which cannot return the single
majority cluster FLAME relies on; those outputs are kept as `*_sklearn_defaults.json` and are superseded.
`compare_scale.py` uses 20% Byzantine districts (n_att = K // 5) as Table 13 does; its first run used one
attacker at every K and is kept as `compare_scalability_one_attacker.json`.

`screen_updates_corrected.py` is the Algorithm-1-faithful function that now
lives in `poc/robust_fl.py`; it is kept here so the diff against the released
version is one file.

`table13_perseed.json` (`table13_perseed.py`) is Table 13 -- K in {5, 10, 20, 50},
20% Byzantine under scale, FedAvg and LPRA v2, seeds 42-44 -- with every
per-seed value kept; `results/extC_districts_scaling.csv` is its summary and
the source of the numbers in the revised manuscript (F1 = mean of the last
three rounds; s.d. = population s.d. over the three seeds).  An earlier file
named `table13_definitive.json` was a one-attacker run and is withdrawn.

`exp3_exp9_rerun.json` (`exp3_exp9_rerun.py`) re-runs Exp-3 and Exp-9 (Tables
6-8) under the v2.1 code so that the effect of the initialisation change on
the K = 5 tables is known rather than assumed.

Every JSON in this folder was regenerated on 2026-09-20 under the v2.1 code
(district-local initialisation).  The first runs of `compare_independent_attacks.py`,
`compare_sensitivity.py`, `compare_krum.py`, `compare_loao.py` and
`compare_flame.py` had used the pooled initialisation; the numbers that moved
are listed in CHANGELOG v2.1.  The RESPONSE_*_draft.md files of v2.0 are
superseded by the response letter and removed.
