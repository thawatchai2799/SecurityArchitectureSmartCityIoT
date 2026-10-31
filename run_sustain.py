#!/usr/bin/env python3
"""
run_sustain.py -- operational-sustainability replay on the CIC-IDS2017 week.

    python run_sustain.py --cicids-dir DIR --seed 42                 # full grid for one seed
    python run_sustain.py --cicids-dir DIR --seed 42 --quick         # 2 protocols x 2 policies
    python run_sustain.py --cicids-dir DIR --protocols fedavg lpra --policies every_1 trigger

Results: results_sustain/replay_<protocol>_<policy>_s<seed>.json (per-window rows + events)
         results_sustain/summary.csv (one row per run, appended / updated)
BLAS is pinned to one thread BEFORE numpy is imported so that CPU-seconds are the cost of the
computation, not of thread spin-up; compare runs within one machine only.
"""
import os, sys, json, time, argparse
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sustain.windows import load_windows, window_table
from sustain.chrono import replay, PROTOCOLS

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results_sustain")
os.makedirs(RES, exist_ok=True)
POLICIES = ["static", "every_1", "every_2", "every_4", "every_8", "trigger", "drift", "oracle", "adwin", "kswin", "ddm", "drift_fb"]


def _machine():
    import platform
    return dict(python=platform.python_version(), platform=platform.platform(),
                cpu_count=os.cpu_count(), run_date=time.strftime("%Y-%m-%d %H:%M"))


def load_cached(cicids_dir, seed, sample_per_day, windows_per_day):
    cache = os.path.join(RES, f"windows_s{seed}_{sample_per_day}x{windows_per_day}.npz")
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        d = {k: z[k] for k in ("X", "y", "ytype", "day", "win", "district")}
        d["feats"] = list(z["feats"]); d["meta"] = json.loads(str(z["meta"]))
        print(f"  windows loaded from cache {os.path.basename(cache)}")
        return d
    d = load_windows(cicids_dir, sample_per_day=sample_per_day, windows_per_day=windows_per_day, seed=seed)
    np.savez_compressed(cache, X=d["X"], y=d["y"], ytype=d["ytype"], day=d["day"], win=d["win"],
                        district=d["district"], feats=np.array(d["feats"]), meta=json.dumps(d["meta"]))
    window_table(d).to_csv(os.path.join(RES, f"window_table_s{seed}.csv"), index=False)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cicids-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--protocols", nargs="*", default=PROTOCOLS)
    ap.add_argument("--policies", nargs="*", default=POLICIES)
    ap.add_argument("--w-init", type=int, default=16)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--local-epochs", type=int, default=2)
    ap.add_argument("--sample-per-day", type=int, default=160000)
    ap.add_argument("--windows-per-day", type=int, default=8)
    ap.add_argument("--delta", type=float, default=0.05)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-run even if the result file exists")
    a = ap.parse_args()
    if a.quick:
        a.protocols, a.policies = ["tree_local", "fedavg"], ["static", "every_2"]
    print("machine:", _machine())
    data = load_cached(a.cicids_dir, a.seed, a.sample_per_day, a.windows_per_day)

    rows = []
    for p in a.protocols:
        for pol in a.policies:
            out_path = os.path.join(RES, f"replay_{p}_{pol}_s{a.seed}.json")
            if os.path.exists(out_path) and not a.force:
                with open(out_path) as f:
                    rows.append(json.load(f)["summary"]); print(f"  {p:10s} {pol:8s} cached"); continue
            t0 = time.time()
            r = replay(data, p, pol, w_init=a.w_init, seed=a.seed, rounds=a.rounds,
                       local_epochs=a.local_epochs, delta=a.delta)
            r["machine"] = _machine(); r["args"] = vars(a)
            with open(out_path, "w") as f:
                json.dump(r, f, indent=1, default=float)
            s = r["summary"]; rows.append(s)
            print(f"  {p:10s} {pol:8s} meanF1 {s['mean_f1']:.3f} streamF1 {s['stream_f1']:.3f} "
                  f"retrains {s['n_retrain']:2d} cpu {s['retrain_cpu_s']:7.2f}s "
                  f"MB {(s['bytes_up']+s['bytes_down']+s['raw_bytes'])/1e6:8.2f} tx {s['tx']:4d}  ({time.time()-t0:.0f}s)")
    # ---- merge into the grid summary --------------------------------------------------------
    sp = os.path.join(RES, "summary.csv")
    df = pd.DataFrame(rows)
    if os.path.exists(sp):
        old = pd.read_csv(sp)
        key = ["protocol", "policy", "seed"]
        old = old[~old.set_index(key).index.isin(df.set_index(key).index)]
        df = pd.concat([old, df], ignore_index=True)
    df.sort_values(["protocol", "policy", "seed"]).to_csv(sp, index=False)
    print(f"summary -> {sp} ({len(df)} rows)")


if __name__ == "__main__":
    main()
