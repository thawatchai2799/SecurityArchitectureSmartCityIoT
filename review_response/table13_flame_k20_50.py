"""Extends table13_perseed.py's protocol (Table 13 / E9, district scaling) to add FLAME at the
district counts where its own clustering has enough clients to be meaningful: K in {20,50},
20% Byzantine (n_att = K // 5) under the "scale" attack, plus the no-attack cost comparison.
Same data, split, rounds, seeds and non-IID regime as table13_perseed.py so the numbers are
directly comparable to the published Table 13 rows for FedAvg and LPRA v2 at the same K.
FLAME implementation: flame_impl.py (Algorithm 1 of Nguyen et al., USENIX Security 2022;
cosine distance on the local models, HDBSCAN with min_cluster_size = floor(K/2)+1,
median-norm clipping over all K, equal-weight mean, Gaussian noise sigma = lambda * S_t).
Usage: python table13_flame_k20_50.py [--lam 0.01]; outputs carry a lam<lam> tag, and with the
default lambda are also written to the untagged files the manuscript (Table S11) is built from.
Earlier runs kept: *_sklearn_defaults.json, *_v2.1.0.json (cosine on updates, lambda = 0.001).
"""
import os, sys, json, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "table13_flame_k20_50.json")
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

import argparse
import flame_impl
from flame_impl import CLUSTER_LOG
ap = argparse.ArgumentParser(); ap.add_argument("--lam", type=float, default=flame_impl.LAMBDA_DEFAULT)
ARGS = ap.parse_args(); LAM = ARGS.lam
flame_impl.install(byzantine, lam=LAM)
TAG = f"lam{LAM:g}"

ton = load_ton_iot(sample=60000)
Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

out = []
t_start = time.time()
for K in (20, 50):
    for agg in ("fedavg", "flame", "lpra"):
        for attack, n_att in (("none", 0), ("scale", max(1, K // 5))):
            for seed in (42, 43, 44):
                t0 = time.time()
                r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid",
                                            seed=seed, attack=attack, n_att=n_att, aggregator=agg,
                                            lpra_version="v2")
                row = dict(K=K, agg=agg, attack=attack, n_att=n_att, seed=seed,
                          final_f1=round(r["final_f1"], 4), last3=round(r["mean_last3_f1"], 4), last3_raw=float(r["mean_last3_f1"]),
                          hon=r["honest_rejections"], att=r["attacker_rejections"],
                          caught=r["rounds_all_attackers_rejected"])
                if agg == "flame":
                    log = CLUSTER_LOG[-10:]   # the 10 rounds just run
                    row["flame_rounds_no_cluster"] = sum(1 for e in log if e["n_clusters"] == 0)
                    row["flame_rounds_cluster_kept_all"] = sum(1 for e in log if e["n_clusters"] > 0 and e["kept"] == K)
                    row["flame_rounds_cluster_excluded_some"] = sum(1 for e in log if e["n_clusters"] > 0 and e["kept"] < K)
                out.append(row)
                print(row, f"{time.time()-t0:.1f}s", flush=True)
                json.dump(out, open(OUT.replace(".json", f"_{TAG}.json"), "w"), indent=1)
print(f"\nTOTAL TIME: {time.time()-t_start:.1f}s over {len(out)} runs")
json.dump(CLUSTER_LOG, open(OUT.replace(".json", f"_clusterlog_{TAG}.json"), "w"))
if abs(LAM - flame_impl.LAMBDA_DEFAULT) < 1e-12:
    json.dump(out, open(OUT, "w"), indent=1)
    json.dump(CLUSTER_LOG, open(OUT.replace(".json", "_clusterlog.json"), "w"))
print("wrote", OUT.replace(".json", f"_{TAG}.json"))

# ---- summary (the rows Table S11 is built from): per K x aggregator x attack over the three seeds ----
summ = []
for K in (20, 50):
    for agg in ("fedavg", "flame", "lpra"):
        for attack in ("none", "scale"):
            rs = [r for r in out if (r["K"], r["agg"], r["attack"]) == (K, agg, attack)]
            f1 = np.array([r["last3_raw"] for r in rs])
            summ.append(dict(K=K, aggregator=agg, attack=attack, n_att=rs[0]["n_att"],
                             f1=round(float(f1.mean()), 4), f1_sd=round(float(f1.std()), 4),
                             honest_rej=round(float(np.mean([r["hon"] for r in rs])), 2),
                             att_rej_sum=int(sum(r["att"] for r in rs)),
                             caught_mean=round(float(np.mean([r["caught"] for r in rs])), 2)))
json.dump(summ, open(OUT.replace(".json", f"_summary_{TAG}.json"), "w"), indent=1)
if abs(LAM - flame_impl.LAMBDA_DEFAULT) < 1e-12:
    json.dump(summ, open(OUT.replace(".json", "_summary.json"), "w"), indent=1)
for s in summ:
    print(s)
