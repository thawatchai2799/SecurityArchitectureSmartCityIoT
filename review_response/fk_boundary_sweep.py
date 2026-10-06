"""Round 2, Reviewer 3, Point 3: where does LPRA's screen degrade or invert as the
Byzantine fraction f/K grows, at a fixed K larger than 5?

Sweep: K in {9, 11}; f in {2, 3, 4, 5, 6} (f/K from 0.18 to 0.67 at K = 9 and 0.18 to 0.55
at K = 11); attacks scale, flip, noise and the colluding adaptive attacker that defeated
LPRA v1 (opposite direction, strength s = 6, all attackers sending the same vector);
aggregators FedAvg (undefended reference) and LPRA v2; LPRA v1 is added for the adaptive
attack only, to show the inversion the v2 majority fallback was built against.
Seeds 42-44, 10 rounds, 60k-flow sample, orphan-free partition, district-local init,
fixed attacker placement (districts 0..f-1) as in Tables 9, 10 and 13.

K = 9 is the district count at which every district owns exactly one TON_IoT attack
family, so the sweep is the one Reviewer 3 suggested; K = 11 adds a count at which two of the nine
families are each split between two owner districts (district d owns family d % 9).

Output: fk_boundary_sweep.json (one row per run) and fk_boundary_sweep_summary.json
(per K, f, attack, aggregator: mean +/- s.d. over seeds of last-3-round F1, attacker
rejections, honest rejections, rounds with all attackers rejected, INCONCLUSIVE rounds).
"""
import os, sys, json, time, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fk_boundary_sweep.json")
from poc import byzantine
from poc.data_loader import load_ton_iot
from sklearn.model_selection import train_test_split

ton = load_ton_iot(sample=60000)
Xall, yall, mall = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
tr, te = train_test_split(np.arange(len(yall)), test_size=0.3, stratify=mall, random_state=42)
X, yb, ym, Xt, yt = Xall[tr], yall[tr], mall[tr], Xall[te], yall[te]

GRID_K = (9, 11); GRID_F = (2, 3, 4, 5, 6); SEEDS = (42, 43, 44)
ATTACKS = ("scale", "flip", "noise", "adaptive")

def configs():
    for K in GRID_K:
        for f in GRID_F:
            for attack in ATTACKS:
                aggs = [("fedavg", "v2"), ("lpra", "v2")] + ([("lpra", "v1")] if attack == "adaptive" else [])
                for agg, ver in aggs:
                    yield K, f, attack, agg, ver

if __name__ == "__main__":
    rows = []; t_start = time.time()
    for K, f, attack, agg, ver in configs():
        for seed in SEEDS:
            t0 = time.time()
            r = byzantine.run_byzantine(X, yb, ym, Xt, yt, k=K, rounds=10, regime="non-iid", seed=seed,
                                        attack=attack, n_att=f, aggregator=agg, lpra_version=ver,
                                        strength=6.0, direction="opposite")
            inconclusive = sum(1 for h in r["history"] if len(h["accepted"]) == 0)
            row = dict(K=K, f=f, fK=round(f / K, 3), attack=attack, agg=agg, version=ver if agg == "lpra" else None, seed=seed,
                       final_f1=round(r["final_f1"], 4), last3=round(r["mean_last3_f1"], 4), last3_raw=float(r["mean_last3_f1"]),
                       hon=r["honest_rejections"], att=r["attacker_rejections"], caught=r["rounds_all_attackers_rejected"],
                       inconclusive_rounds=int(inconclusive))
            rows.append(row); print(row, f"{time.time()-t0:.0f}s", flush=True)
            json.dump(rows, open(OUT, "w"), indent=1)
    print(f"TOTAL {time.time()-t_start:.0f}s over {len(rows)} runs")

    summ = []
    for K, f, attack, agg, ver in configs():
        rs = [r for r in rows if (r["K"], r["f"], r["attack"], r["agg"]) == (K, f, attack, agg) and (agg != "lpra" or r["version"] == ver)]
        f1 = np.array([r["last3_raw"] for r in rs])
        summ.append(dict(K=K, f=f, fK=round(f / K, 3), attack=attack, agg=agg + ("" if agg != "lpra" else f"_{ver}"),
                         f1_mean=round(float(f1.mean()), 4), f1_sd=round(float(f1.std()), 4),
                         att_rej=f"{min(r['att'] for r in rs)}-{max(r['att'] for r in rs)}/{f*10}",
                         hon_rej=f"{min(r['hon'] for r in rs)}-{max(r['hon'] for r in rs)}/{(K-f)*10}",
                         caught=f"{min(r['caught'] for r in rs)}-{max(r['caught'] for r in rs)}/10",
                         inconclusive=f"{min(r['inconclusive_rounds'] for r in rs)}-{max(r['inconclusive_rounds'] for r in rs)}/10"))
    json.dump(summ, open(OUT.replace(".json", "_summary.json"), "w"), indent=1)
    for s in summ:
        print(f"K={s['K']:2} f={s['f']} f/K={s['fK']:.2f} {s['attack']:8s} {s['agg']:8s} F1 {s['f1_mean']:.4f}±{s['f1_sd']:.4f} "
              f"att {s['att_rej']:9s} hon {s['hon_rej']:9s} caught {s['caught']:7s} inconcl {s['inconclusive']}")
    print("wrote", OUT, "and summary")
