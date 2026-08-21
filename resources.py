"""
resources.py
------------
What a gateway actually spends to run each detector: CPU time, memory, and the energy that follows
from them. A smart city deploys thousands of these, so the per-flow cost is a sustainability question
as much as a performance one.

What is measured directly
    train_cpu_s        wall time to fit the model (single-threaded, so wall ≈ CPU)
    infer_cpu_us       time per flow at inference in batch mode, the deployed case, measured with a
                       high-resolution clock over a burst long enough to exceed the OS clock tick
    infer_mem_mb       peak memory allocated while classifying a batch (the model's working set)
    single_flow_cpu_us CPU time for one predict() call on a single flow -- the worst case a gateway
                       sees if it classifies packet by packet instead of in batches
    model_kb           serialised model size

What is derived, with the assumption stated in the output
    cpu_s_per_1M       CPU-seconds to classify one million flows  = infer_cpu_us x 1e6 / 1e6
    energy_J_per_1M    cpu_s_per_1M x P, for a stated board power P
    kWh_per_year       energy at a stated sustained flow rate

`energy_J_per_1M` is a scaling of measured CPU time by an assumed power figure, not a wattmeter
reading, and the manuscript says so. Two boards are quoted so that the reader can rescale: a
Raspberry-Pi-class gateway (~3 W under load, one core busy) and an x86 mini-PC (~12 W).
"""
from __future__ import annotations
import io
import gc
import time
import pickle
import platform
import tracemalloc
import numpy as np

BOARDS = {"pi_class_3W": 3.0, "x86_mini_12W": 12.0}   # sustained package power while one core works


def _peak_alloc_mb(fn) -> tuple[float, float]:
    """Peak Python-allocated memory attributable to `fn`, in MB, plus its return value.
    Process RSS is useless here because it is dominated by the loaded dataset; this isolates
    what the model itself needs while it works."""
    gc.collect()
    tracemalloc.start()
    out = fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / (1024.0 ** 2), out


def _model_kb(model) -> float:
    buf = io.BytesIO(); pickle.dump(model, buf); return buf.getbuffer().nbytes / 1024.0


def profile(model, X_train, y_train, X_test, batch: int = 8192, repeats: int = 3,
            flows_per_s_deployed: float = 1000.0) -> dict:
    """Fit `model`, then measure the CPU cost of classifying flows in batches."""
    X_train = np.asarray(X_train, dtype=np.float32); X_test = np.asarray(X_test, dtype=np.float32)
    t0 = time.perf_counter(); model.fit(X_train, y_train); train_cpu = time.perf_counter() - t0

    n = min(batch, len(X_test))
    Xb = X_test[:n]
    model.predict(Xb[:64])                       # warm up any lazy allocation

    # Windows' process_time() has a ~16 ms granularity, so a single batch predict reads as 0.
    # Time a whole burst of batches with perf_counter until the interval is long enough to be
    # meaningful, and repeat the burst a few times keeping the fastest (least-disturbed) run.
    def _timed_rate(fn, unit_count, min_seconds=0.25):
        reps = 1
        while True:
            t0 = time.perf_counter()
            for _ in range(reps):
                fn()
            dt = time.perf_counter() - t0
            if dt >= min_seconds or reps > 1 << 20:
                return dt / (reps * unit_count)
            reps = max(2 * reps, int(reps * min_seconds / max(dt, 1e-9)) + 1)

    per_flow = min(_timed_rate(lambda: model.predict(Xb), n) for _ in range(repeats))
    infer_cpu_us = per_flow * 1e6
    infer_mem_mb, _ = _peak_alloc_mb(lambda: model.predict(Xb))

    x1 = X_test[:1]
    single_flow_cpu_us = _timed_rate(lambda: model.predict(x1), 1) * 1e6

    cpu_s_per_1M = infer_cpu_us * 1e6 / 1e6          # µs/flow × 1e6 flows ÷ 1e6 µs per s
    out = dict(train_cpu_s=train_cpu, infer_cpu_us=infer_cpu_us, infer_mem_mb=infer_mem_mb,
               single_flow_cpu_us=single_flow_cpu_us, model_kb=_model_kb(model),
               cpu_s_per_1M=cpu_s_per_1M, flows_per_cpu_s=1e6 / max(infer_cpu_us, 1e-9))
    for name, watts in BOARDS.items():
        out[f"J_per_1M_{name}"] = cpu_s_per_1M * watts
        out[f"kWh_per_year_{name}"] = (cpu_s_per_1M * watts * flows_per_s_deployed * 3.156e7
                                       / 1e6 / 3.6e6)
    out["assumed_flows_per_s"] = flows_per_s_deployed
    return out


def profile_all(models: dict, X_train, y_train, X_test, **kw) -> list[dict]:
    rows = []
    for name, m in models.items():
        r = profile(m, X_train, y_train, X_test, **kw)
        r["model"] = name
        rows.append(r)
        print(f"  {name:20s} train {r['train_cpu_s']:6.2f} s | infer {r['infer_cpu_us']:7.2f} µs/flow "
              f"| {r['model_kb']:7.1f} KB | {r['cpu_s_per_1M']:7.2f} CPU-s per 1M flows "
              f"| {r['J_per_1M_pi_class_3W']:7.1f} J/1M (3 W board)")
    return rows
