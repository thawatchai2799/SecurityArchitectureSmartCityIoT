"""Reviewer 1, Comment 2(c): the ~0.03 ms "ledger anchoring" figure in E11.

city_simulation.EdgeGateway.process() starts a timer before model.predict(),
calls ledger.submit(), and stops the timer as soon as submit() returns.
submit() appends to the mempool and returns a tx id; the block is cut
later, when the mempool reaches block_size or block_interval elapses.  So
the figure is per-alert *submission* (plus one inference), not the time
until the alert is actually on the chain.

The ledger already records the right quantity: _cut_block() fills
metrics["tx_latencies"] with (commit_time - submit_time) per transaction.
This measures both on the same run so the manuscript can quote whichever it
means, correctly labelled.
"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc.blockchain import PermissionedLedger

if __name__ == "__main__":
    # Same ledger configuration as the simulation's default.
    led = PermissionedLedger(members=["Gateway-Healthcare"])
    print(f"block_size={led.block_size}  block_interval_s={led.block_interval}")

    submit_ms = []
    for i in range(2000):
        payload = dict(kind="ALERT", district="Healthcare", evidence_hash="a" * 64,
                       model="DecisionTreeClassifier", ts=time.time())
        t0 = time.perf_counter()
        led.submit(payload, submitter="Gateway-Healthcare")   # what E11 times
        submit_ms.append((time.perf_counter() - t0) * 1000)
    led.flush()

    commit_ms = [t * 1000 for t in led.metrics["tx_latencies"]]
    block_ms = [t * 1000 for t in led.metrics["block_latencies"]]

    def stat(v):
        v = np.asarray(v)
        return dict(mean=round(float(v.mean()), 4), p50=round(float(np.percentile(v, 50)), 4),
                    p95=round(float(np.percentile(v, 95)), 4), max=round(float(v.max()), 4))

    out = dict(n_tx=len(submit_ms), blocks=led.metrics["blocks"],
               submit_ms=stat(submit_ms), commit_ms=stat(commit_ms), block_cut_ms=stat(block_ms))
    print()
    print(f"  submission latency (what E11 reports): mean {out['submit_ms']['mean']:.4f} ms  "
          f"p95 {out['submit_ms']['p95']:.4f} ms")
    print(f"  commit latency (submit -> on chain)  : mean {out['commit_ms']['mean']:.4f} ms  "
          f"p95 {out['commit_ms']['p95']:.4f} ms")
    print(f"  block cut cost                       : mean {out['block_cut_ms']['mean']:.4f} ms "
          f"over {out['blocks']} blocks")
    ratio = out["commit_ms"]["mean"] / max(out["submit_ms"]["mean"], 1e-9)
    print(f"\n  commit is {ratio:.0f}x the submission figure")
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger_latency.json"), "w"), indent=1)
    print("\nwrote ledger_latency.json")
