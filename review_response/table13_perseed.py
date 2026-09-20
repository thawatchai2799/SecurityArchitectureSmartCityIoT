"""Table 13 (E9, district part), per seed: K in {5,10,20,50}, 20% Byzantine (n_att = K//5) under scale,
FedAvg vs LPRA v2, seeds 42-44, 60k sample, 10 rounds, repo v2.1 code (orphan-free partition,
district-local init).  Per-seed values kept so the s.d. can be verified; the
mean of the last three rounds and the population s.d. over seeds are what Table 13
and results/extC_districts_scaling.csv report."""
import os, sys, json, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "table13_perseed.json")
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split
ton = load_ton_iot(sample=60000)
Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]
out=[]
for K in (5,10,20,50):
    for agg in ("fedavg","lpra"):
        for attack,n_att in (("none",0),("scale",max(1,K//5))):
            for seed in (42,43,44):
                t0=time.time()
                r=byzantine.run_byzantine(X,yb,ym,Xt,yt,k=K,rounds=10,regime="non-iid",seed=seed,attack=attack,n_att=n_att,aggregator=agg,lpra_version="v2")
                row=dict(K=K,agg=agg,attack=attack,n_att=n_att,seed=seed,final_f1=round(r["final_f1"],4),last3=round(r["mean_last3_f1"],4),
                         hon=r["honest_rejections"],att=r["attacker_rejections"],caught=r["rounds_all_attackers_rejected"])
                out.append(row); print(row, f"{time.time()-t0:.0f}s", flush=True)
                json.dump(out,open(OUT,"w"),indent=1)
