# A Multi-Layer Security Architecture for Smart-City IoT with Measured Limits

Edge intrusion detection · screened federated learning (LPRA) · permissioned-ledger
model provenance · cloud orchestration — evaluated end to end on real network traffic, with the
limits of each layer stated and measured (v2.1.0; see CHANGELOG.md).

This repository reproduces every number, table and figure in the accompanying article. No special
hardware is required: the full pipeline runs on a laptop in well under an hour. Only the optional
Hyperledger Fabric experiment needs Docker.

```
  L1  real IoT / enterprise flows
  L2  lightweight edge IDS on each district gateway + federated training (LPRA)
  L3  permissioned consortium ledger — alert digests and model versions only
  L4  cloud orchestrator — cross-district correlation, Merkle-proof audit
```

---

## 1. Requirements

| | |
|---|---|
| Python | 3.9 or newer (tested on 3.12) |
| Packages | `numpy`, `pandas`, `scikit-learn`, `matplotlib`, `tabulate` |
| Disk | ~1.5 GB with all datasets |
| Optional | Node.js 18+ (to rebuild the manuscript), Docker (for the Fabric experiment) |

Windows, WSL, Linux and macOS are all supported; the console output is forced to UTF-8 so that Windows
code pages do not break a run.

## 2. Install

**Windows (PowerShell)**

```powershell
git clone https://github.com/thawatchai2799/SecurityArchitectureSmartCityIoT.git
cd SecurityArchitectureSmartCityIoT
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS / WSL**

```bash
git clone https://github.com/thawatchai2799/SecurityArchitectureSmartCityIoT.git
cd SecurityArchitectureSmartCityIoT
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If PowerShell refuses to activate the environment, run once in that window:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## 3. Datasets

`data/TON_IoT_Train_Test_Network.csv` (211,043 labelled flows) **ships with this repository** — the main
experiments run immediately. Three optional datasets enable the cross-dataset study and the supplement;
put them in `data/` with exactly these names:

| File in `data/` | Source | Needed for |
|---|---|---|
| `TON_IoT_Train_Test_Network.csv` | included | everything (E1–E11) |
| `CICIDS2017.csv` | [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html), `MachineLearningCVE` folder | E12, Table 13, Table 2 |
| `UNSW_NB15_training-set.csv` | [UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset) | E12, Table 13, Table 2 |
| `log2.csv` | [UCI Internet Firewall Data](https://archive.ics.uci.edu/dataset/542/internet+firewall+data) | Supplementary Table S2 |
| `CICIoT2023.csv` *(optional)* | [CICIoT2023](https://www.unb.ca/cic/datasets/iotdataset-2023.html) | adds a row/column to the direction-free matrix |

Any missing file simply skips its experiment; nothing crashes.

### 3.1 Preparing CIC-IDS2017

The release ships eight per-day CSVs. Merge them (quote the pattern — Windows shells do not expand
wildcards, so `tools/merge_csv.py` expands them itself):

```bash
python tools/merge_csv.py "path/to/MachineLearningCVE/*.csv" data/CICIDS2017.csv --sample 300000
```

### 3.2 Preparing UNSW-NB15

If you have `UNSW_NB15_training-set.csv`, copy it into `data/` and skip this step. If you have the **raw**
release (`UNSW-NB15_1.csv` … `_4.csv`, 49 columns, no header row), convert it:

```bash
python tools/make_unsw_from_raw.py "path/to/UNSW_NB15/UNSW-NB15_*.csv" --sample 200000
```

The converter assigns the official column names, drops the identifier columns (`srcip`, `sport`, `dstip`,
`dsport`) and the timestamps, normalises `attack_cat`, and writes `data/UNSW_NB15_training-set.csv`.

### 3.3 Internet Firewall Data (UCI id 542)

The UCI Python API does not serve this dataset, so download the zip:

```bash
curl -sSLO https://archive.ics.uci.edu/static/public/542/internet+firewall+data.zip
unzip -o "internet+firewall+data.zip" -d dl_firewall
cp dl_firewall/log2.csv data/log2.csv
```

## 4. Run the experiments

### Step 1 — preflight (10 seconds, always do this first)

```bash
python check_env.py
```

It verifies the Python version and packages, checks that `results/` is writable, and **actually loads every
dataset present**. A renamed or malformed column is reported with the full list of columns found — far
better than discovering it 15 minutes into a run.

### Step 2 — main experiments

```bash
python run_poc.py
```

≈ 4 minutes with TON_IoT alone, ≈ 12–20 minutes with all datasets. Produces E1, E3, E4, E6, E7, E8, E10 and
E12, writes every CSV/PNG into `results/`, and packs `results_bundle.zip`.

Useful flags: `--quick` (40k-row smoke test, ~1 minute), `--sample N`, `--seed N`.

### Step 3 — extended experiments

```bash
python run_extended.py --part A --seed 42
python run_extended.py --part A --seed 43
python run_extended.py --part A --seed 44
python run_extended.py --part B
python run_extended.py --part C
python run_extended.py --part D
python run_extended.py --part fig
```

≈ 15–25 minutes in total. The parts are independent and resumable — part A checkpoints per seed, so an
interrupted run continues where it stopped. `python run_extended.py` alone runs everything in one go.

> If you re-run part A and it prints `already done, skipping`, delete
> `results/extA_byzantine_grid_raw.csv` first; that file is the checkpoint.

### Step 3b — advanced experiments (E14–E16)

```bash
python run_advanced.py --part R                      # edge CPU, memory and energy accounting
python run_advanced.py --part A --n-att 1            # adaptive attacker sweep, 1 Byzantine district
python run_advanced.py --part A --n-att 2            # ... and 2 colluding districts
python run_advanced.py --part T --cicids-dir "path/to/MachineLearningCVE"   # temporal / drift
```

`--part R` and `--part A` need only TON_IoT (≈ 2 minutes each). `--part T` reads the **per-day**
CIC-IDS2017 files directly — point it at the folder that holds `Monday-WorkingHours.pcap_ISCX.csv`
and friends, not at the merged `data/CICIDS2017.csv`, because the merge discards the day.

### Step 4 — collect the numbers

```bash
python paper_src/make_facts.py
```

Writes `results/paper_facts.json` (~230 numbers and 19 tables) — the single file every manuscript figure
and table is generated from.

## 5. Optional — the Hyperledger Fabric experiment (E13)

Replaces the emulated ledger of layer L3 with a real Fabric v2.5 network. See **`fabric/README.md`** for the full runbook;
`fabric/chaincode/Dockerfile` is what makes chaincode-as-a-service deployment work. Short version, inside WSL/Linux with Docker running:

```bash
./install-fabric.sh --fabric-version 2.5.9 docker samples binary   # one-off
cd ~/fabric-samples/test-network && ./network.sh up createChannel -c mychannel -ca
cp -r /path/to/this/repo/fabric ~/cityanchor
./network.sh deployCCAAS -ccn cityanchor -ccp ~/cityanchor/chaincode
cd ~/cityanchor/bench && npm install
FABRIC_SAMPLES=~/fabric-samples node bench.mjs 2000 20
```

Deployment uses **chaincode-as-a-service**: on Docker Engine 26+ the peer's built-in image builder fails
with `docker image build failed: ... broken pipe`, and CCaaS avoids it by building the image with your own
daemon. Record the results in `fabric/fabric_facts.json` (the file shipped there holds the measurements
reported in the article) and `make_facts.py` will pick them up.

## 6. Optional — rebuild the manuscript

```bash
npm install docx jszip
python paper_src/make_facts.py         # results/*.csv|json  ->  results/paper_facts.json
python paper_src/make_figures.py       # all 10 figures at 600 dpi, PNG + PDF, in results/figures/
node paper_src/make_paper.js           # -> Paper_Draft_SmartCities.docx (MDPI template styles)
node paper_src/make_supp.js            # -> Supplementary_Material.docx + Cover_Letter.docx
python tools/check_wording_v25.py Paper_Draft_SmartCities.docx   # verify the wording fixes held
```

`make_paper.js` calls `paper_src/apply_template_headers.js` automatically after writing the file: the
header and footer parts (running head, page numbers, DOI placeholder, the first-page logo table) are not
styles, so loading `styles.xml` does not carry them — they are instead copied byte-for-byte out of
`paper_src/template/smartcities-template.dot` and spliced into the built document, with integrity checks
that abort the build rather than ship a malformed file (see CHANGELOG CH, CL–CM). If MDPI ships a revised
template, drop the new `.dot` in that folder and rebuild; nothing else needs to change.

`tools/check_wording_v25.py` re-checks, on the built file, every wording and numeric-formatting fix made
since v25 (see CHANGELOG) — run it after every rebuild. It exits non-zero and prints exactly which phrase
is missing or which stale phrase reappeared, so a regression is caught immediately rather than resurfacing
in a later review round.

`make_figures.py` also prints, for every figure, which result file and which table each of its numbers
comes from — run it and read that list if you want to verify that a figure agrees with the text.

The manuscript is built against the official Smart Cities template: `paper_src/template/mdpi_styles.xml` is
loaded verbatim as the document's styles, so the paragraphs carry the real MDPI style names
(`MDPI_1.2_title`, `MDPI_3.1_text`, `MDPI_4.1_table_caption`, …) and the page setup, margins and continuous
line numbering are the template's. Drop a newer template into that folder and rebuild to follow a revision.

Every number in the manuscript — including the ones printed inside Figure 1 — is read from
`results/paper_facts.json`, so the text can never drift away from the experiments. A fact whose experiment
has not been run appears as a highlighted placeholder instead of a stale value.

## 7. Repository layout

```
├── check_env.py                preflight check — run this first
├── run_poc.py                  E1, E3, E4, E6, E7, E8, E10, E12
├── run_extended.py             E2, E5, E9, E11   (--part A|B|C|D|fig)
├── run_advanced.py             E14 temporal, E15 resources/energy, E16 adaptive attacker
├── poc/
│   ├── data_loader.py          bias-aware loaders; native / common-9 / direction-free-4 views
│   ├── edge_ids.py             lightweight IDS zoo + footprint metrics (size, µs/flow, FPR)
│   ├── federated.py            FedAvg, IID and non-IID district partitions
│   ├── robust_fl.py            LPRA: two-stage screen + personalised fine-tuning
│   ├── byzantine.py            LPRA vs FedAvg / Median / Trimmed Mean / Krum / Multi-Krum
│   ├── generalisation.py       leave-one-attack-out, feature ablation, tree-rule extraction
│   ├── temporal.py             chronological (per-day) evaluation, static vs rolling re-training
│   ├── resources.py            CPU time, working set and energy per million flows
│   ├── blockchain.py           permissioned PoA ledger, Merkle proofs, enrolment list
│   └── city_simulation.py      district gateways → ledger → cloud orchestrator + audit
├── fabric/                     Fabric chaincode (CCaaS), Gateway-SDK benchmark, runbook
├── paper_src/                  make_facts.py, make_figures.py, make_paper.js, make_supp.js
│   ├── apply_template_headers.js   splices the journal's header/footer parts into the built docx
│   └── template/               the official Smart Cities (MDPI) template and its styles.xml
├── tools/                      merge_csv.py, make_unsw_from_raw.py
│   └── check_wording_v25.py    post-build check: every wording/numeric fix since v25, still present
├── DATASETS.md                 where to get each dataset and how to prepare it
├── CHANGELOG.md                development log, including the bugs that were found and fixed
├── data/                       TON_IoT included; other datasets go here
└── results/                    all output (git-ignored)
```

## 8. Experiment ↔ code map

| Article | Code | Article | Code |
|---|---|---|---|
| E1 edge benchmark | `run_poc.py` Exp-1 / 1b | E8 ledger micro-benchmark | Exp-4 |
| E2 multi-seed CIs | `run_extended.py --part B` | E9 scalability + γ sweep | `--part C` |
| E3 FedAvg regimes | Exp-3 | E10 city replay + insider attacks | Exp-5 |
| E4 LPRA, personalised FL | Exp-9 | E11 zero-day ransomware scenario | `--part D` |
| E5 aggregator comparison | `--part A --seed N` | E12 cross-dataset | Exp-1c / Exp-2 |
| E6 leave-one-attack-out | Exp-7 | E13 Hyperledger Fabric | `fabric/` |
| E7 feature ablation | Exp-8 | S1 / S2 / S5 (supplement) | Exp-1m / Exp-6 / Exp-8b |
| E14 temporal drift | `run_advanced.py --part T` | E15 resources and energy | `--part R` |
| E16 adaptive attacker | `--part A --n-att 1\|2` | | |

## 9. Reproducibility notes

* Every experiment uses fixed seeds; multi-seed confidence intervals are in `--part B`.
* Timing figures (µs per flow, tx/s) are machine-dependent. Compare models **within** one run, not across
  machines. On the authors' hardware the detection metrics reproduced to the fourth decimal, while
  per-flow latency differed by 50%.
* The emulated ledger in `poc/blockchain.py` measures design choices (validator count, block size) against
  each other. For deployment figures use the Fabric experiment: it is roughly 327× slower (E13,
  computed dynamically in `make_facts.py` as `fab_ratio_txs`, so this number tracks whatever the
  Fabric benchmark actually measures on a re-run rather than going stale).
* The included TON_IoT file is the `Train_Test_Network` release; identifiers (IP, port, timestamp) are
  removed by the loader, not by the file.

## 10. Known limitations

1. All datasets are testbed captures. Identifier removal reduces, but does not eliminate, testbed artefacts.
2. CICIoT2023 reports per-window statistics without a directional split, so it participates only in the
   four-feature direction-free view.
3. LPRA is evaluated with at most 40% Byzantine districts. The adaptive sweep (E16) found a real failure of
   the first version of the screen at that ratio and motivated the hardened default (`version="v2"` in
   `poc/robust_fl.py`): the reference direction is now the median of the survivors' deltas and the accepted
   set must be a majority. Pass `version="v1"` to reproduce the failure. The "stealth" attack of
   Baruch et al. is still not detected, though it caused no measurable damage here.
4. Federated learning uses no secure aggregation or differential privacy, and the feature standardiser is
   fitted on pooled training statistics (2 × d numbers, not raw flows).
5. The Fabric measurement uses two organisations on one host; a geographically distributed deployment would
   be slower.

## 11. Citation and licence

MIT licence (see `LICENSE`). If you use this code, please cite the article and this repository
(`CITATION.cff`). The datasets remain under their original licences — cite TON_IoT (Moustafa 2021;
Alsaedi et al. 2020), CIC-IDS2017 (Sharafaldin et al. 2018), UNSW-NB15 (Moustafa & Slay 2015) and the
UCI Internet Firewall Data Set as appropriate.

## 12. Citing a fixed version

The manuscript's Data Availability statement should point at an immutable release, not at a moving branch.
Before submission, tag the commit that produced the reported numbers:

```bash
git tag -a v1.0-manuscript -m "Numbers reported in the Smart Cities submission"
git push origin v1.0-manuscript
```

and cite that tag (or the commit hash) in the paper.  The peer-review revision is tagged `v2.1.0`
(the Data Availability statement of the revised manuscript cites it); `v1.0-manuscript` remains the
submitted version.  Note that `paper_src/make_paper.js` regenerates the *submitted* manuscript text; the
revised text was edited in the manuscript file, and the numbers it reports come from `results/` as
regenerated under this release plus the harnesses in `review_response/` (see `CHANGELOG.md`, v2.0 and v2.1).  The revised manuscript is delivered with every changed passage shaded by source (green Reviewer 1, pink Reviewer 3, yellow Reviewer 2, purple Editor, grey authors' own corrections); the key is at the top of `CHANGELOG.md`. `results/paper_facts.json` and the CSV files it is
built from are the audit trail: every number in the manuscript can be traced to one of them, and
`python paper_src/make_figures.py` prints, per figure, which file and which table each value comes from.
The Fabric measurements live in `fabric/fabric_facts.json` because they are produced by a Docker network
rather than by the Python pipeline; the ledger size recorded there (24.3 MB after 4,001 anchored alerts —
two 2,000-alert benchmark runs plus one functional-test invocation) is stated in decimal MB.
