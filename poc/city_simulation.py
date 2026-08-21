"""
city_simulation.py
------------------
Layer 1 + 4: replays REAL flows (TON_IoT) through K simulated district gateways,
each running the edge IDS model.  Alerts are hashed and anchored on the ledger,
then forwarded to the Cloud Security Orchestrator, which
    * correlates alerts across districts (e.g. city-wide DDoS campaign),
    * verifies every alert against the ledger before trusting it,
    * measures end-to-end detection-to-record latency.
Also emulates two attacks *on the security system itself*:
    (a) an insider edits an alert in a district's local DB  -> ledger detects it
    (b) a rogue node tries to submit alerts without enrolment -> rejected
"""
from __future__ import annotations
import time
import json
import numpy as np
from collections import defaultdict, Counter
from .blockchain import PermissionedLedger, sha256, verify_proof
from .federated import DISTRICTS


class DistrictGateway:
    def __init__(self, name, model, ledger):
        self.name, self.model, self.ledger = name, model, ledger
        self.local_db = []          # what the district keeps (evidence)
        self.stats = Counter()
        self.latencies = []

    def process(self, X_flow: np.ndarray, flow_meta: dict):
        t0 = time.perf_counter()
        pred = int(self.model.predict(X_flow.reshape(1, -1))[0])
        self.stats["flows"] += 1
        if pred == 1:
            evidence_hash = sha256(json.dumps(flow_meta, sort_keys=True))
            alert = dict(kind="ALERT", district=self.name, evidence_hash=evidence_hash,
                         model=type(self.model).__name__, ts=time.time())
            tx_id = self.ledger.submit(alert, submitter=f"Gateway-{self.name}")
            self.local_db.append(dict(tx_id=tx_id, alert=alert, meta=flow_meta))
            self.stats["alerts"] += 1
            self.latencies.append(time.perf_counter() - t0)
            return alert
        self.latencies.append(time.perf_counter() - t0)
        return None


class CloudOrchestrator:
    def __init__(self, ledger):
        self.ledger = ledger
        self.alerts = []
        self.by_district = defaultdict(list)

    def ingest(self, alert):
        self.alerts.append(alert); self.by_district[alert["district"]].append(alert)

    def correlate(self, window_s: float = 5.0, min_districts: int = 3):
        """Very simple cross-district correlation: many alerts in many districts in a
        short window => city-wide campaign."""
        if not self.alerts:
            return []
        ts = np.array([a["ts"] for a in self.alerts]); order = np.argsort(ts)
        campaigns, i = [], 0
        while i < len(order):
            j = i
            while j < len(order) and ts[order[j]] - ts[order[i]] <= window_s:
                j += 1
            ds = {self.alerts[k]["district"] for k in order[i:j]}
            if len(ds) >= min_districts:
                campaigns.append(dict(start=float(ts[order[i]]), n_alerts=j - i, districts=sorted(ds)))
                i = j
            else:
                i += 1
        return campaigns

    def audit_district(self, gw: DistrictGateway) -> dict:
        """Verify each alert in the district's local DB against the ledger via Merkle proofs."""
        index = {}
        for b in self.ledger.chain[1:]:
            for pos, t in enumerate(b.txs):
                index[t.tx_id] = (b.index, pos)
        ok = bad = 0
        for rec in gw.local_db:
            bidx, pos = index[rec["tx_id"]]
            tx_hash, proof, root = self.ledger.proof_for(bidx, pos)
            # recompute what the district *claims* the alert was
            claimed = self.ledger.chain[bidx].txs[pos]
            claimed_hash = sha256(json.dumps(dict(tx_id=claimed.tx_id, submitter=claimed.submitter,
                                                  payload=rec["alert"], ts=claimed.ts), sort_keys=True))
            if verify_proof(claimed_hash, proof, root):
                ok += 1
            else:
                bad += 1
        return dict(district=gw.name, verified=ok, tampered=bad)


def run_city(model, X: np.ndarray, y_true: np.ndarray, y_type: np.ndarray, k: int = 5,
             n_flows: int = 20000, seed: int = 42, block_size: int = 50) -> dict:
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(y_true), min(n_flows, len(y_true)), replace=False)
    enrolled = [f"Gateway-{DISTRICTS[i]}" for i in range(k)]
    ledger = PermissionedLedger(block_size=block_size, block_interval_s=0.5, members=enrolled)
    gws = [DistrictGateway(DISTRICTS[i], model, ledger) for i in range(k)]
    cloud = CloudOrchestrator(ledger)
    # assign flows to districts (round-robin, deterministic)
    tp = fp = fn = tn = 0
    t0 = time.perf_counter()
    for n, i in enumerate(idx):
        gw = gws[n % k]
        meta = dict(seq=int(i), type=str(y_type[i]))
        alert = gw.process(X[i], meta)
        if alert:
            cloud.ingest(alert)
        pred = 1 if alert else 0
        if pred and y_true[i]: tp += 1
        elif pred and not y_true[i]: fp += 1
        elif not pred and y_true[i]: fn += 1
        else: tn += 1
    ledger.flush(); wall = time.perf_counter() - t0
    campaigns = cloud.correlate()

    # ---- (a) insider tampering in a district DB ------------------------ #
    victim = gws[0]
    if victim.local_db:
        victim.local_db[0]["alert"]["district"] = "Water"      # forge attribution
    audit = [cloud.audit_district(g) for g in gws]
    # ---- (b) rogue node: an un-enrolled host that *impersonates* a gateway name  #
    rogue_rejected = {}
    for impostor in ("RogueNode", "Gateway-Fake", "Gateway-transport"):
        try:
            ledger.submit(dict(kind="ALERT", district="Fake"), submitter=impostor)
            rogue_rejected[impostor] = False
        except PermissionError:
            rogue_rejected[impostor] = True
    intact, msg = ledger.verify_chain()
    lat = np.concatenate([g.latencies for g in gws]) * 1e3
    return dict(n_flows=int(len(idx)), districts=k, wall_time_s=wall,
                flows_per_s=len(idx) / wall,
                detection=dict(tp=tp, fp=fp, fn=fn, tn=tn,
                               precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1),
                               fpr=fp / max(fp + tn, 1)),
                per_flow_latency_ms=dict(mean=float(lat.mean()), p95=float(np.percentile(lat, 95)),
                                         p99=float(np.percentile(lat, 99))),
                alerts=len(cloud.alerts), campaigns_detected=len(campaigns),
                # NOTE: this correlation runs on wall-clock timestamps of the replay and is
                # only a smoke test; the paper's timing analysis is Exp-14 (run_extended.py),
                # which replays the same flows on a simulated clock.
                campaign_examples=campaigns[:3], ledger=ledger.summary(),
                ledger_intact=intact, audit=audit, rogue_node_rejected=rogue_rejected,
                per_district={g.name: dict(g.stats) for g in gws})
