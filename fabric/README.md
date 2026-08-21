# Experiment E13 — the same anchoring logic on a real Hyperledger Fabric network

Goal: replace the emulated ledger of Section 5.5 with Hyperledger Fabric v2.5 (two organisations,
Raft ordering) and measure `AnchorAlert` throughput, latency, ledger growth and membership rejection.
This fills Section 5.10 and Table 14 of the manuscript.

Everything runs on the laptop. Budget ~1–2 hours, most of it the one-off Docker/WSL install.

---

## 0. Prerequisites (Windows 11 → use WSL 2; the Fabric scripts are bash)

```powershell
wsl --install -d Ubuntu          # skip if WSL 2 + Ubuntu already installed
wsl --status                     # must say: Default Version: 2
```

Install **Docker Desktop**, then Settings → Resources → WSL integration → enable for *Ubuntu*.
Verify from inside Ubuntu:

```bash
docker version        # both Client and Server must answer
docker compose version
```

Then, inside Ubuntu:

```bash
sudo apt update && sudo apt install -y curl git jq
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v               # v20.x
```

## 1. Fabric samples + binaries

```bash
cd ~
curl -sSLO https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh
chmod +x install-fabric.sh
./install-fabric.sh --fabric-version 2.5.9 docker samples binary
```

Checkpoint: `ls ~/fabric-samples/test-network/network.sh` exists.

## 2. Bring up the network (2 orgs + Raft orderer + CAs)

```bash
cd ~/fabric-samples/test-network
./network.sh up createChannel -c mychannel -ca
docker ps --format '{{.Names}}'      # expect peer0.org1, peer0.org2, orderer, 3 CAs
```

If a port is busy, `./network.sh down` and retry.

## 3. Deploy the CityAnchor chaincode

Copy this repository's `fabric/chaincode` into the Linux filesystem first (much faster than /mnt/c):

```bash
cp -r /mnt/c/Users/LENOVO/Downloads/Smart_City_MDPI_journal/run/fabric ~/cityanchor
cd ~/fabric-samples/test-network
./network.sh deployCC -ccn cityanchor -ccp ~/cityanchor/chaincode -ccl javascript
```

This packages, installs on both peers, approves for both orgs and commits with the default
majority endorsement policy. It takes 3–5 minutes (it runs `npm install` inside the builder).

Checkpoint — a single invoke should return the anchored record:

```bash
export PATH=${PWD}/../bin:$PATH
export FABRIC_CFG_PATH=$PWD/../config/
source ./scripts/envVar.sh; setGlobals 1
peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --tls --cafile "${PWD}/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem" \
  -C mychannel -n cityanchor \
  --peerAddresses localhost:7051 --tlsRootCertFiles "${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
  --peerAddresses localhost:9051 --tlsRootCertFiles "${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" \
  -c '{"function":"AnchorAlert","Args":["alert-1","Transport","dt8","abc123","1"]}'
```

## 4. Benchmark (this is the number Table 14 needs)

```bash
cd ~/cityanchor/bench
npm install
FABRIC_SAMPLES=~/fabric-samples node bench.mjs 2000 20
FABRIC_SAMPLES=~/fabric-samples node bench.mjs 2000 50
```

Each run prints JSON and also writes `bench_result_conc20.json` / `bench_result_conc50.json`.
Expect roughly 100–1000 tx/s and 0.5–3 s per transaction: Fabric commits through endorsement +
ordering + validation, so it is one to two orders of magnitude slower than the in-process emulation,
which is exactly the comparison the paper wants to make.

## 5. Ledger size and membership rejection

```bash
# ledger bytes after the benchmark
docker exec peer0.org1.example.com du -sb /var/hyperledger/production/ledgersData

# a client whose identity is NOT in the channel must be refused
cd ~/fabric-samples/test-network
source ./scripts/envVar.sh; setGlobals 2         # Org2 identity, but query Org1's peer only
peer chaincode query -C mychannel -n cityanchor -c '{"function":"GetAlert","Args":["alert-1"]}' 2>&1 | tail -2
```

Also record the block-cutting parameters in force, since they set the latency floor:

```bash
grep -A4 "BatchTimeout\|MaxMessageCount" ~/fabric-samples/test-network/configtx/configtx.yaml | head -20
```

## 6. Send back

* `bench_result_conc20.json`, `bench_result_conc50.json`
* the `du -sb` number and the number of alerts anchored when it was taken
* the BatchTimeout / MaxMessageCount values
* the exact error text from the rejected identity
* `docker ps --format '{{.Image}}'` (to cite the exact Fabric image versions)

## 7. Tear down

```bash
cd ~/fabric-samples/test-network && ./network.sh down
```

---

## If something breaks

* `deployCC` fails at `npm install` → the builder container needs internet; check Docker DNS, or retry.
* `bench.mjs` cannot find credentials → check `FABRIC_SAMPLES` points at the directory that contains
  `test-network/organizations/...`.
* gRPC `UNAVAILABLE` → the peer is not on `localhost:7051` from where you run node; run the bench
  inside the same WSL distro that hosts Docker.
* Everything else → send me the full error; the fallback is to report Fabric qualitatively and keep
  the emulation as the quantitative result, which costs about 2 percentage points of reviewer goodwill.
