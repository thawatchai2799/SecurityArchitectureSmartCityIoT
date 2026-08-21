#!/usr/bin/env python3
"""
check_env.py -- 10-second preflight check.  Run this BEFORE run_poc.py / run_extended.py.

    python check_env.py

Verifies the Python version, the required packages, write access to results/,
which datasets are present, and that every present dataset actually loads with the
expected columns.  Prints an estimated runtime.  Exit code 0 = ready to run.
"""
import os, sys, time, platform, importlib

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OK, WARN, FAIL = "[ ok ]", "[warn]", "[FAIL]"
problems = 0


def line(tag, msg):
    print(f"{tag} {msg}")


print("=" * 78)
print("Smart-city security PoC - environment check")
print("=" * 78)
line(OK if sys.version_info >= (3, 9) else FAIL,
     f"Python {platform.python_version()} on {platform.system()} {platform.release()} "
     f"({os.cpu_count()} logical CPUs)")
if sys.version_info < (3, 9):
    problems += 1
    print("       Python 3.9+ is required (the code uses `str | None` type hints).")

for mod, minv in [("numpy", None), ("pandas", None), ("sklearn", "1.0"),
                  ("matplotlib", None), ("tabulate", None)]:
    try:
        m = importlib.import_module(mod)
        line(OK, f"{mod} {getattr(m, '__version__', '?')}")
    except Exception as e:
        problems += 1
        line(FAIL, f"{mod} missing ({e}); run:  pip install -r requirements.txt")

res = os.path.join(HERE, "results")
try:
    os.makedirs(res, exist_ok=True)
    probe = os.path.join(res, ".write_probe")
    open(probe, "w", encoding="utf-8").write("ok"); os.remove(probe)
    line(OK, f"results/ is writable ({res})")
except Exception as e:
    problems += 1; line(FAIL, f"cannot write to {res}: {e}")

try:
    from poc import data_loader as dl
except Exception as e:
    print(f"{FAIL} cannot import poc.data_loader: {e}"); sys.exit(1)

print("-" * 78)
avail = dl.available_datasets()
present = []
for key, ok in avail.items():
    fname = dl.FILES[key]
    if not ok:
        line(WARN, f"{key:11s} missing  ({fname})  -> the experiments that need it are skipped")
        continue
    t0 = time.time()
    try:
        d = dl.LOADERS[key](sample=20000)
        line(OK, f"{key:11s} loads OK  rows(sample)={len(d['y_bin']):,} native={d['X_native'].shape[1]} "
                 f"attack_ratio={d['y_bin'].mean():.3f} types={len(set(d['y_multi']))} "
                 f"[{time.time() - t0:.1f}s]")
        present.append(key)
    except Exception as e:
        problems += 1
        line(FAIL, f"{key:11s} FAILED to load: {type(e).__name__}")
        print("       " + str(e).replace("\n", "\n       ")[:900])

print("-" * 78)
n_extra = len([k for k in present if k not in ("ton_iot", "firewall")])
est = 3 + 4 * n_extra
print(f"Estimated runtime:  run_poc.py  ~{est}-{est + 5} min   |   "
      f"run_extended.py ~25-40 min (use --part A/B/C/D to split it)")
if problems:
    print(f"\n{problems} problem(s) found - fix them before running the experiments.")
    sys.exit(1)
print("\nAll good. Next:  python run_poc.py     then:  python run_extended.py")
