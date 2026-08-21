#!/usr/bin/env python3
"""
run_advanced.py -- three experiments that answer the questions a random split, a latency figure and a
fixed attack list leave open.

    --part T   E14 temporal / concept drift   (needs the per-day CIC-IDS2017 files)
    --part R   E15 edge resource and energy accounting   (TON_IoT, no extra data)
    --part A   E16 adaptive attacker sweep against LPRA  (TON_IoT, no extra data)
    --part all everything available

Examples
    python run_advanced.py --part R
    python run_advanced.py --part A --n-att 1
    python run_advanced.py --part T --cicids-dir "C:/data/CIC_IDS2017/MachineLearningCVE"

Results land in results/ as CSV/JSON and are picked up by paper_src/make_facts.py.
"""
import os, sys, json, time, argparse, warnings
warnings.filterwarnings("ignore")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poc import data_loader as dl, edge_ids, byzantine, resources, temporal

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RES, exist_ok=True)


def _machine():
    import platform
    return dict(python=platform.python_version(), platform=platform.platform(),
                cpu_count=os.cpu_count(), run_date=time.strftime("%Y-%m-%d %H:%M"))


def save_json(obj, name):
    # stamp every result with the machine that produced it: mixing results from two hosts is the
    # easiest way to publish an inconsistent table, and make_facts.py checks these stamps.
    if isinstance(obj, dict):
        obj = dict(obj, machine=_machine())
    with open(os.path.join(RES, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=float)


# --------------------------------------------------------------------------- #
def part_temporal(a):
    print("\n[E14] Temporal evaluation on CIC-IDS2017 (chronological, one model per protocol)")
    pattern = os.path.join(a.cicids_dir, "*.csv") if a.cicids_dir else None
    if not pattern:
        print("  --cicids-dir not given; skipping. Point it at the folder holding "
              "Monday-WorkingHours.pcap_ISCX.csv etc.")
        return
    df = temporal.load_by_day(pattern, sample_per_file=a.per_file, seed=a.seed)
    print(f"  loaded {len(df):,} rows over {df['__day'].nunique()} days, "
          f"{len([c for c in df.columns if not c.startswith('__')])} features")
    out = temporal.run_temporal(df, n_train_days=a.train_days, kind="dt", seed=a.seed)
    rows = pd.DataFrame(out["rows"])
    rows.to_csv(os.path.join(RES, "exp15_temporal_cicids.csv"), index=False)
    print(f"\n  random-split control (the number a random-split paper would report): "
          f"F1 {out['control']['f1']:.4f}, FPR {out['control']['fpr']:.4f}")
    print(rows[["protocol", "day", "in_training", "n", "attack_ratio", "f1", "recall", "fpr"]]
          .round(4).to_string(index=False))
    print("\n  attack families first seen on each day:")
    for d, t in out["novel_types"].items():
        print(f"    {d:10s} {', '.join(t) if t else '(none new)'}")
    save_json(out, "exp15_temporal_cicids.json")


# --------------------------------------------------------------------------- #
def part_resources(a):
    print("\n[E15] Edge resource and energy accounting (TON_IoT, native features)")
    # No sub-sampling by default: the profiled model must be the same one reported in Table 4,
    # otherwise the serialised size differs (a smaller training set grows a smaller tree).
    ton = dl.load_ton_iot(sample=a.sample)
    X, y, m = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(y)), test_size=0.3, stratify=m, random_state=a.seed)
    rows = resources.profile_all(edge_ids.model_zoo(a.seed), X[tr], y[tr], X[te],
                                 flows_per_s_deployed=a.flows_per_s)
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(RES, "exp16_resources.csv"), index=False)
    print(f"\n  assumptions: energy = measured CPU-seconds x board power; boards "
          f"{resources.BOARDS}; deployed rate {a.flows_per_s:,.0f} flows/s per gateway")
    print(d[["model", "infer_cpu_us", "single_flow_cpu_us", "infer_mem_mb", "model_kb",
             "cpu_s_per_1M", "J_per_1M_pi_class_3W", "kWh_per_year_pi_class_3W"]]
          .round(3).to_string(index=False))
    save_json(dict(rows=rows, boards=resources.BOARDS, flows_per_s=a.flows_per_s,
                   note="energy is measured CPU time scaled by an assumed board power, "
                        "not a wattmeter reading"), "exp16_resources.json")


# --------------------------------------------------------------------------- #
def part_adaptive(a):
    print("\n[E16] Adaptive attacker that knows LPRA: strength sweep")
    ton = dl.load_ton_iot(sample=a.sample or 60000)     # the sweep is 36 federated runs; keep it quick
    X, y, m = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(y)), test_size=0.3, stratify=m, random_state=a.seed)
    kw = dict(k=5, rounds=a.rounds, seed=a.seed, regime="non-iid")

    path = os.path.join(RES, "exp17_adaptive_sweep.csv")
    done = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    rows = done.to_dict("records") if len(done) else []

    # three defences: no screen at all, the first version of the screen, and the hardened default.
    # v1 is kept because the sweep is what exposed its failure mode, and the paper reports it.
    variants = [("fedavg", None), ("lpra", "v1"), ("lpra", "v2")]
    for agg, ver in variants:
        tag = agg if ver is None else f"{agg}_{ver}"
        vkw = dict(kw)
        if ver:
            vkw["lpra_version"] = ver
        ctrl = byzantine.run_byzantine(X[tr], y[tr], m[tr], X[te], y[te], attack="none", n_att=0,
                                       aggregator=agg, **vkw)
        rows.append(dict(aggregator=tag, direction="none", strength=0.0, n_att=0,
                         f1=ctrl["final_f1"], caught=0, honest_rej=ctrl["honest_rejections"],
                         damage=0.0))
        base = ctrl["final_f1"]
        for direction in ("orthogonal", "opposite"):
            for s in a.strengths:
                r = byzantine.run_byzantine(X[tr], y[tr], m[tr], X[te], y[te], attack="adaptive",
                                            n_att=a.n_att, aggregator=agg, strength=s,
                                            direction=direction, **vkw)
                rows.append(dict(aggregator=tag, direction=direction, strength=s, n_att=a.n_att,
                                 f1=r["final_f1"], caught=r["rounds_all_attackers_rejected"],
                                 honest_rej=r["honest_rejections"], damage=base - r["final_f1"]))
                print(f"  {tag:9s} {direction:10s} s={s:5.1f} n={a.n_att} "
                      f"F1={r['final_f1']:.4f} damage={base - r['final_f1']:+.4f} "
                      f"caught={r['rounds_all_attackers_rejected']}/{a.rounds}")
        pd.DataFrame(rows).to_csv(path, index=False)
    print(f"\n  wrote {path}")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", help="T | R | A | all")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sample", type=int, default=None,
                    help="TON_IoT rows (default: the full dataset, so that E15 profiles exactly the "
                         "model E1 benchmarks; E16 falls back to 60,000 rows for speed)")
    ap.add_argument("--rounds", type=int, default=10, help="federated rounds for E16")
    ap.add_argument("--n-att", type=int, default=1, help="Byzantine districts for E16 (1 or 2)")
    ap.add_argument("--strengths", type=float, nargs="*",
                    default=[1.0, 2.0, 2.5, 3.0, 6.0, 20.0],
                    help="attacker distance as a multiple of the honest median distance")
    ap.add_argument("--flows-per-s", type=float, default=1000.0, help="deployed rate for E15 energy")
    ap.add_argument("--cicids-dir", default=None, help="folder with the per-day CIC-IDS2017 CSVs")
    ap.add_argument("--per-file", type=int, default=120000, help="rows sampled per day file")
    ap.add_argument("--train-days", type=int, default=3, help="days used for training in E14")
    a = ap.parse_args()

    import platform
    print("machine:", dict(python=platform.python_version(), platform=platform.platform(),
                           cpu_count=os.cpu_count(), run_date=time.strftime("%Y-%m-%d %H:%M")))
    t0 = time.time()
    if a.part in ("all", "T"):
        part_temporal(a)
    if a.part in ("all", "R"):
        part_resources(a)
    if a.part in ("all", "A"):
        part_adaptive(a)
    print(f"\nDone part={a.part} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
