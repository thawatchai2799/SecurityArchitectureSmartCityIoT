"""Exp-3 (Table 6) and Exp-9 (Tables 7, 8) re-run under the v2.1 code (district-local
initialisation), full TON_IoT, seed 42, exactly as run_poc.py runs them.  Used to check
which K = 5 numbers the initialisation change touched: none of the LPRA or no-attack
numbers; undefended FedAvg under the Gaussian-noise attack moved (0.686 -> 0.780)."""
import os,sys,json,numpy as np,pandas as pd,warnings; warnings.filterwarnings("ignore")
R=os.path.join(os.path.dirname(os.path.abspath(__file__)),".."); sys.path.insert(0,R)
from poc import data_loader as dl, federated, blockchain, robust_fl
from sklearn.model_selection import train_test_split
ton=dl.load_ton_iot(sample=None,seed=42)
Xn,yb,ym=ton["X_native"].values.astype(np.float32),ton["y_bin"],ton["y_multi"]
idx_tr,idx_te=train_test_split(np.arange(len(yb)),test_size=0.3,stratify=ym,random_state=42)
out={}
print("[Exp-3]",flush=True)
fl_ledger=blockchain.PermissionedLedger(block_size=5)
for regime in ("iid","non-iid"):
    r=federated.run_federated(Xn[idx_tr],yb[idx_tr],ym[idx_tr],Xn[idx_te],yb[idx_te],k=5,rounds=15,local_epochs=2,regime=regime,seed=42,ledger=fl_ledger if regime=="non-iid" else None)
    out["exp3_"+regime]={k:v for k,v in r.items() if k in("federated_f1","centralised_f1","local_only_f1_mean","raw_bytes_not_shared","weight_bytes_per_round")}
    print(regime,out["exp3_"+regime],flush=True)
print("[Exp-9]",flush=True)
rl=blockchain.PermissionedLedger(block_size=5)
for attack in ("none","scale","flip","noise"):
    for defense in ((False,True) if attack!="none" else (True,)):
        r=robust_fl.run_robust_fl(Xn[idx_tr],yb[idx_tr],ym[idx_tr],Xn[idx_te],yb[idx_te],k=5,rounds=15,local_epochs=2,regime="non-iid",seed=42,attack=attack,byzantine=None if attack=="none" else 0,defense=defense,ledger=rl if defense else None,personalise=(attack=="none"))
        key=f"{attack}/{'LPRA' if defense else 'plain FedAvg'}"
        out["exp9_"+key]={k:v for k,v in r.items() if k in("global_f1","byzantine_caught_rounds","false_quarantines","personalised","screen_log","first_flag")}
        print(key,r["global_f1"],r["byzantine_caught_rounds"],{k:r.get(k) for k in r if k not in("history","personalised","global_f1","byzantine_caught_rounds")} ,flush=True)
        if "personalised" in r:
            for d in r["personalised"]: print("   ",d,flush=True)
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"exp3_exp9_rerun.json"),"w"),indent=1,default=str)
