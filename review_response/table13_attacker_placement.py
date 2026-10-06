"""Round 2, Reviewer 1, Comment 3: Table 13 with the Byzantine districts drawn at random
instead of always being districts 0..n_att-1.

Protocol otherwise identical to table13_perseed.py (E9 district part): K in {5,10,20,50},
20% Byzantine (n_att = max(1, K//5)) under the scaling attack, FedAvg and LPRA v2,
seeds 42-44, 60k-flow sample, 10 rounds, orphan-free partition, district-local init.

Placements.  K = 5 has only five possible single-attacker placements, so all five are
run (placement 0 is the published one).  For K = 10, 20, 50 five placements are drawn
without replacement from range(K) with an independent generator (seed 1000 + p); placement
0 is again the published fixed set range(n_att), so the published rows are one of the
five.  Each placement is run under the same three training seeds as Table 13.

For every run the dominant attack families owned by the attacker districts are recorded
(poc.federated.partition's ownership rule: for K <= 9 family i -> district i % K, so at K = 5
districts 0-3 own two families each; for K > 9 district d -> family d % 9), so the reader can
see which family combinations were covered.

Usage: python table13_attacker_placement.py [--summarise-only]
Output: table13_attacker_placement.json (one row per run) and
table13_attacker_placement_summary.json (per K and aggregator: mean +/- s.d. over the
placements of the seed-averaged F1, attacker quarantine rate and honest rejections, plus
the published fixed-placement values for reference).
"""
import os, sys, json, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "table13_attacker_placement.json")
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

BENIGN = {"normal", "benign", "benigntraffic"}
N_PLACEMENTS = 5

ton = load_ton_iot(sample=60000)
Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]
types = sorted(set(ym) - BENIGN)          # 9 TON_IoT attack families

def families_of(K, districts):
    """Dominant families owned by the given districts under poc.federated.partition's
    orphan-free ownership rule: for K <= 9 family i -> district i % K (a district can own
    two families, e.g. district 0 owns backdoor and password at K = 5); for K > 9
    district d -> family types[d % 9]."""
    T = len(types); owners = {d: [] for d in range(K)}
    if K <= T:
        for i, t in enumerate(types): owners[i % K].append(str(t))
    else:
        for d in range(K): owners[d].append(str(types[d % T]))
    return sorted(set(f for d in districts for f in owners[d]))

def placements(K, n_att):
    if K == 5:
        return [[d] for d in range(5)]
    out = [list(range(n_att))]
    for p in range(1, N_PLACEMENTS):
        rng = np.random.default_rng(1000 + p)
        while True:
            cand = sorted(int(i) for i in rng.choice(K, size=n_att, replace=False))
            if cand not in out:
                out.append(cand); break
    return out

if __name__ == "__main__":
    rows = []; t_start = time.time()
    if "--summarise-only" in sys.argv:        # rebuild labels and summary from the stored runs, no training
        rows = json.load(open(OUT))
        for r in rows: r["families"] = families_of(r["K"], r["attackers"])
        json.dump(rows, open(OUT, "w"), indent=1)
    for K in ((5, 10, 20, 50) if "--summarise-only" not in sys.argv else ()):
        n_att = max(1, K // 5)
        for pi, att in enumerate(placements(K, n_att)):
            fams = families_of(K, att)
            for agg in ("fedavg", "lpra"):
                for seed in (42, 43, 44):
                    t0 = time.time()
                    r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid", seed=seed,
                                                attack="scale", n_att=n_att, aggregator=agg, lpra_version="v2",
                                                attacker_ids=att)
                    row = dict(K=K, n_att=n_att, placement=pi, attackers=att, families=fams, agg=agg, seed=seed,
                               final_f1=round(r["final_f1"], 4), last3=round(r["mean_last3_f1"], 4),
                               last3_raw=float(r["mean_last3_f1"]),
                               hon=r["honest_rejections"], att=r["attacker_rejections"],
                               caught=r["rounds_all_attackers_rejected"])
                    rows.append(row); print(row, f"{time.time()-t0:.0f}s", flush=True)
                    json.dump(rows, open(OUT, "w"), indent=1)
    print(f"TOTAL {time.time()-t_start:.0f}s over {len(rows)} runs")

    # ---- summary: seed-average per placement, then mean/sd over placements ----
    summ = []
    for K in (5, 10, 20, 50):
        n_att = max(1, K // 5)
        for agg in ("fedavg", "lpra"):
            per_pl = []
            for pi in range(len(placements(K, n_att))):
                rs = [r for r in rows if r["K"] == K and r["agg"] == agg and r["placement"] == pi]
                per_pl.append(dict(placement=pi, attackers=rs[0]["attackers"], families=rs[0]["families"],
                                   f1=float(np.mean([r["last3_raw"] for r in rs])),
                                   f1_sd_seeds=float(np.std([r["last3_raw"] for r in rs])),
                                   hon_mean=float(np.mean([r["hon"] for r in rs])),
                                   hon_min=int(min(r["hon"] for r in rs)), hon_max=int(max(r["hon"] for r in rs)),
                                   att_mean=float(np.mean([r["att"] for r in rs])),
                                   caught_mean=float(np.mean([r["caught"] for r in rs]))))
            f1s = np.array([p["f1"] for p in per_pl]); hons = np.array([p["hon_mean"] for p in per_pl])
            atts = np.array([p["att_mean"] for p in per_pl]); cau = np.array([p["caught_mean"] for p in per_pl])
            summ.append(dict(K=K, n_att=n_att, agg=agg, n_placements=len(per_pl),
                             honest_district_rounds=(K - n_att) * 10, attacker_rounds=n_att * 10,
                             f1_mean=round(float(f1s.mean()), 4), f1_sd=round(float(f1s.std()), 4),
                             f1_min=round(float(f1s.min()), 4), f1_max=round(float(f1s.max()), 4),
                             f1_fixed=round(float(per_pl[0]["f1"]), 4),
                             att_rej_mean=round(float(atts.mean()), 2), att_rej_min=float(atts.min()), att_rej_max=float(atts.max()),
                             caught_mean=round(float(cau.mean()), 2), caught_min=float(cau.min()),
                             hon_rej_mean=round(float(hons.mean()), 2), hon_rej_min=int(min(p["hon_min"] for p in per_pl)),
                             hon_rej_max=int(max(p["hon_max"] for p in per_pl)),
                             placements=per_pl))
    json.dump(summ, open(OUT.replace(".json", "_summary.json"), "w"), indent=1)
    for s in summ:
        print(f"K={s['K']:2} {s['agg']:7s} F1 {s['f1_mean']:.4f}±{s['f1_sd']:.4f} [{s['f1_min']:.4f},{s['f1_max']:.4f}] fixed {s['f1_fixed']:.4f} "
              f"| att_rej {s['att_rej_mean']}/{s['attacker_rounds']} (min {s['att_rej_min']}) caught {s['caught_mean']}/10 "
              f"| hon_rej {s['hon_rej_mean']} [{s['hon_rej_min']},{s['hon_rej_max']}]/{s['honest_district_rounds']}")
    print("wrote", OUT, "and summary")
