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
| `compare_tamper.py` | five tamper attacks incl. truncation and quorum re-signing | R3 4 |
| `compare_flame.py` | FLAME baseline beside LPRA and FedAvg | R3 2 |

`screen_updates_corrected.py` is the Algorithm-1-faithful function that now
lives in `poc/robust_fl.py`; it is kept here so the diff against the released
version is one file.

`table13_definitive.json` is Table 13 regenerated from the corrected code and
is the source of the numbers in the revised manuscript.
