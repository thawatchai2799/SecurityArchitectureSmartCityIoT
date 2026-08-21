#!/usr/bin/env python3
"""
run_poc.py  --  end-to-end Proof-of-Concept
============================================
Multi-Layer Trustworthy Security Architecture for Smart-City IoT
  L1  IoT / network traffic      : real TON_IoT flows (211k) + optional other datasets
  L2  Edge AI IDS                : lightweight model benchmark  (Exp-1)
      + cross-dataset generalisation on common semantic features (Exp-2, if extra data present)
  L2' Federated learning         : 5 districts, IID vs non-IID vs centralised vs local (Exp-3)
  L3  Permissioned blockchain    : alert / model anchoring, throughput, tamper detection (Exp-4)
  L4  Cloud orchestrator         : city replay, correlation, audit, rogue node (Exp-5)

Usage:  python run_poc.py [--sample N] [--quick]
Outputs -> results/*.json, results/*.csv, results/fig_*.png, results/REPORT.md
"""
import os, sys, json, time, argparse, warnings
warnings.filterwarnings("ignore")
# Windows consoles default to a legacy code page (e.g. cp874 on Thai systems) and
# would raise UnicodeEncodeError on characters such as "µ" or "×".
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, os.path.dirname(__file__))
from poc import data_loader as dl
from poc import edge_ids, federated, blockchain
from poc.city_simulation import run_city
from poc import robust_fl, generalisation

RES = os.path.join(os.path.dirname(__file__), "results"); os.makedirs(RES, exist_ok=True)


def save(obj, name):
    with open(os.path.join(RES, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None, help="subsample rows (default: all)")
    ap.add_argument("--quick", action="store_true", help="fast settings for smoke test")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    if a.quick and not a.sample:
        a.sample = 40000
    T0 = time.time(); report = {}
    import platform
    report["machine"] = dict(python=platform.python_version(), platform=platform.platform(),
                             processor=platform.processor(), cpu_count=os.cpu_count(),
                             run_date=time.strftime("%Y-%m-%d %H:%M"), args=vars(a))
    print("machine:", report["machine"])
    if sys.version_info < (3, 9):
        print("WARNING: Python >= 3.9 is required (type hints use PEP 604 syntax).")

    print("=" * 70); print("[L1] Loading datasets"); print("=" * 70)
    avail = dl.available_datasets(); print("available:", avail)
    ton = dl.load_ton_iot(sample=a.sample, seed=a.seed)
    Xn, Xc, yb, ym = ton["X_native"].values.astype(np.float32), ton["X_common"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    print(f"TON_IoT: {Xn.shape[0]} flows, {Xn.shape[1]} native features, {Xc.shape[1]} common features")
    print("class balance:", dict(zip(*np.unique(ym, return_counts=True))))
    idx_tr, idx_te = train_test_split(np.arange(len(yb)), test_size=0.3, stratify=ym, random_state=a.seed)
    report["dataset"] = dict(name="TON_IoT Train_Test_Network", n=int(len(yb)),
                             n_native_features=int(Xn.shape[1]), n_common_features=int(Xc.shape[1]),
                             types=dict(zip(*[list(map(str, u)) if i == 0 else list(map(int, u))
                                              for i, u in enumerate(np.unique(ym, return_counts=True))])))

    # ------------------------------------------------------------------ #
    print("\n[Exp-1] Edge IDS benchmark (native bias-aware features)")
    res1 = edge_ids.benchmark(Xn[idx_tr], yb[idx_tr], Xn[idx_te], yb[idx_te], seed=a.seed)
    df1 = pd.DataFrame(res1); print(df1[["model", "f1", "roc_auc", "fpr", "model_size_kb",
                                         "latency_us_per_flow", "throughput_flows_per_s"]].round(4).to_string(index=False))
    df1.to_csv(os.path.join(RES, "exp1_edge_ids_benchmark.csv"), index=False)
    report["exp1_edge_ids"] = res1

    print("\n[Exp-1b] Same models on the 9 COMMON semantic features only")
    res1b = edge_ids.benchmark(Xc[idx_tr], yb[idx_tr], Xc[idx_te], yb[idx_te], seed=a.seed)
    df1b = pd.DataFrame(res1b); print(df1b[["model", "f1", "roc_auc", "fpr"]].round(4).to_string(index=False))
    df1b.to_csv(os.path.join(RES, "exp1b_common_features.csv"), index=False)
    report["exp1b_common_features"] = res1b

    # ------------------------------------------------------------------ #
    print("\n[Exp-2] Cross-dataset generalisation (train on A, test on B)")
    others = [k for k, v in avail.items() if v and k not in ("ton_iot", "firewall")]
    loaded = {}                     # cache: each extra CSV is read only once
    report["exp1c_native_other_datasets"] = {}
    for k in others:
        print(f"\n[Exp-1c] Native edge-IDS benchmark on {k}")
        d = dl.LOADERS[k](sample=a.sample, seed=a.seed); loaded[k] = d
        Xo, yo = np.nan_to_num(d["X_native"].values.astype(np.float32)), d["y_bin"]
        print(f"   {d['name']}: {len(yo):,} rows, {Xo.shape[1]} native features, "
              f"attack ratio {yo.mean():.3f}, direction_proxy={d['direction_proxy']}")
        tr, te = train_test_split(np.arange(len(yo)), test_size=0.3, stratify=yo, random_state=a.seed)
        r = edge_ids.benchmark(Xo[tr], yo[tr], Xo[te], yo[te], seed=a.seed)
        for row in r:
            row["dataset"] = d["name"]; row["n_rows"] = int(len(yo))
        pd.DataFrame(r).to_csv(os.path.join(RES, f"exp1c_native_{k}.csv"), index=False)
        print(pd.DataFrame(r)[["model", "f1", "roc_auc", "fpr", "latency_us_per_flow"]].round(4).to_string(index=False))
        report["exp1c_native_other_datasets"][k] = r

    if others:
        from sklearn.metrics import f1_score
        # Every dataset contributes a *train* and a *test* split, so the diagonal of the
        # matrix is an honest held-out score, not a resubstitution score.
        views = {"common9": ("X_common", "9 directional features"),
                 "dirfree4": ("X_dirfree", "4 direction-free features")}
        report["exp2_cross_dataset"] = {}
        for vkey, (attr, vdesc) in views.items():
            sets = {}
            for k in ["ton_iot"] + others:
                d = loaded.get(k) or dl.LOADERS[k](sample=a.sample, seed=a.seed)
                loaded[k] = d
                # the 9 directional features are meaningless where the dataset does not
                # separate the directions -> such datasets appear only in the dirfree view
                if vkey == "common9" and d.get("direction_proxy"):
                    continue
                Xv = np.nan_to_num(d[attr].values.astype(np.float32))
                tr, te = train_test_split(np.arange(len(d["y_bin"])), test_size=0.3,
                                          stratify=d["y_bin"], random_state=a.seed)
                sets[d["name"]] = (Xv, d["y_bin"], tr, te)
            if len(sets) < 2:
                continue
            rows = []
            for src, (Xs, ys, tr, _) in sets.items():
                m = edge_ids.model_zoo(a.seed)["RandomForest(20x8)"]; m.fit(Xs[tr], ys[tr])
                for dst, (Xd, yd, _, te) in sets.items():
                    rows.append(dict(train=src, test=dst, f1=f1_score(yd[te], m.predict(Xd[te]))))
            df2 = pd.DataFrame(rows).pivot(index="train", columns="test", values="f1")
            print(f"\n  cross-dataset F1 ({vdesc}):"); print(df2.round(3))
            df2.to_csv(os.path.join(RES, f"exp2_cross_dataset_f1_{vkey}.csv"))
            report["exp2_cross_dataset"][vkey] = rows
            fig, ax = plt.subplots(figsize=(5.5, 4.5)); im = ax.imshow(df2.values, vmin=0, vmax=1, cmap="viridis")
            ax.set_xticks(range(len(df2.columns))); ax.set_xticklabels(df2.columns, rotation=30)
            ax.set_yticks(range(len(df2.index))); ax.set_yticklabels(df2.index)
            for i in range(df2.shape[0]):
                for j in range(df2.shape[1]):
                    ax.text(j, i, f"{df2.values[i, j]:.2f}", ha="center", va="center", color="w", fontsize=9)
            ax.set_xlabel("test dataset"); ax.set_ylabel("train dataset")
            ax.set_title(f"Cross-dataset F1 ({vdesc})")
            fig.colorbar(im); fig.tight_layout()
            fig.savefig(os.path.join(RES, f"fig5_cross_dataset_{vkey}.png"), dpi=150); plt.close(fig)
    else:
        print("  -> only TON_IoT present.  Drop CICIoT2023.csv / CICIDS2017.csv / "
              "UNSW_NB15_training-set.csv into ./data to enable Exp-1c and Exp-2.")
        report["exp2_cross_dataset"] = "skipped: no second dataset in ./data"

    # ------------------------------------------------------------------ #
    print("\n[Exp-1m] Multi-class attack-type classification on TON_IoT (edge model)")
    from sklearn.metrics import classification_report
    from sklearn.ensemble import RandomForestClassifier
    mc = RandomForestClassifier(n_estimators=30, max_depth=12, n_jobs=1, random_state=a.seed)
    mc.fit(Xn[idx_tr], ym[idx_tr]); ymp = mc.predict(Xn[idx_te])
    cr = classification_report(ym[idx_te], ymp, output_dict=True, zero_division=0)
    dfm = pd.DataFrame(cr).T.round(4); print(dfm.to_string())
    dfm.to_csv(os.path.join(RES, "exp1m_multiclass_ton_iot.csv"))
    report["exp1m_multiclass"] = cr

    # ------------------------------------------------------------------ #
    print("\n[Exp-6] Perimeter layer: firewall-policy replication (Internet Firewall Data Set)")
    if avail.get("firewall"):
        fw = dl.load_firewall(seed=a.seed)
        rows6 = []
        for tag, Xf in (("no-ports (bias-aware)", fw["X_native"]), ("with-ports", fw["X_ports"])):
            Xf = Xf.values.astype(np.float32); yf = fw["y_bin"]
            tr, te = train_test_split(np.arange(len(yf)), test_size=0.3, stratify=yf, random_state=a.seed)
            for r in edge_ids.benchmark(Xf[tr], yf[tr], Xf[te], yf[te], seed=a.seed):
                r["features"] = tag; rows6.append(r)
        df6 = pd.DataFrame(rows6); print(df6[["features", "model", "f1", "roc_auc", "fpr"]].round(4).to_string(index=False))
        df6.to_csv(os.path.join(RES, "exp6_firewall_perimeter.csv"), index=False)
        report["exp6_firewall"] = rows6
    else:
        print("  -> put log2.csv (Internet Firewall Data Set) into ./data to enable.")
        report["exp6_firewall"] = "skipped"

    # ------------------------------------------------------------------ #
    print("\n[Exp-4] Permissioned ledger micro-benchmark")
    res4 = blockchain.throughput_benchmark(n_tx=2000 if a.quick else 10000, block_size=100)
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res4.items()}, indent=1))
    report["exp4_ledger"] = res4

    # ------------------------------------------------------------------ #
    print("\n[Exp-3] Federated learning across 5 districts (weights anchored on ledger)")
    fl_ledger = blockchain.PermissionedLedger(block_size=5)
    rounds = 6 if a.quick else 15
    res3 = {}
    for regime in ("iid", "non-iid"):
        r = federated.run_federated(Xn[idx_tr], yb[idx_tr], ym[idx_tr], Xn[idx_te], yb[idx_te],
                                    k=5, rounds=rounds, local_epochs=2, regime=regime, seed=a.seed,
                                    ledger=fl_ledger if regime == "non-iid" else None)
        res3[regime] = r
        print(f"  {regime:8s} federated F1={r['federated_f1']:.4f} | centralised F1={r['centralised_f1']:.4f}"
              f" | local-only mean F1={r['local_only_f1_mean']:.4f} | raw bytes kept private={r['raw_bytes_not_shared']/1e6:.1f} MB"
              f" | weight bytes/round={r['weight_bytes_per_round']/1e3:.1f} KB")
        for d in r["districts"]:
            print(f"     {d['district']:11s} n={d['n_flows']:6d} attack_ratio={d['attack_ratio']:.2f} top={d['top_types']}")
    fl_ledger.flush(); ok, msg = fl_ledger.verify_chain()
    print(f"  model-update ledger: {fl_ledger.metrics['tx_submitted']} anchored versions, verify -> {msg}")
    report["exp3_federated"] = res3
    report["exp3_model_ledger"] = fl_ledger.summary()

    # ------------------------------------------------------------------ #
    print("\n[Exp-7] Leave-one-attack-family-out (unseen attack) on TON_IoT")
    res7 = generalisation.leave_one_attack_out(Xn, yb, ym, seed=a.seed)
    df7 = pd.DataFrame(res7); print(df7.round(4).to_string(index=False))
    df7.to_csv(os.path.join(RES, "exp7_leave_one_attack_out.csv"), index=False); report["exp7_loao"] = res7

    print("\n[Exp-8] Feature-importance ablation on TON_IoT")
    res8 = generalisation.feature_ablation(ton["X_native"], yb, seed=a.seed)
    print(pd.DataFrame(res8["ranking"]).round(4).to_string(index=False))
    print(pd.DataFrame(res8["ablation"])[["removed_top_k", "n_features", "f1"]].round(4).to_string(index=False))
    pd.DataFrame(res8["ablation"]).to_csv(os.path.join(RES, "exp8_feature_ablation.csv"), index=False)
    pd.DataFrame(res8["ranking"]).to_csv(os.path.join(RES, "exp8_feature_ranking.csv"), index=False)
    report["exp8_ablation"] = res8


    print("\n[Exp-8b] Decision-tree rule extraction (explainability)")
    res8b = generalisation.tree_rules(ton["X_native"], yb, ym, seed=a.seed)
    pd.DataFrame(res8b["leaves"]).to_csv(os.path.join(RES, "exp8b_tree_rules.csv"), index=False)
    print(f"   {res8b['n_leaves']} leaves, depth {res8b['depth']}; top attack leaf covers "
          f"{100*res8b['top_attack_leaf_share']:.0f}% of attack test flows")
    report["exp8b_tree_rules"] = res8b

    print("\n[Exp-9] Poisoning-resilient, ledger-anchored aggregation (LPRA) + personalised FL")
    res9 = {}; rl = blockchain.PermissionedLedger(block_size=5)
    for attack in ("none", "scale", "flip", "noise"):
        for defense in ((False, True) if attack != "none" else (True,)):
            r = robust_fl.run_robust_fl(Xn[idx_tr], yb[idx_tr], ym[idx_tr], Xn[idx_te], yb[idx_te], k=5,
                                        rounds=rounds, local_epochs=2, regime="non-iid", seed=a.seed,
                                        attack=attack, byzantine=None if attack == "none" else 0,
                                        defense=defense, ledger=rl if defense else None,
                                        personalise=(attack == "none"))
            key = f"{attack}/{'LPRA' if defense else 'plain FedAvg'}"; res9[key] = r
            print(f"  {key:22s} global F1={r['global_f1']:.4f} byzantine caught in {r['byzantine_caught_rounds']}/{rounds} rounds")
            if "personalised" in r:
                for d in r["personalised"]:
                    print(f"     {d['district']:11s} global={d['global_f1_local_test']:.4f} personalised={d['personalised_f1_local_test']:.4f}")
    rl.flush(); report["exp9_robust_fl"] = res9; report["exp9_ledger"] = rl.summary()
    pd.DataFrame([dict(setting=k, global_f1=v["global_f1"], byzantine_caught_rounds=v["byzantine_caught_rounds"]) for k, v in res9.items()]).to_csv(os.path.join(RES, "exp9_robust_fl.csv"), index=False)
    if "personalised" in res9.get("none/LPRA", {}):
        pd.DataFrame(res9["none/LPRA"]["personalised"]).to_csv(os.path.join(RES, "exp9_personalised_fl.csv"), index=False)

    # ------------------------------------------------------------------ #
    print("\n[Exp-5] City-wide replay: 5 district gateways -> ledger -> cloud orchestrator")
    edge_model = DecisionTreeClassifier(max_depth=8, random_state=a.seed).fit(Xn[idx_tr], yb[idx_tr])
    n_replay = 5000 if a.quick else 20000
    res5 = run_city(edge_model, Xn[idx_te], yb[idx_te], ym[idx_te], k=5, n_flows=n_replay, seed=a.seed)
    print(json.dumps({k: v for k, v in res5.items() if k not in ("campaign_examples",)}, indent=1, default=str))
    report["exp5_city_replay"] = res5

    # ------------------------------------------------------------------ #
    print("\n[figures]")
    make_figures(df1, df1b, res3, res4)
    report["runtime_s"] = time.time() - T0
    save(report, "poc_results.json")
    write_report(report, df1, df1b)
    import shutil
    bundle = shutil.make_archive(os.path.join(os.path.dirname(__file__), "results_bundle"), "zip", RES)
    print(f"\nDone in {report['runtime_s']:.0f}s.  See {RES}/")
    print(f">>> Send this file back for paper write-up: {bundle}")


def make_figures(df1, df1b, res3, res4):
    # Fig 1: quality vs footprint
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x = np.arange(len(df1)); w = 0.35
    ax[0].bar(x - w / 2, df1["f1"], w, label="native features (54)")
    ax[0].bar(x + w / 2, df1b["f1"], w, label="common features (9)")
    ax[0].set_xticks(x); ax[0].set_xticklabels(df1["model"], rotation=15); ax[0].set_ylim(0.8, 1.0)
    ax[0].set_ylabel("F1 (attack vs normal)"); ax[0].set_title("Detection quality"); ax[0].legend()
    ax[1].scatter(df1["latency_us_per_flow"], df1["model_size_kb"], s=80)
    for _, r in df1.iterrows():
        ax[1].annotate(r["model"], (r["latency_us_per_flow"], r["model_size_kb"]), fontsize=8)
    ax[1].set_xscale("log"); ax[1].set_yscale("log")
    ax[1].set_xlabel("per-flow inference latency (µs)"); ax[1].set_ylabel("model size (KB)")
    ax[1].set_title("Edge footprint"); fig.tight_layout(); fig.savefig(os.path.join(RES, "fig1_edge_ids.png"), dpi=150)

    # Fig 2: federated convergence
    fig, ax = plt.subplots(figsize=(6, 4))
    for regime, r in res3.items():
        ax.plot([h["round"] for h in r["history"]], [h["f1"] for h in r["history"]], marker="o", label=f"FedAvg {regime}")
    ax.axhline(res3["non-iid"]["centralised_f1"], ls="--", c="k", label="centralised (no privacy)")
    ax.axhline(res3["non-iid"]["local_only_f1_mean"], ls=":", c="r", label="local-only mean (non-iid)")
    ax.set_xlabel("communication round"); ax.set_ylabel("global-model F1"); ax.legend(); ax.set_title("Federated vs centralised vs local")
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig2_federated.png"), dpi=150)

    # Fig 3: ledger overhead
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].bar(["plain DB", "on-chain"], [res4["plain_db_bytes"] / 1e3, res4["onchain_bytes"] / 1e3])
    ax[0].set_ylabel("KB for %d alerts" % res4["tx_submitted"]); ax[0].set_title(f"Storage overhead ×{res4['storage_overhead_x']:.2f}")
    ax[1].bar(["tx confirm", "block commit"], [res4["avg_tx_confirm_ms"], res4["avg_block_commit_ms"]])
    ax[1].set_ylabel("ms"); ax[1].set_title(f"Latency ({res4['tx_per_s']:.0f} tx/s)")
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig3_ledger.png"), dpi=150)

    # NOTE: publication-quality figures (600 dpi PNG + PDF) are produced by
    # paper_src/make_figures.py from the CSV/JSON in results/.  The plots written here are
    # quick previews for the console user.


def write_report(rep, df1, df1b):
    r3, r4, r5 = rep["exp3_federated"], rep["exp4_ledger"], rep["exp5_city_replay"]
    L = ["# PoC results — Multi-Layer Trustworthy Security Architecture for Smart-City IoT", ""]
    L += [f"Dataset: {rep['dataset']['name']} — {rep['dataset']['n']:,} real flows, "
          f"{rep['dataset']['n_native_features']} bias-aware features (IP/port removed).", ""]
    L += ["## Exp-1 Edge IDS benchmark", "", df1[["model", "accuracy", "f1", "roc_auc", "fpr", "model_size_kb",
          "latency_us_per_flow", "throughput_flows_per_s"]].round(4).to_markdown(index=False), ""]
    L += ["## Exp-1b Same models, 9 common semantic features (for cross-dataset use)", "",
          df1b[["model", "f1", "roc_auc", "fpr"]].round(4).to_markdown(index=False), ""]
    L += ["## Exp-3 Federated learning (5 districts)", ""]
    for reg, r in r3.items():
        L += [f"- **{reg}**: FedAvg F1 = {r['federated_f1']:.4f}, centralised F1 = {r['centralised_f1']:.4f}, "
              f"local-only mean F1 = {r['local_only_f1_mean']:.4f}; raw data kept on-premise = "
              f"{r['raw_bytes_not_shared']/1e6:.1f} MB, weights exchanged/round = {r['weight_bytes_per_round']/1e3:.1f} KB"]
    L += ["", "## Exp-4 Permissioned ledger", "",
          f"- {r4['validators']} validators (PoA, quorum {r4['quorum']}), {r4['tx_per_s']:.0f} tx/s, "
          f"tx confirm {r4['avg_tx_confirm_ms']:.2f} ms, storage overhead ×{r4['storage_overhead_x']:.2f}",
          f"- chain verification: intact = {r4['verify_intact']}, tamper detected = {r4['tamper_detected']} ({r4['tamper_msg']})", ""]
    L += ["## Exp-5 City-wide replay", "",
          f"- {r5['n_flows']:,} real flows through {r5['districts']} gateways at {r5['flows_per_s']:.0f} flows/s; "
          f"per-flow latency mean {r5['per_flow_latency_ms']['mean']:.3f} ms, p99 {r5['per_flow_latency_ms']['p99']:.3f} ms",
          f"- detection: precision {r5['detection']['precision']:.4f}, recall {r5['detection']['recall']:.4f}, FPR {r5['detection']['fpr']:.4f}",
          f"- {r5['alerts']:,} alerts anchored in {r5['ledger']['blocks']} blocks; cross-district campaigns detected: {r5['campaigns_detected']}",
          f"- insider tampering audit: {r5['audit']}", f"- rogue node rejected: {r5['rogue_node_rejected']}; ledger intact: {r5['ledger_intact']}", ""]
    L += ["Figures: fig1_edge_ids.png, fig2_federated.png, fig3_ledger.png, fig4_city_replay.png"]
    with open(os.path.join(RES, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
