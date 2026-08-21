#!/usr/bin/env python3
"""
run_extended.py -- experiments added for manuscript v0.3 (all on TON_IoT, no hardware)
  ExtA  Byzantine grid : {none,scale,flip,noise,stealth} x {1,2 attackers} x 6 aggregators x 3 seeds
  ExtB  Multi-seed CIs : Exp-1 edge benchmark and Exp-3 FedAvg (5 seeds, mean +/- SD)
  ExtC  Scalability    : districts K in {5,10,20,50}; validators in {3..15}; ledger block size sweep
  ExtD  City scenario  : ransomware campaign Healthcare -> Water -> Transport; time-to-detect per layer
Usage: python run_extended.py [--quick]
"""
import os, sys, json, time, argparse, warnings
warnings.filterwarnings("ignore")
for _stream in (sys.stdout, sys.stderr):      # Windows legacy code pages -> UTF-8
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
sys.path.insert(0, os.path.dirname(__file__))
from poc import data_loader as dl, edge_ids, federated, blockchain, byzantine
from poc.blockchain import PermissionedLedger, sha256

RES = os.path.join(os.path.dirname(__file__), "results"); os.makedirs(RES, exist_ok=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true")
    ap.add_argument("--part", default="all", help="A|B|C|D|fig|all  (run parts separately on slow machines)")
    ap.add_argument("--seed", type=int, default=None, help="for --part A: run a single seed (checkpointed)")
    a = ap.parse_args()
    T0 = time.time(); rep = load_rep()
    import platform
    rep["machine"] = dict(python=platform.python_version(), platform=platform.platform(),
                          cpu_count=os.cpu_count(), run_date=time.strftime("%Y-%m-%d %H:%M"))
    print("machine:", rep["machine"])
    run = lambda x: a.part in ("all", x)
    seeds_A = [42, 43, 44] if not a.quick else [42]
    seeds_B = [42, 43, 44, 45, 46] if not a.quick else [42, 43]
    roundsA = 10 if not a.quick else 5

    need_full = a.part in ("all", "B", "D")
    if need_full:
        ton_full = dl.load_ton_iot()
        Xf, yf, mf = ton_full["X_native"].values.astype(np.float32), ton_full["y_bin"], ton_full["y_multi"]
    ton = dl.load_ton_iot(sample=60000 if not a.quick else 25000)
    Xn, yb, ym = ton["X_native"].values.astype(np.float32), ton["y_bin"], ton["y_multi"]
    tr, te = train_test_split(np.arange(len(yb)), test_size=0.3, stratify=ym, random_state=42)

    # ================================================================== #
    if run("A"):
      print("[ExtA] Byzantine-robust aggregation grid")
      configs = [("none", 0)] + [(at, n) for at in ("scale", "flip", "noise", "stealth") for n in (1, 2)]
      rawp = os.path.join(RES, "extA_byzantine_grid_raw.csv")
      done = pd.read_csv(rawp) if os.path.exists(rawp) else pd.DataFrame()
      rows = done.to_dict("records") if len(done) else []
      for seed in ([a.seed] if a.seed is not None else seeds_A):
        if len(done) and (done.seed == seed).any():
            print(f"  seed {seed} already done, skipping"); continue
        for att, n in configs:
            for agg in byzantine.AGGREGATORS:
                r = byzantine.run_byzantine(Xn[tr], yb[tr], ym[tr], Xn[te], yb[te], k=5, rounds=roundsA,
                                            seed=seed, attack=att, n_att=n, aggregator=agg)
                rows.append({k: v for k, v in r.items() if k != "history"})
                print(f"  seed={seed} {att:8s} n={n} {agg:12s} F1={r['final_f1']:.4f} caught={r['rounds_all_attackers_rejected']}/{roundsA} hon_rej={r['honest_rejections']}")
        pd.DataFrame(rows).to_csv(rawp, index=False)          # checkpoint per seed
      dfA = pd.DataFrame(rows)
      piv = dfA.groupby(["attack", "n_att", "aggregator"]).agg(f1_mean=("final_f1", "mean"), f1_sd=("final_f1", "std"),
                                                             caught=("rounds_all_attackers_rejected", "mean"),
                                                             honest_rej=("honest_rejections", "mean"), seeds=("seed", "nunique")).reset_index()
      piv.to_csv(os.path.join(RES, "extA_byzantine_grid_summary.csv"), index=False)
      print(piv.round(4).to_string(index=False)); rep["extA"] = piv.to_dict("records"); save_rep(rep)

    # ================================================================== #
    if run("B"):
      print("\n[ExtB] Multi-seed confidence intervals (full TON_IoT)")
      rowsB1, rowsB3 = [], []
      for seed in seeds_B:
        itr, ite = train_test_split(np.arange(len(yf)), test_size=0.3, stratify=mf, random_state=seed)
        for r in edge_ids.benchmark(Xf[itr], yf[itr], Xf[ite], yf[ite], seed=seed):
            r["seed"] = seed; rowsB1.append(r)
        r3 = federated.run_federated(Xf[itr], yf[itr], mf[itr], Xf[ite], yf[ite], k=5, rounds=15 if not a.quick else 6,
                                     local_epochs=2, regime="non-iid", seed=seed)
        rowsB3.append(dict(seed=seed, federated_f1=r3["federated_f1"], centralised_f1=r3["centralised_f1"],
                           local_only_f1_mean=r3["local_only_f1_mean"]))
        print(f"  seed {seed}: FedAvg={r3['federated_f1']:.4f} cen={r3['centralised_f1']:.4f} local={r3['local_only_f1_mean']:.4f}")
      dfB1 = pd.DataFrame(rowsB1); dfB1.to_csv(os.path.join(RES, "extB_edge_multiseed_raw.csv"), index=False)
      sB1 = dfB1.groupby("model")[["f1", "roc_auc", "fpr", "latency_us_per_flow", "model_size_kb"]].agg(["mean", "std"])
      sB1.to_csv(os.path.join(RES, "extB_edge_multiseed_summary.csv")); print(sB1.round(4))
      dfB3 = pd.DataFrame(rowsB3); dfB3.to_csv(os.path.join(RES, "extB_fedavg_multiseed.csv"), index=False)
      print(dfB3.describe().loc[["mean", "std"]].round(4))
      rep["extB_edge"] = json.loads(sB1.to_json()); rep["extB_fed"] = dfB3.describe().loc[["mean", "std"]].to_dict(); save_rep(rep)

    # ================================================================== #
    if run("C"):
      print("\n[ExtC] Scalability")
      rowsC1 = []
      for K in ([5, 10, 20, 50] if not a.quick else [5, 10, 20]):
          for agg in ("fedavg", "lpra"):
              for att, n in (("none", 0), ("scale", max(1, K // 5))):
                  r = byzantine.run_byzantine(Xn[tr], yb[tr], ym[tr], Xn[te], yb[te], k=K, rounds=roundsA, seed=42,
                                              attack=att, n_att=n, aggregator=agg)
                  rowsC1.append(dict(K=K, aggregator=agg, attack=att, n_att=n, f1=r["final_f1"], caught=r["rounds_all_attackers_rejected"],
                                     honest_rej=r["honest_rejections"], round_time_s=r["time_s"] / roundsA))
                  print(f"  K={K:2d} {agg:7s} {att:5s} n_att={n:2d} F1={r['final_f1']:.4f} caught={r['rounds_all_attackers_rejected']}/{roundsA} t/round={r['time_s']/roundsA:.2f}s")
      dfC1 = pd.DataFrame(rowsC1); dfC1.to_csv(os.path.join(RES, "extC_districts_scaling.csv"), index=False)
      print("  gamma sensitivity of LPRA at K=20 (extreme non-IID)")
      rowsC1b = []
      for gamma in (2.5, 3.5, 5.0, 8.0):
          for att, n in (("none", 0), ("scale", 4)):
              r = byzantine.run_byzantine(Xn[tr], yb[tr], ym[tr], Xn[te], yb[te], k=20, rounds=roundsA, seed=42,
                                          attack=att, n_att=n, aggregator="lpra", lpra_gamma=gamma)
              rowsC1b.append(dict(gamma=gamma, attack=att, n_att=n, f1=r["final_f1"], caught=r["rounds_all_attackers_rejected"], honest_rej=r["honest_rejections"]))
              print(f"    gamma={gamma} {att:5s} F1={r['final_f1']:.4f} caught={r['rounds_all_attackers_rejected']}/{roundsA} honest_rej={r['honest_rejections']}")
      pd.DataFrame(rowsC1b).to_csv(os.path.join(RES, "extC_lpra_gamma_sensitivity_K20.csv"), index=False)

      rowsC2 = []
      for V in [3, 5, 7, 11, 15]:
          led = PermissionedLedger(validators=[f"Agency{i}" for i in range(V)], block_size=100, block_interval_s=1e9,
                                   members=["Gateway-T"])
          t0 = time.perf_counter(); n_tx = 5000
          for i in range(n_tx):
              led.submit(dict(kind="ALERT", district="Transport", attack="ddos", flow_hash=sha256(str(i))), submitter="Gateway-T")
          led.flush(); dt = time.perf_counter() - t0; s = led.summary()
          rowsC2.append(dict(validators=V, quorum=s["quorum"], tx_per_s=n_tx / dt, block_commit_ms=s["avg_block_commit_ms"],
                             storage_overhead_x=s["storage_overhead_x"], verify_ms=1e3 * _timeit(led.verify_chain)))
          print(f"  validators={V:2d} quorum={s['quorum']} tx/s={n_tx/dt:8.0f} commit={s['avg_block_commit_ms']:.2f}ms overhead={s['storage_overhead_x']:.2f}x")
      dfC2 = pd.DataFrame(rowsC2); dfC2.to_csv(os.path.join(RES, "extC_validators_scaling.csv"), index=False)

      rowsC3 = []
      for bs in [10, 50, 100, 500, 1000]:
          s = blockchain.throughput_benchmark(n_tx=5000, block_size=bs)
          rowsC3.append(dict(block_size=bs, tx_per_s=s["tx_per_s"], tx_confirm_ms=s["avg_tx_confirm_ms"],
                             block_commit_ms=s["avg_block_commit_ms"], storage_overhead_x=s["storage_overhead_x"]))
          print(f"  block_size={bs:4d} tx/s={s['tx_per_s']:8.0f} confirm={s['avg_tx_confirm_ms']:.2f}ms overhead={s['storage_overhead_x']:.2f}x")
      dfC3 = pd.DataFrame(rowsC3); dfC3.to_csv(os.path.join(RES, "extC_blocksize_sweep.csv"), index=False)
      rep["extC"] = dict(districts=rowsC1, gamma_K20=rowsC1b, validators=rowsC2, blocksize=rowsC3); save_rep(rep)

    # ================================================================== #
    if run("D"):
      print("\n[ExtD] City-wide ransomware campaign scenario (replay of real flows with a timeline)")
      resD = city_scenario(Xf, yf, mf, seed=42)
      print(json.dumps(resD, indent=1, default=float)); rep["extD"] = resD
      with open(os.path.join(RES, "extD_scenario.json"), "w", encoding="utf-8") as f:
          json.dump(resD, f, indent=2, default=float)
      save_rep(rep)

    # ================================================================== #
    if run("fig") or a.part == "all":
      need = ["extA_byzantine_grid_summary.csv", "extC_districts_scaling.csv",
              "extC_validators_scaling.csv", "extC_blocksize_sweep.csv", "extD_scenario.json"]
      miss = [f for f in need if not os.path.exists(os.path.join(RES, f))]
      if miss:
          print(f"  figures skipped, missing result files: {miss}\n"
                f"  run the corresponding parts first:  python run_extended.py --part A|C|D")
      else:
          piv = pd.read_csv(os.path.join(RES, need[0]))
          dfC1 = pd.read_csv(os.path.join(RES, need[1])); dfC2 = pd.read_csv(os.path.join(RES, need[2]))
          dfC3 = pd.read_csv(os.path.join(RES, need[3]))
          with open(os.path.join(RES, need[4]), encoding="utf-8") as fh:
              resD = json.load(fh)
          figures(piv, dfC1, dfC2, dfC3, resD)
    rep["runtime_s"] = rep.get("runtime_s", 0) + time.time() - T0; save_rep(rep)
    print(f"\nDone part={a.part} in {time.time()-T0:.0f}s")


def load_rep():
    pth = os.path.join(RES, "extended_results.json")
    if not os.path.exists(pth):
        return {}
    with open(pth, encoding="utf-8") as fh:
        return json.load(fh)


def save_rep(rep):
    with open(os.path.join(RES, "extended_results.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, default=float)


def _timeit(fn):
    t0 = time.perf_counter(); fn(); return time.perf_counter() - t0


def city_scenario(X, y, ytype, seed=42, k=5, dt_flow=0.01, window_s=10.0, min_districts=3):
    """Simulated clock: each district receives 100 flows/s of normal traffic.  A ransomware
    campaign starts in Healthcare at t=60 s, spreads to Water at t=180 s and Transport at
    t=300 s (attack share ramps 0 -> 30 %).  Detector = depth-8 tree trained on a disjoint split
    that EXCLUDES ransomware (zero-day setting).  We measure per layer:
      L2 first alert per district, L3 anchoring delay, L4 time when >= 3 districts show an
      alert-rate anomaly in the same 10 s bin (campaign declared) vs. 'no-L4' baseline where
      districts only exchange daily reports (24 h)."""
    rng = np.random.default_rng(seed)
    normal = np.where(ytype == "normal")[0]; rans = np.where(ytype == "ransomware")[0]
    other = np.where((ytype != "normal") & (ytype != "ransomware"))[0]
    rng.shuffle(normal); n_tr = normal[:30000]; n_rep = normal[30000:]
    model = DecisionTreeClassifier(max_depth=8, random_state=seed).fit(np.vstack([X[n_tr], X[other]]),
                                                                       np.concatenate([np.zeros(len(n_tr)), np.ones(len(other))]))
    districts = ["Transport", "Energy", "Water", "Healthcare", "e-Gov"]
    onset = {"Healthcare": 60.0, "Water": 180.0, "Transport": 300.0}
    led = PermissionedLedger(block_size=20, block_interval_s=1.0,
                             members=[f"Gateway-{d}" for d in districts])
    first_alert, alerts, anchor_delay = {}, [], []
    T_end = 480.0; flows_per_s = 100; rate = 1.0 / flows_per_s
    for d in districts:
        t = 0.0; ni = 0; ri = 0
        while t < T_end:
            share = 0.0
            if d in onset and t >= onset[d]:
                share = min(0.3, 0.3 * (t - onset[d]) / 30.0)
            if rng.random() < share:
                idx = rans[ri % len(rans)]; ri += 1
            else:
                idx = n_rep[ni % len(n_rep)]; ni += 1
            if model.predict(X[idx].reshape(1, -1))[0] == 1:
                sub = time.perf_counter()
                led.submit(dict(kind="ALERT", district=d, evidence_hash=sha256(str(int(idx))), sim_t=t), submitter=f"Gateway-{d}")
                anchor_delay.append(time.perf_counter() - sub)
                alerts.append((t, d, bool(ytype[idx] == "ransomware")))
                if d not in first_alert and ytype[idx] == "ransomware":
                    first_alert[d] = t
            t += rate
    led.flush()
    # L4 correlation on the simulated clock: rate-based (a naive "any alert in 3 districts"
    # rule fires immediately from the ~1 % benign false-positive rate).  Alerts are binned per
    # district in 10 s bins; the benign baseline (mean, sd) is learned from the first 50 s;
    # a district is "in anomaly" when its bin count > mean + 6 sd (and >= 3x mean); a campaign
    # is declared at the first bin in which >= min_districts districts are in anomaly.
    bin_s = 10.0; nb = int(T_end / bin_s); counts = {d: np.zeros(nb) for d in districts}
    for (t, d, _) in alerts:
        counts[d][min(int(t // bin_s), nb - 1)] += 1
    base = {d: (counts[d][:5].mean(), counts[d][:5].std() + 1e-9) for d in districts}
    anomaly_start = {}
    campaign_t = None
    for b in range(nb):
        an = [d for d in districts if counts[d][b] > max(base[d][0] + 6 * base[d][1], 3 * base[d][0])]
        for d in an:
            anomaly_start.setdefault(d, b * bin_s)
        if len(an) >= min_districts and campaign_t is None:
            campaign_t = (b + 1) * bin_s          # end of the bin = decision time
    alerts.sort()
    fp_alerts = sum(1 for _, _, tp in alerts if not tp); tp_alerts = sum(1 for _, _, tp in alerts if tp)
    return dict(scenario="ransomware campaign Healthcare->Water->Transport, zero-day detector (ransomware unseen)",
                onset_s=onset, first_true_alert_s=first_alert,
                detection_delay_s={d: round(first_alert[d] - onset[d], 2) for d in first_alert},
                L3_mean_anchor_delay_ms=1e3 * float(np.mean(anchor_delay)) if anchor_delay else None,
                L4_district_anomaly_flag_s=anomaly_start, L4_campaign_declared_s=campaign_t,
                L4_time_from_first_onset_s=(campaign_t - 60.0) if campaign_t else None,
                no_L4_baseline_s="24 h (daily inter-agency report) or never",
                total_alerts=len(alerts), true_alerts=tp_alerts, false_alerts=fp_alerts,
                normal_flows_replayed=int(T_end * flows_per_s * k), ledger_blocks=led.metrics["blocks"],
                ledger_intact=led.verify_chain()[0])


def figures(piv, dfC1, dfC2, dfC3, resD):
    # Fig 6: Byzantine grid heatmap (F1 mean) attackers=1 and 2
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for ax, n in zip(axes, (1, 2)):
        sub = piv[(piv.n_att == n) | (piv.attack == "none")].pivot(index="attack", columns="aggregator", values="f1_mean")
        sub = sub.reindex(["none", "scale", "flip", "noise", "stealth"])[byzantine.AGGREGATORS]
        im = ax.imshow(sub.values, vmin=0.7, vmax=1.0, cmap="RdYlGn")
        ax.set_xticks(range(len(sub.columns))); ax.set_xticklabels(sub.columns, rotation=30)
        ax.set_yticks(range(len(sub.index))); ax.set_yticklabels(sub.index)
        for i in range(sub.shape[0]):
            for j in range(sub.shape[1]):
                v = sub.values[i, j]
                if not np.isnan(v): ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=8)
        ax.set_title(f"Global F1, {n} attacker(s) of 5")
    fig.colorbar(im, ax=axes, shrink=0.8); fig.savefig(os.path.join(RES, "fig6_byzantine_grid.png"), dpi=150, bbox_inches="tight")
    # Fig 7: scalability
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    for agg in ("fedavg", "lpra"):
        for att in ("none", "scale"):
            s = dfC1[(dfC1.aggregator == agg) & (dfC1.attack == att)]
            ax[0].plot(s.K, s.f1, marker="o", label=f"{agg} / {att}")
    ax[0].set_xlabel("number of districts K"); ax[0].set_ylabel("global F1"); ax[0].legend(fontsize=7); ax[0].set_title("Districts (20% Byzantine under 'scale')")
    ax[1].plot(dfC2.validators, dfC2.tx_per_s, marker="o"); ax[1].set_xlabel("validators"); ax[1].set_ylabel("tx/s"); ax[1].set_title("Ledger throughput vs validators")
    ax2 = ax[1].twinx(); ax2.plot(dfC2.validators, dfC2.storage_overhead_x, marker="s", c="r"); ax2.set_ylabel("storage overhead ×", color="r")
    ax[2].plot(dfC3.block_size, dfC3.tx_confirm_ms, marker="o"); ax[2].set_xscale("log"); ax[2].set_xlabel("block size (tx)"); ax[2].set_ylabel("tx confirm (ms)")
    ax3 = ax[2].twinx(); ax3.plot(dfC3.block_size, dfC3.storage_overhead_x, marker="s", c="r"); ax3.set_ylabel("storage overhead ×", color="r"); ax[2].set_title("Block size trade-off")
    fig.tight_layout(); fig.savefig(os.path.join(RES, "fig7_scalability.png"), dpi=150)
    # Fig 8: scenario timeline
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ons = resD["onset_s"]; fa = resD["first_true_alert_s"]
    for i, d in enumerate(["Healthcare", "Water", "Transport"]):
        ax.plot([ons[d], 480], [i, i], c="#ddd", lw=8, solid_capstyle="butt")
        ax.plot(ons[d], i, "k|", ms=14); ax.text(ons[d], i + 0.28, "onset", fontsize=7, ha="center")
        if d in fa:
            ax.plot(fa[d], i, "r^", ms=9); ax.text(fa[d], i - 0.42, f"L2 alert +{fa[d]-ons[d]:.1f}s", fontsize=7, ha="center", color="r")
    if resD["L4_campaign_declared_s"]:
        ax.axvline(resD["L4_campaign_declared_s"], c="b", ls="--"); ax.text(resD["L4_campaign_declared_s"] + 3, 2.4, "L4: city-wide campaign declared", color="b", fontsize=8)
    ax.set_yticks([0, 1, 2]); ax.set_yticklabels(["Healthcare", "Water", "Transport"]); ax.set_xlabel("simulated time (s)"); ax.set_ylim(-0.8, 2.9)
    ax.set_title("Ransomware campaign scenario: per-layer detection timeline"); fig.tight_layout(); fig.savefig(os.path.join(RES, "fig8_scenario_timeline.png"), dpi=150)


if __name__ == "__main__":
    main()
