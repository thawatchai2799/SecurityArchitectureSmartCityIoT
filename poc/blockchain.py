"""
blockchain.py
-------------
Layer 3: a *permissioned* (consortium) ledger shared by city agencies.
It is deliberately minimal but faithful to what a Hyperledger-Fabric-style
deployment would provide, so that overhead numbers are meaningful:

    * Validators   : a fixed set of city agencies (Proof-of-Authority, round-robin
                     block proposer, block accepted when > 2/3 validators sign).
    * Transactions : ONLY hashes / metadata are stored on-chain
                       - IDS alert digests (district, type, hash of evidence flow)
                       - global model-update hashes (federated round anchoring)
                     Raw traffic and personal data stay off-chain (privacy by design).
    * Blocks       : header {index, prev_hash, merkle_root, timestamp, proposer,
                     signatures[]} + tx list.  Merkle proofs allow a single alert
                     to be verified without downloading the whole block.
    * Tampering    : verify_chain() detects any modification of a past alert.

Signatures are HMAC-SHA256 with per-agency keys (stand-in for ECDSA/X.509 MSP).
Metrics: tx throughput, block latency, on-chain bytes vs. plain DB bytes.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import time
import secrets
import copy
from dataclasses import dataclass, field, asdict

AGENCIES = ["MunicipalityIT", "CityPolice", "ElectricUtility", "WaterAuthority", "University"]


def sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def merkle_root(tx_hashes: list[str]) -> str:
    if not tx_hashes:
        return sha256("")
    layer = tx_hashes[:]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]


def merkle_proof(tx_hashes: list[str], index: int) -> list[tuple[str, str]]:
    proof, layer, i = [], tx_hashes[:], index
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        sib = i ^ 1
        proof.append((layer[sib], "L" if sib < i else "R"))
        layer = [sha256(layer[j] + layer[j + 1]) for j in range(0, len(layer), 2)]
        i //= 2
    return proof


def verify_proof(tx_hash: str, proof, root: str) -> bool:
    h = tx_hash
    for sib, side in proof:
        h = sha256(sib + h) if side == "L" else sha256(h + sib)
    return h == root


@dataclass
class Tx:
    tx_id: str
    submitter: str
    payload: dict
    ts: float

    def hash(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True))


@dataclass
class Block:
    index: int
    prev_hash: str
    proposer: str
    ts: float
    txs: list[Tx]
    merkle: str = ""
    signatures: dict = field(default_factory=dict)
    hash: str = ""

    def header(self) -> str:
        return json.dumps(dict(index=self.index, prev_hash=self.prev_hash, proposer=self.proposer,
                               ts=self.ts, merkle=self.merkle), sort_keys=True)


class PermissionedLedger:
    def __init__(self, validators=AGENCIES, block_size: int = 50, block_interval_s: float = 1.0,
                 members=None):
        """`members` is the enrolment list (Fabric MSP stand-in): every principal
        allowed to *submit* transactions.  Validators, the cloud aggregator and any
        explicitly enrolled district gateway are members; anything else is refused,
        including a node that merely names itself "Gateway-<something>"."""
        self.validators = list(validators)
        self.members = set(self.validators) | {"CloudAggregator"} | set(members or [])
        self.keys = {v: secrets.token_bytes(32) for v in self.validators}   # MSP stand-in
        self.block_size, self.block_interval = block_size, block_interval_s
        self.chain: list[Block] = []
        self.mempool: list[Tx] = []
        self.last_cut = time.perf_counter()
        self.metrics = dict(tx_submitted=0, blocks=0, block_latencies=[], tx_latencies=[])
        self._tx_submit_ts: dict[str, float] = {}
        self.plain_db_bytes = 0
        g = Block(0, "0" * 64, "genesis", time.time(), [])
        g.merkle = merkle_root([]); g.hash = sha256(g.header()); self.chain.append(g)

    # ------------------------------------------------------------------ #
    def submit(self, payload: dict, submitter: str) -> str:
        if submitter not in self.members:
            raise PermissionError(f"{submitter} is not an enrolled member of this channel")
        tx = Tx(secrets.token_hex(8), submitter, copy.deepcopy(payload), time.time())  # ledger keeps its own immutable copy
        self.mempool.append(tx); self.metrics["tx_submitted"] += 1
        self._tx_submit_ts[tx.tx_id] = time.perf_counter()
        self.plain_db_bytes += len(json.dumps(payload))     # what a plain DB would store
        if len(self.mempool) >= self.block_size or \
                time.perf_counter() - self.last_cut >= self.block_interval:
            self._cut_block()
        return tx.tx_id

    def flush(self):
        if self.mempool:
            self._cut_block()

    def _sign(self, v: str, header: str) -> str:
        return hmac.new(self.keys[v], header.encode(), hashlib.sha256).hexdigest()

    def _cut_block(self):
        t0 = time.perf_counter()
        prev = self.chain[-1]
        proposer = self.validators[len(self.chain) % len(self.validators)]     # PoA round-robin
        blk = Block(prev.index + 1, prev.hash, proposer, time.time(), self.mempool)
        blk.merkle = merkle_root([t.hash() for t in blk.txs])
        hdr = blk.header()
        for v in self.validators:                        # every validator endorses
            blk.signatures[v] = self._sign(v, hdr)
        quorum = 2 * len(self.validators) // 3 + 1
        assert len(blk.signatures) >= quorum, "no quorum"
        blk.hash = sha256(hdr + json.dumps(blk.signatures, sort_keys=True))
        self.chain.append(blk); self.mempool = []; self.last_cut = time.perf_counter()
        dt = time.perf_counter() - t0
        self.metrics["blocks"] += 1; self.metrics["block_latencies"].append(dt)
        now = time.perf_counter()
        for t in blk.txs:
            self.metrics["tx_latencies"].append(now - self._tx_submit_ts.pop(t.tx_id))

    # ------------------------------------------------------------------ #
    def verify_chain(self) -> tuple[bool, str]:
        for i in range(1, len(self.chain)):
            b, p = self.chain[i], self.chain[i - 1]
            if b.prev_hash != p.hash:
                return False, f"block {i}: broken prev-hash link"
            if b.merkle != merkle_root([t.hash() for t in b.txs]):
                return False, f"block {i}: merkle root mismatch (tx tampered)"
            hdr = b.header()
            ok = sum(hmac.compare_digest(self._sign(v, hdr), s) for v, s in b.signatures.items())
            if ok < 2 * len(self.validators) // 3 + 1:
                return False, f"block {i}: signature quorum failed"
            if b.hash != sha256(hdr + json.dumps(b.signatures, sort_keys=True)):
                return False, f"block {i}: header hash mismatch"
        return True, "chain intact"

    def proof_for(self, block_index: int, tx_pos: int):
        b = self.chain[block_index]
        hashes = [t.hash() for t in b.txs]
        return b.txs[tx_pos].hash(), merkle_proof(hashes, tx_pos), b.merkle

    def onchain_bytes(self) -> int:
        return sum(len(json.dumps(dict(hdr=b.header(), sig=b.signatures,
                                        txs=[asdict(t) for t in b.txs]))) for b in self.chain)

    def summary(self) -> dict:
        m = self.metrics
        return dict(validators=len(self.validators), members=len(self.members), quorum=2 * len(self.validators) // 3 + 1,
                    tx_submitted=m["tx_submitted"], blocks=m["blocks"],
                    avg_block_commit_ms=1e3 * (sum(m["block_latencies"]) / max(len(m["block_latencies"]), 1)),
                    avg_tx_confirm_ms=1e3 * (sum(m["tx_latencies"]) / max(len(m["tx_latencies"]), 1)),
                    onchain_bytes=self.onchain_bytes(), plain_db_bytes=self.plain_db_bytes,
                    storage_overhead_x=self.onchain_bytes() / max(self.plain_db_bytes, 1))


# ---------------------------------------------------------------------- #
def throughput_benchmark(n_tx: int = 5000, block_size: int = 100) -> dict:
    led = PermissionedLedger(block_size=block_size, block_interval_s=1e9,
                             members=["Gateway-Transport"])
    t0 = time.perf_counter()
    for i in range(n_tx):
        led.submit(dict(kind="ALERT", district="Transport", attack="ddos", flow_hash=sha256(str(i))),
                   submitter="Gateway-Transport")
    led.flush(); dt = time.perf_counter() - t0
    ok, msg = led.verify_chain()
    # tamper test: silently rewrite one already-committed alert
    victim = min(3, len(led.chain) - 1)
    assert victim >= 1 and led.chain[victim].txs, "need at least one non-genesis block"
    led.chain[victim].txs[0].payload["attack"] = "normal"
    tampered_ok, tampered_msg = led.verify_chain()
    s = led.summary()
    s.update(dict(tx_per_s=n_tx / dt, verify_intact=ok, tampered_block=victim,
                  tamper_detected=not tampered_ok, tamper_msg=tampered_msg))
    return s


if __name__ == "__main__":
    print(json.dumps(throughput_benchmark(), indent=2))
