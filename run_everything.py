#!/usr/bin/env python3
"""
run_everything.py -- the whole operational-cost study in one command.

    python run_everything.py --cicids-dir /path/to/MachineLearningCVE

What it does, in order
    1. preflight: data files, Python packages, output folder
    2. chronological windows for every seed (cached as .npz, built once)
    3. every replay: seeds x protocols x re-training policies (6 x 12), in parallel worker processes,
       resumable (a replay whose result file already exists is skipped)
    4. tables, figures and sustain_facts.json (make_sustain_figures.py)
    5. formatted manuscript facts (paper_src/make_sustain_facts.py)
    6. supplementary tables S1-S4 (make_supplementary.py)
    6. optionally the manuscript .docx (--paper vNN; needs node + the docx package)

Progress is printed as each replay finishes and at least every 30 s:
percent done, elapsed time, estimated remaining time and the clock time at which the run is
expected to finish. The estimate is based on measured per-replay durations and re-calibrates
itself to this machine as replays complete, so the first estimate is rough and later ones are not.

Options
    --dataset cic2017|cic2018   which stream: CIC-IDS2017 MachineLearningCVE (8 files, default) or
                                CSE-CIC-IDS2018 "Processed Traffic Data for ML Algorithms" (10 files)
    --seeds 42 43 44 45 46      seeds to run (default: these five)
    --workers N                 parallel replays (default: half the CPUs, at least 1, at most 4)
    --results-dir DIR           output folder (default: results_sustain)
    --paper v03                 also build the manuscript as versions/Paper_Draft_<v03>.docx
    --quick                     smoke test: 2 seeds, 16,000 flows per day, 3 protocols x 5 policies
    --force                     re-run replays even if their result files exist
"""
import os
import sys
# BLAS must be pinned before numpy is imported, in this process and in every worker (workers are
# spawned and re-import this file, so the pinning below runs there too).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
import json
import glob
import time
import argparse
import datetime
import subprocess
import multiprocessing as mp
import warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

PROTOCOLS = ["tree_local", "tree_cap", "mlp_local", "fedavg", "lpra", "central"]
POLICIES = ["static", "every_1", "every_2", "every_4", "every_8", "trigger", "drift", "oracle",
            "adwin", "kswin", "ddm", "drift_fb"]
QUICK_PROTOCOLS = ["tree_cap", "mlp_local", "fedavg"]
QUICK_POLICIES = ["static", "every_2", "drift", "adwin", "ddm"]

# Measured wall-clock seconds per replay on the reference machine (one core per replay). Only the
# ratios matter: they order the jobs (longest first) and seed the time estimate, which is then
# re-calibrated from the replays that have actually finished on this machine.
REF_SECONDS = {
    "tree_local": {"static": 12, "every_1": 305, "every_2": 162, "every_4": 83, "every_8": 50, "trigger": 9, "drift": 125, "oracle": 138},
    "tree_cap":   {"static": 8,  "every_1": 290, "every_2": 150, "every_4": 80, "every_8": 48, "trigger": 8, "drift": 122, "oracle": 133},
    "mlp_local":  {"static": 11, "every_1": 14,  "every_2": 14,  "every_4": 14, "every_8": 14, "trigger": 12, "drift": 14, "oracle": 14},
    "fedavg":     {"static": 13, "every_1": 26,  "every_2": 27,  "every_4": 26, "every_8": 26, "trigger": 13, "drift": 28, "oracle": 27},
    "lpra":       {"static": 13, "every_1": 28,  "every_2": 26,  "every_4": 26, "every_8": 26, "trigger": 13, "drift": 27, "oracle": 27},
    "central":    {"static": 12, "every_1": 23,  "every_2": 24,  "every_4": 23, "every_8": 25, "trigger": 12, "drift": 23, "oracle": 21},
}
# the standard drift detectors: provisional estimates (the detector itself costs seconds; the
# re-training count is what decides the time), refined by the calibration during the run
for _p, _d in REF_SECONDS.items():
    _d.setdefault("adwin", _d["drift"]); _d.setdefault("kswin", _d["every_2"]); _d.setdefault("ddm", _d["drift"])
    _d.setdefault("drift_fb", _d["drift"] + _d["every_8"])


# ----------------------------------------------------------------------------------------------- #
#  small helpers
# ----------------------------------------------------------------------------------------------- #
def hms(seconds: float) -> str:
    seconds = max(int(round(seconds)), 0)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def clock(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M on %a %d %b")


class Log:
    """Print to the console and append to a log file."""
    def __init__(self, path):
        self.f = open(path, "a", encoding="utf-8")

    def __call__(self, msg=""):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self.f.write(line + "\n"); self.f.flush()


def machine_info():
    import platform
    return dict(python=platform.python_version(), platform=platform.platform(),
                cpu_count=os.cpu_count(), run_date=time.strftime("%Y-%m-%d %H:%M"))


# ----------------------------------------------------------------------------------------------- #
#  step 1: preflight
# ----------------------------------------------------------------------------------------------- #
def preflight(a, log):
    from sustain.windows import FILE_ORDER, _day_key_2018
    problems = []
    a.day_order = []
    if not os.path.isdir(a.cicids_dir):
        problems.append(f"--cicids-dir is not a folder: {a.cicids_dir}")
    elif a.dataset == "cic2017":
        for _, fname in FILE_ORDER:
            if not os.path.exists(os.path.join(a.cicids_dir, fname)):
                problems.append(f"missing data file: {fname}")
        a.day_order = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    else:
        files = sorted(glob.glob(os.path.join(a.cicids_dir, "*.csv")))
        if len(files) != 10:
            problems.append(f"expected the 10 per-day CSV files of CSE-CIC-IDS2018 in {a.cicids_dir}, found {len(files)}")
        try:
            a.day_order = sorted(_day_key_2018(os.path.basename(f)) for f in files)
        except ValueError as e:
            problems.append(str(e))
    for mod in ("numpy", "pandas", "sklearn", "matplotlib", "scipy", "tabulate"):
        try:
            __import__(mod)
        except ImportError:
            problems.append(f"missing Python package: {mod}  (pip install {mod if mod != 'sklearn' else 'scikit-learn'})")
    os.makedirs(a.results_dir, exist_ok=True)
    try:
        probe = os.path.join(a.results_dir, ".write_test"); open(probe, "w").close(); os.remove(probe)
    except OSError as e:
        problems.append(f"results folder not writable: {a.results_dir} ({e})")
    if a.paper:
        if subprocess.run(["node", "--version"], capture_output=True).returncode != 0:
            problems.append("--paper needs node (Node.js 18+)")
        elif subprocess.run(["node", "-e", "require('docx'); require('jszip')"], capture_output=True, cwd=ROOT).returncode != 0:
            problems.append("--paper needs the docx and jszip packages: npm install docx jszip")
    if problems:
        log("PREFLIGHT FAILED:")
        for p in problems:
            log("  - " + p)
        sys.exit(1)
    log(f"preflight ok: {a.dataset}, {len(a.day_order)} capture days, packages present, results -> {a.results_dir}")
    log(f"machine: {machine_info()}")


# ----------------------------------------------------------------------------------------------- #
#  step 2: window caches
# ----------------------------------------------------------------------------------------------- #
def cache_path(results_dir, seed, sample_per_day, windows_per_day, dataset="cic2017"):
    tag = "" if dataset == "cic2017" else f"_{dataset}"
    return os.path.join(results_dir, f"windows{tag}_s{seed}_{sample_per_day}x{windows_per_day}.npz")


def _save_cache(cp, d, results_dir, seed):
    import numpy as np
    from sustain.windows import window_table
    np.savez_compressed(cp, X=d["X"], y=d["y"], ytype=d["ytype"], day=d["day"], win=d["win"],
                        district=d["district"], feats=np.array(d["feats"]), meta=json.dumps(d["meta"]))
    window_table(d).to_csv(os.path.join(results_dir, f"window_table_s{seed}.csv"), index=False)


def build_caches(a, log):
    from sustain.windows import load_windows, load_windows_2018
    todo = [sd for sd in a.seeds if not os.path.exists(cache_path(a.results_dir, sd, a.sample_per_day, a.windows_per_day, a.dataset))]
    for sd in a.seeds:
        if sd not in todo:
            log(f"windows for seed {sd}: cached")
    if not todo:
        return
    t0 = time.time()
    if a.dataset == "cic2018":
        # the 2018 files are large (one is 3.8 GB): read each file once for all seeds
        log(f"windows for seeds {todo}: reading the {len(a.day_order)} day files once for all seeds (several minutes) ...")
        out = load_windows_2018(a.cicids_dir, sample_per_day=a.sample_per_day, windows_per_day=a.windows_per_day,
                                seeds=todo, verbose=False)
        for sd in todo:
            _save_cache(cache_path(a.results_dir, sd, a.sample_per_day, a.windows_per_day, a.dataset), out[sd], a.results_dir, sd)
            log(f"windows for seed {sd}: {out[sd]['meta']['n_rows']:,} flows, {out[sd]['meta']['n_windows']} windows, "
                f"{out[sd]['meta']['k']} districts")
        log(f"windows built in {time.time() - t0:.0f} s")
        return
    for i, sd in enumerate(todo):
        t1 = time.time()
        log(f"windows for seed {sd}: loading the 8 day files ({i + 1}/{len(todo)}) ...")
        d = load_windows(a.cicids_dir, sample_per_day=a.sample_per_day, windows_per_day=a.windows_per_day,
                         seed=sd, verbose=False)
        _save_cache(cache_path(a.results_dir, sd, a.sample_per_day, a.windows_per_day, a.dataset), d, a.results_dir, sd)
        log(f"windows for seed {sd}: {d['meta']['n_rows']:,} flows, {d['meta']['n_windows']} windows, "
            f"{d['meta']['k']} districts ({time.time() - t1:.0f} s)")


def load_cache(cp):
    import numpy as np
    z = np.load(cp, allow_pickle=True)
    d = {k: z[k] for k in ("X", "y", "ytype", "day", "win", "district")}
    d["feats"] = list(z["feats"]); d["meta"] = json.loads(str(z["meta"]))
    return d


# ----------------------------------------------------------------------------------------------- #
#  step 3: replays in worker processes
# ----------------------------------------------------------------------------------------------- #
def job_path(results_dir, protocol, policy, seed):
    return os.path.join(results_dir, f"replay_{protocol}_{policy}_s{seed}.json")


def run_one(job):
    """Worker: one replay. Returns (job, seconds, error-or-None). Never raises."""
    protocol, policy, seed, cfg = job
    t0 = time.time()
    try:
        from sustain.chrono import replay
        data = load_cache(cache_path(cfg["results_dir"], seed, cfg["sample_per_day"], cfg["windows_per_day"], cfg["dataset"]))
        r = replay(data, protocol, policy, w_init=cfg["w_init"], seed=seed, rounds=cfg["rounds"],
                   local_epochs=cfg["local_epochs"], delta=cfg["delta"], standardise_inplace=True)
        r["machine"] = machine_info()
        r["args"] = dict(cfg, protocol=protocol, policy=policy, seed=seed)
        out = job_path(cfg["results_dir"], protocol, policy, seed)
        tmp = out + ".tmp"
        with open(tmp, "w") as f:
            json.dump(r, f, indent=1, default=float)
        os.replace(tmp, out)                      # atomic: a half-written file never counts as done
        return job, time.time() - t0, None
    except Exception as e:                        # report, do not kill the pool
        import traceback
        return job, time.time() - t0, traceback.format_exc(limit=3) + str(e)


MATCH_KEYS = ("sample_per_day", "windows_per_day", "w_init", "rounds", "local_epochs", "delta", "dataset")


def _is_done(path, cfg):
    """A replay counts as done only if its result file exists AND was produced with the same
    experimental settings; a file left by a smoke test or an earlier configuration is re-run."""
    if not os.path.exists(path):
        return False
    try:
        args = json.load(open(path))["args"]
    except Exception:
        return False
    legacy = {"dataset": "cic2017"}               # files written before the dataset option existed
    return all(args.get(k, legacy.get(k)) == cfg[k] for k in MATCH_KEYS)


def run_replays(a, log):
    cfg = dict(results_dir=a.results_dir, sample_per_day=a.sample_per_day, windows_per_day=a.windows_per_day,
               w_init=a.w_init, rounds=a.rounds, local_epochs=a.local_epochs, delta=a.delta, dataset=a.dataset)
    # reference durations were measured on the 40-window 2017 stream; a longer stream costs
    # proportionally more re-trainings, so scale the estimate by the number of held-out windows
    n_win = a.windows_per_day * len(a.day_order)
    scale = max(n_win - a.w_init, 1) / 24.0
    # refuse to mix two streams in one results folder (tables and figures would silently blend them)
    for p in glob.glob(os.path.join(a.results_dir, "replay_*_s*.json")):
        try:
            ds = json.load(open(p))["summary"].get("dataset", "cic2017")
        except Exception:
            continue
        if ds != a.dataset:
            log(f"ABORT: {a.results_dir} already holds {ds} replays; use --results-dir for a separate folder")
            sys.exit(1)
    jobs, skipped, stale = [], 0, 0
    for seed in a.seeds:
        for p in a.protocols:
            for pol in a.policies:
                path = job_path(a.results_dir, p, pol, seed)
                if not a.force and _is_done(path, cfg):
                    skipped += 1; continue
                if os.path.exists(path) and not a.force:
                    stale += 1
                jobs.append((p, pol, seed, cfg))
    if stale:
        log(f"{stale} existing result file(s) were produced with different settings (e.g. a smoke test) and will be re-run")
    weight = lambda j: REF_SECONDS[j[0]][j[1]] * scale
    jobs.sort(key=weight, reverse=True)           # longest first: better packing across workers
    total_w = sum(weight(j) for j in jobs)
    n_total = len(jobs) + skipped
    log(f"replays: {len(jobs)} to run, {skipped} already done, {a.workers} worker(s)")
    if not jobs:
        return 0

    t_start = time.time()
    done_w, done_n, done_secs, failed = 0.0, 0, 0.0, []
    # first estimate: reference durations, perfectly packed over the workers
    est_total = total_w / a.workers
    log(f"first estimate (reference machine, {a.workers} worker(s)): about {hms(est_total)} -> "
        f"finish around {clock(t_start + est_total)}; this will re-calibrate as replays complete")

    def report():
        pct = 100.0 * (skipped + done_n) / n_total
        elapsed = time.time() - t_start
        # speed = real seconds per reference second on this machine (1.0 until a replay has finished);
        # work consumed so far = elapsed x workers (all workers busy), remaining work = total - consumed
        speed = done_secs / done_w if done_w > 0 else 1.0
        remaining = max(total_w * speed - elapsed * a.workers, 0.0) / a.workers
        log(f"progress {skipped + done_n}/{n_total} = {pct:5.1f} % | elapsed {hms(elapsed)} | "
            f"remaining about {hms(remaining)} | finish around {clock(time.time() + remaining)}")

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=a.workers) as pool:
        pending = [pool.apply_async(run_one, (j,)) for j in jobs]
        last_report = time.time()
        while pending:
            still = []
            for res in pending:
                if res.ready():
                    job, secs, err = res.get()
                    done_n += 1; done_w += weight(job); done_secs += secs
                    tag = f"{job[0]:10s} {job[1]:8s} seed {job[2]}"
                    if err:
                        failed.append((job, err)); log(f"FAILED  {tag} after {hms(secs)}:\n{err}")
                    else:
                        log(f"done    {tag} in {hms(secs)}")
                    report(); last_report = time.time()
                else:
                    still.append(res)
            pending = still
            if pending and time.time() - last_report >= 30:
                report(); last_report = time.time()
            if pending:
                time.sleep(2)
    log(f"replays finished: {done_n - len(failed)} ok, {len(failed)} failed, {hms(time.time() - t_start)} elapsed")
    if failed:
        log("FAILED replays (fix the cause and re-run; finished replays are kept):")
        for job, _ in failed:
            log(f"  - {job[0]} {job[1]} seed {job[2]}")
    return len(failed)


# ----------------------------------------------------------------------------------------------- #
#  steps 4-6: tables, figures, facts, manuscript
# ----------------------------------------------------------------------------------------------- #
def run_script(args, log, env=None):
    log("running: " + " ".join(args))
    r = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
    for line in tail:
        log("    " + line)
    if r.returncode != 0:
        log(f"FAILED (exit {r.returncode}): " + " ".join(args))
    return r.returncode


def postprocess(a, log):
    env = dict(os.environ, SUSTAIN_RESULTS=a.results_dir)
    rc = run_script([sys.executable, os.path.join(ROOT, "make_sustain_figures.py")], log, env)
    if rc:
        return rc
    rc = run_script([sys.executable, os.path.join(ROOT, "paper_src", "make_sustain_facts.py")], log, env)
    if rc:
        return rc
    rc = run_script([sys.executable, os.path.join(ROOT, "make_supplementary.py")], log, env)
    if rc:
        return rc
    if a.paper:
        rc = run_script(["node", os.path.join(ROOT, "paper_src", "make_sustain_paper.js"), a.paper], log, env)
    return rc


# ----------------------------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cicids-dir", required=True, help="folder with the per-day CSV files of the chosen dataset")
    ap.add_argument("--dataset", choices=["cic2017", "cic2018"], default="cic2017")
    ap.add_argument("--seeds", type=int, nargs="*", default=[42, 43, 44, 45, 46])
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    ap.add_argument("--results-dir", default=os.path.join(ROOT, "results_sustain"))
    ap.add_argument("--paper", default=None, metavar="vNN", help="also build the manuscript, e.g. --paper v03")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sample-per-day", type=int, default=160000)
    ap.add_argument("--windows-per-day", type=int, default=8)
    ap.add_argument("--w-init", type=int, default=16)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--local-epochs", type=int, default=2)
    ap.add_argument("--delta", type=float, default=0.05)
    a = ap.parse_args()
    if a.results_dir == os.path.join(ROOT, "results_sustain") and a.dataset != "cic2017":
        a.results_dir = os.path.join(ROOT, f"results_sustain_{a.dataset}")      # keep the two streams apart
    if a.quick and a.results_dir in (os.path.join(ROOT, "results_sustain"), os.path.join(ROOT, f"results_sustain_{a.dataset}")):
        a.results_dir = a.results_dir + "_quick"                                 # never mixed with real results
    a.results_dir = os.path.abspath(a.results_dir)
    a.protocols, a.policies = PROTOCOLS, POLICIES
    if a.quick:
        a.seeds = a.seeds[:2]; a.sample_per_day = 16000
        a.protocols, a.policies = QUICK_PROTOCOLS, QUICK_POLICIES
    os.makedirs(a.results_dir, exist_ok=True)
    log = Log(os.path.join(a.results_dir, "run_everything.log"))
    t0 = time.time()
    log("=" * 80)
    log(f"run_everything.py started; seeds {a.seeds}; {len(a.protocols)} protocols x {len(a.policies)} policies"
        + ("; QUICK smoke test" if a.quick else ""))

    preflight(a, log)
    build_caches(a, log)
    n_failed = run_replays(a, log)
    if n_failed:
        log("post-processing skipped because some replays failed; re-run the same command to retry them")
        sys.exit(2)
    rc = postprocess(a, log)
    if rc:
        log(f"FINISHED WITH ERRORS after {hms(time.time() - t0)}; see the messages above and {os.path.join(a.results_dir, 'run_everything.log')}")
    else:
        log(f"ALL DONE in {hms(time.time() - t0)}; results in {a.results_dir}"
            + (f"; manuscript in versions/Paper_Draft_{a.paper}.docx" if a.paper else ""))
    sys.exit(rc)


if __name__ == "__main__":
    mp.freeze_support()
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n[{time.strftime('%H:%M:%S')}] interrupted by the user; finished replays are kept -- "
              "run the same command again to resume where it stopped", flush=True)
        sys.exit(130)
