"""Reviewer 3, point 4: the tamper test only modifies a payload; it does not
test deletion or an adversary who can re-sign.  This runs five attacks
against the emulated ledger's verify_chain(), each with the realistic
attacker capability stated, and reports which are detected.

  1  modify payload            (the submitted test)          no keys
  2  delete one tx from a block                              no keys
  3  truncate the chain (drop the last block)                no keys
  4  delete a tx AND recompute merkle + header + re-sign     with a
     with fewer than quorum validator keys                   minority of keys
  5  same as 4, but with >= quorum validator keys             colluding
                                                             majority

Expected: 1-4 detected; 5 NOT detected -- and that is the honest-majority
bound the ledger inherits from PoA.  The point of running 5 is to state the
bound as a measurement rather than leave it implicit.
"""
import os, sys, json, copy, hmac, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poc.blockchain import PermissionedLedger, merkle_root, sha256

def fresh():
    led = PermissionedLedger(members=["Gateway-Healthcare"])
    for i in range(120):
        led.submit(dict(kind="ALERT", district="Healthcare", attack="ransomware", i=i),
                   submitter="Gateway-Healthcare")
    led.flush()
    ok, _ = led.verify_chain(); assert ok
    return led

def resign(led, blk_idx, keys_available):
    """Rebuild block blk_idx's merkle root, header hash and signatures using
    only the validator keys the attacker holds; leave other signatures stale."""
    b = led.chain[blk_idx]
    b.merkle = merkle_root([t.hash() for t in b.txs])
    hdr = b.header()
    for v in keys_available:
        b.signatures[v] = hmac.new(led.keys[v], hdr.encode(), hashlib.sha256).hexdigest()
    b.hash = sha256(hdr + json.dumps(b.signatures, sort_keys=True))
    # re-link every later block to the new hash and re-sign them the same way
    for j in range(blk_idx + 1, len(led.chain)):
        led.chain[j].prev_hash = led.chain[j - 1].hash
        hdr = led.chain[j].header()
        for v in keys_available:
            led.chain[j].signatures[v] = hmac.new(led.keys[v], hdr.encode(), hashlib.sha256).hexdigest()
        led.chain[j].hash = sha256(hdr + json.dumps(led.chain[j].signatures, sort_keys=True))

if __name__ == "__main__":
    results = []
    n_val = len(PermissionedLedger().validators)
    quorum = 2 * n_val // 3 + 1
    print(f"validators={n_val}  quorum={quorum}\n")

    # 1 modify (as submitted)
    led = fresh(); led.chain[2].txs[0].payload["attack"] = "normal"
    ok, msg = led.verify_chain(); results.append(("1 modify payload", "no keys", not ok, msg))

    # 2 delete a tx
    led = fresh(); del led.chain[2].txs[0]
    ok, msg = led.verify_chain(); results.append(("2 delete one tx", "no keys", not ok, msg))

    # 3 truncate chain
    led = fresh(); n0 = len(led.chain); led.chain.pop()
    ok, msg = led.verify_chain()
    # truncation leaves a valid shorter chain; detection needs an external anchor
    results.append(("3 truncate last block", "no keys", not ok,
                    f"{msg}  (chain shrank {n0}->{len(led.chain)}; undetectable without an external height anchor)"))

    # 4 delete + re-sign with a MINORITY of keys
    led = fresh(); del led.chain[2].txs[0]
    resign(led, 2, led.validators[:quorum - 1])
    ok, msg = led.verify_chain(); results.append(("4 delete + re-sign, minority keys", f"{quorum-1}/{n_val} keys", not ok, msg))

    # 5 delete + re-sign with a QUORUM of keys
    led = fresh(); del led.chain[2].txs[0]
    resign(led, 2, led.validators[:quorum])
    ok, msg = led.verify_chain(); results.append(("5 delete + re-sign, quorum keys", f"{quorum}/{n_val} keys", not ok, msg))

    print(f"{'attack':38} {'attacker holds':>16}  {'detected':>8}  message")
    for name, keys, det, msg in results:
        print(f"{name:38} {keys:>16}  {str(det):>8}  {msg[:70]}")
    json.dump([dict(attack=a, keys=k, detected=d, msg=m) for a, k, d, m in results],
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tamper_extended.json"), "w"), indent=1)
    print("\nwrote tamper_extended.json")
