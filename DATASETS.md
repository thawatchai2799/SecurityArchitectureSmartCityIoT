# Datasets

`data/TON_IoT_Train_Test_Network.csv` is included in this repository. Everything else is optional and is
downloaded by the user; put each file in `data/` under exactly the name in the table.

| File in `data/` | Rows used in the article | Where to get it |
|---|---|---|
| `TON_IoT_Train_Test_Network.csv` | 211,043 | **included** · [UNSW Canberra TON_IoT](https://research.unsw.edu.au/projects/toniot-datasets) |
| `CICIDS2017.csv` | 300,000 (sampled from the 8 `MachineLearningCVE` files) | [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) |
| `UNSW_NB15_training-set.csv` | 200,000 (sampled from the raw 4-file release) | [UNSW-NB15](https://research.unsw.edu.au/projects/unsw-nb15-dataset) |
| `log2.csv` | 65,532 | [UCI Internet Firewall Data, id 542](https://archive.ics.uci.edu/dataset/542/internet+firewall+data) |
| `CICIoT2023.csv` (optional) | — | [CICIoT2023](https://www.unb.ca/cic/datasets/iotdataset-2023.html) |

## Preparation commands

```bash
# CIC-IDS2017 — merge the eight per-day files (quote the pattern; the script expands it itself,
# which is what makes this work on Windows shells too)
python tools/merge_csv.py "path/to/MachineLearningCVE/*.csv" data/CICIDS2017.csv --sample 300000

# UNSW-NB15 — only if you have the RAW release (UNSW-NB15_1.csv … _4.csv, 49 columns, no header)
python tools/make_unsw_from_raw.py "path/to/UNSW_NB15/UNSW-NB15_*.csv" --sample 200000

# Internet Firewall Data (the UCI Python API does not serve this one)
curl -sSLO https://archive.ics.uci.edu/static/public/542/internet+firewall+data.zip
unzip -o "internet+firewall+data.zip" -d dl_firewall && cp dl_firewall/log2.csv data/log2.csv

# CICIoT2023 — the full release is ~13 GB; 10–15 part files are enough for the 300k sample
python tools/merge_csv.py "path/to/CICIoT2023/*.csv" data/CICIoT2023.csv --sample 300000
```

## Always verify before a long run

```bash
python check_env.py
```

Each present dataset is actually loaded. If a column is missing or renamed, the error names the missing
column **and** lists every column found in the file, so the fix is a one-line edit in
`poc/data_loader.py`. Datasets that are absent are skipped, and the experiments that need them are skipped
with them — nothing crashes.

## How each dataset is used

* **Native view** — every numeric, flag and one-hot feature of that dataset, minus IP addresses, ports and
  timestamps (these identify the attacker machine in a testbed and inflate accuracy).
* **Common view (9 features)** — duration, source/destination bytes and packets, bytes per packet each way,
  packet ratio, byte ratio. Used for cross-dataset transfer between datasets that distinguish direction.
* **Direction-free view (4 features)** — duration, total bytes, total packets, bytes per packet. Defined for
  every dataset including CICIoT2023, which reports per-window statistics without a directional split.

## Licences

Each dataset keeps its own licence and citation requirements. TON_IoT is redistributed here under the terms
set by UNSW Canberra; cite Moustafa (2021), *Sustainable Cities and Society* 72:102994 and Alsaedi et al.
(2020), *IEEE Access* 8:165130. The other datasets are not redistributed.
