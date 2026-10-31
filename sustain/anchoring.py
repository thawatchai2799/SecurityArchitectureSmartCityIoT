"""
anchoring.py
------------
What the provenance layer costs per year under each re-training policy, and how much of it a
batched (Merkle) anchoring design removes without weakening what the ledger proves.

The article anchors one transaction per client update and one per global model, per round
((K+1) tx per round), and measured on Hyperledger Fabric 2.5.9 that each anchored record costs
6,076 bytes of ledger (71 % of it X.509 certificates). The replay (chrono.py) counts the tx each
policy generates. Here three anchoring granularities are compared:

    per-record   (K+1) tx per round                         -- the article's design
    per-round    1 tx per round: Merkle root of the (K+1) record hashes
    per-event    1 tx per re-training event: Merkle root over all R x (K+1) hashes

In both batched designs a district can still prove, with a log2(b)-hash Merkle proof against the
anchored root, that its update (or its quarantine decision) was in the batch; what changes is
that the proof is kept by the parties instead of on the ledger. The CPU cost of building roots
and proofs and of verifying them is measured here with the same Merkle code as the article's
emulated ledger (poc/blockchain.py), so it is a measurement, not an assumption; the ledger bytes
per tx are the Fabric measurement.
"""
from __future__ import annotations
import time
import hashlib
import numpy as np
import pandas as pd

from poc.blockchain import merkle_root, merkle_proof, verify_proof, sha256

BYTES_PER_TX = 6076     # fabric/fabric_facts.json
HASH_BYTES = 32


def _measure(batch: int, repeats: int = 200) -> dict:
    hashes = [sha256(f"record-{i}") for i in range(batch)]
    t0 = time.perf_counter()
    for _ in range(repeats):
        root = merkle_root(hashes)
    t_root = (time.perf_counter() - t0) / repeats
    t0 = time.perf_counter()
    for _ in range(repeats):
        proof = merkle_proof(hashes, batch // 2)
    t_proof = (time.perf_counter() - t0) / repeats
    t0 = time.perf_counter()
    for _ in range(repeats):
        ok = verify_proof(hashes[batch // 2], proof, root)
    t_verify = (time.perf_counter() - t0) / repeats
    assert ok
    return dict(batch=batch, root_us=t_root * 1e6, proof_us=t_proof * 1e6, verify_us=t_verify * 1e6,
                proof_bytes=len(proof) * HASH_BYTES, proof_hashes=len(proof))


def anchoring_table(agg: pd.DataFrame, k: int = 5, rounds: int = 5, windows_per_year: int = 8 * 365,
                    measure_path: str | None = None) -> pd.DataFrame:
    """agg: aggregate_seeds() output (needs tx_per_year, retrains_per_year, protocol, policy).

    measure_path: JSON file holding the Merkle timings. When it exists its numbers are used, so the
    microsecond figures stay those of the machine that ran the study even if the tables are rebuilt
    elsewhere; when it does not, the timings are measured now and written there."""
    import json, os
    rows = []
    need = sorted({1, k + 1, rounds * (k + 1)})
    meas = {}
    if measure_path and os.path.exists(measure_path):
        meas = {int(kk): v for kk, v in json.load(open(measure_path)).items()}
    for b in need:
        if b not in meas:
            meas[b] = _measure(b)
    if measure_path:
        with open(measure_path, "w") as f:
            json.dump({str(kk): v for kk, v in sorted(meas.items())}, f, indent=1)
    for _, r in agg.iterrows():
        tx_rec = r["tx_per_year"]
        if r["protocol"] in ("fedavg", "lpra"):
            n_rounds = tx_rec / (k + 1)
            designs = [("per-record", tx_rec, 1), ("per-round", n_rounds, k + 1),
                       ("per-event", r["retrains_per_year"], rounds * (k + 1))]
        else:
            designs = [("per-record", tx_rec, 1), ("per-event", r["retrains_per_year"], max(int(round(tx_rec / max(r["retrains_per_year"], 1e-9))), 1))]
        for name, tx, b in designs:
            if b not in meas:
                meas[b] = _measure(b)
                if measure_path:
                    with open(measure_path, "w") as f:
                        json.dump({str(kk): v for kk, v in sorted(meas.items())}, f, indent=1)
            m = meas[b]
            rows.append(dict(protocol=r["protocol"], policy=r["policy"], anchoring=name, batch=b,
                             tx_per_year=tx, ledger_gb_per_year=tx * BYTES_PER_TX / 1e9,
                             ledger_reduction=1 - tx / tx_rec if tx_rec else 0.0,
                             proof_bytes=m["proof_bytes"], merkle_cpu_us_per_batch=m["root_us"] + m["proof_us"],
                             verify_cpu_us=m["verify_us"]))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    for b in (1, 6, 30, 150, 1000):
        print(_measure(b))
