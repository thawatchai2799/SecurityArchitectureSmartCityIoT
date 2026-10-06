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
| `table13_flame_k20_50.py` | FLAME added to the Table 13 grid at K = 20 and 50 (Table S11); per-round HDBSCAN cluster log; `--lam` | authors, pre-resubmission; re-run in round 2 |
| `flame_impl.py` | FLAME after its Algorithm 1 (round 2): cosine on the models, HDBSCAN ⌊K/2⌋+1 / min_samples 1 / single cluster, median-norm clipping, equal-weight mean, noise σ = λ·S_t seeded from the previous global model; `install(byzantine, lam)` | R1 round 2, C2 |
| `flame_cluster_property.py` | with FLAME's HDBSCAN settings the admitted set is exactly ⌊K/2⌋+1 even for near-identical models (scikit-learn and `hdbscan` agree) | R1 round 2, C2 |
| `table13_attacker_placement.py` | Table 13 with the Byzantine set varied (E20, Table S12): all five placements at K = 5, fixed + four random at K = 10/20/50; `--summarise-only` | R1 round 2, C3 |
| `fk_boundary_sweep.py` | Byzantine fraction at fixed K (E21, Table S13): K = 9, 11; f = 2–6; four attacks; v2 and v1 | R3 round 2, point 3 |
| `e11_commit_latency_repeats.json` | four repeats of `run_extended.py --part D` (E11 commit latency) | R1 round 2, C1 |
| `../fabric/bench/decode_blockfile.py` | byte-level composition of the E13 ledger (E22, Table S14) → `../fabric/blockfile_composition.json` | R3 round 2, point 4 |

`compare_flame.py` and `table13_flame_k20_50.py` use `flame_impl.py` (round 2): FLAME's Algorithm 1 with
λ = 0.01, FLAME's NIDS value; `--lam` writes `*_lam<λ>.json` and the untagged files are the λ = 0.01 run.
Two earlier runs are kept and superseded: `*_sklearn_defaults.json` (scikit-learn's HDBSCAN defaults, which
cannot return the single majority cluster FLAME relies on) and `*_v2.1.0.json` (cosine distance on the
updates W−G rather than the models, λ = 0.001, noise seeded from a call counter — the run behind the
first revision's statement that FLAME excluded only some of the scaled attackers, now withdrawn).
`compare_ledger_latency.py` is an auxiliary saturated-mempool benchmark of the emulated ledger, not the
E11 measurement; E11's own commit latency is in `results/extD_scenario.json` (round 2, C1).
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
6-8) under the released code so that the effect of each initialisation change on
the K = 5 tables is known rather than assumed; the round-2 run (bootstrap drawn
from district 0's training split, no overlap with its hold-out) is the committed
file and the v2.1 run is kept as `exp3_exp9_rerun_v2.1.0.json`.

Every JSON in this folder was regenerated on 2026-09-20 under the v2.1 code
(district-local initialisation); the round-2 files (FLAME, placement, f/K sweep,
E11 repeats, `exp3_exp9_rerun.json`) on 2026-10-05 under v2.2.0 (`MANIFEST.md`
lists which file is canonical for each table).  The first runs of `compare_independent_attacks.py`,
`compare_sensitivity.py`, `compare_krum.py`, `compare_loao.py` and
`compare_flame.py` had used the pooled initialisation; the numbers that moved
are listed in CHANGELOG v2.1.  The RESPONSE_*_draft.md files of v2.0 are
superseded by the response letter and removed.
