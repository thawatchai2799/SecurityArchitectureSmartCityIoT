#!/usr/bin/env python3
"""
make_sustain_figures.py -- tables and figures for the operational-sustainability paper.

Reads results_sustain/summary.csv (+ replay_*.json) and writes
    results_sustain/tables/*.csv|md      every table in the manuscript
    results_sustain/figures/figS*.png|pdf
    results_sustain/sustain_facts.json   every headline number, by name
Every number printed in the paper must come from one of these files.
"""
import os, sys, json, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sustain.lifecycle import (lifecycle_table, aggregate_seeds, scale_city, sensitivity, combined_scenarios, ASSUMPTIONS,
                               PROTO_LABEL, POLICY_LABEL)
from sustain.anchoring import anchoring_table

RES = os.environ.get("SUSTAIN_RESULTS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "results_sustain")
FIG = os.path.join(RES, "figures"); TAB = os.path.join(RES, "tables")
os.makedirs(FIG, exist_ok=True); os.makedirs(TAB, exist_ok=True)

# Okabe-Ito, fixed order per protocol (validated: CVD-safe with the marker/linestyle secondary encoding)
COL = dict(tree_local="#0072B2", tree_cap="#56B4E9", mlp_local="#009E73", fedavg="#E69F00",
           lpra="#D55E00", central="#CC79A7")
MK = dict(tree_local="o", tree_cap="s", mlp_local="^", fedavg="D", lpra="v", central="P")
POL_ORDER = ["static", "every_8", "every_4", "every_2", "every_1", "trigger", "drift", "oracle", "adwin", "kswin", "ddm", "drift_fb"]
PROTO_ORDER = ["tree_local", "tree_cap", "mlp_local", "fedavg", "lpra", "central"]
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.5,
                     "legend.frameon": False, "figure.dpi": 150})


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"), dpi=600 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig); print("  wrote", name)


def workflow_figure():
    """Static overview: what the replay measures, what is assumed, and how they combine."""
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig, ax = plt.subplots(figsize=(7.2, 3.0)); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.grid(False)

    def box(x, y, w, h, title, lines, fc, ec):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", fc=fc, ec=ec, lw=1.2))
        ax.text(x + w / 2, y + h - 3, title, ha="center", va="top", fontsize=7.6, fontweight="bold", color=ec, linespacing=1.1)
        for i, ln in enumerate(lines):
            ax.text(x + 2.0, y + h - 20 - 7.6 * i, ln, ha="left", va="top", fontsize=6.4)

    box(1, 10, 30, 86, "MEASURED\nin the replay",
        ["per re-training event:", "  CPU-seconds (BLAS, 1 thread)", "  bytes up / down (weights)", "  bytes of raw flows exported",
         "  ledger transactions", "per window:", "  inference and detector CPU-s", "  F1, recall, FPR"],
        "#eaf3fb", "#0072B2")
    box(35, 10, 30, 86, "ASSUMED\n(assumptions table; swept)",
        ["windows per year  (2,920)", "core power: edge 3 W, x86 12 W", "edge slowdown vs x86  (5x)", "network intensity  (0.06 kWh/GB)",
         "bytes per ledger record  (6,076)", "grid factor  (0.4371 kg CO$_2$e/kWh)", "gateway idle draw  (2.7 W)"],
        "#fdf3e3", "#C8780A")
    box(69, 10, 30, 86, "USE-PHASE FOOTPRINT\nper gateway-year",
        ["kWh: training, inference, traffic", "kg CO$_2$e  (Eq. 3)", "GB of model traffic, raw flows",
         "MB of ledger growth", "share of the gateway's idle draw", "x K districts: per city-year (Eq. 2)"],
        "#eaf7f0", "#1B7F4F")
    for x0, x1 in ((31.6, 34.4), (65.6, 68.4)):
        ax.add_patch(FancyArrowPatch((x0, 53), (x1, 53), arrowstyle="-|>", mutation_scale=14, lw=1.4, color="#444"))
    ax.text(50, 1, r"Eq. (1):  $E_{gw} = (s/K)\,[\,(\sigma P_{edge}\,\tau_{gw} + P_{x86}\,\tau_{cloud})/3.6{\times}10^6 + I_{net}(B_{mod}+B_{raw}+B_{led})/10^9\,]$",
            ha="center", va="bottom", fontsize=7.2, color="#444")
    save(fig, "figS0_workflow")


def md_table(df: pd.DataFrame, path: str, floatfmt=".3f"):
    with open(path, "w") as f:
        f.write(df.to_markdown(index=False, floatfmt=floatfmt))


def main():
    # rebuild the grid from the replay files themselves (parallel runs may race on summary.csv)
    rows = []
    for p in sorted(glob.glob(os.path.join(RES, "replay_*_s*.json"))):
        with open(p) as f:
            rows.append(json.load(f)["summary"])
    summary = pd.DataFrame(rows)
    summary.to_csv(os.path.join(RES, "summary.csv"), index=False)
    seeds = sorted(summary.seed.unique())
    print(f"{len(summary)} runs, seeds {seeds}")
    facts = dict(n_seeds=len(seeds), seeds=seeds, assumptions=ASSUMPTIONS)

    # ---------------- Table: window schedule -------------------------------------------------
    wt = pd.read_csv(os.path.join(RES, f"window_table_s{seeds[0]}.csv"))
    md_table(wt, os.path.join(TAB, "T_windows.md")); wt.to_csv(os.path.join(TAB, "T_windows.csv"), index=False)

    # ---------------- Table: detection x cost grid, mean +/- CI over seeds --------------------
    lt = lifecycle_table(summary)
    lt.to_csv(os.path.join(TAB, "lifecycle_per_seed.csv"), index=False)
    agg = aggregate_seeds(lt)
    agg["protocol"] = pd.Categorical(agg.protocol, PROTO_ORDER); agg["policy"] = pd.Categorical(agg.policy, POL_ORDER)
    agg = agg.sort_values(["protocol", "policy"]).reset_index(drop=True)
    agg.to_csv(os.path.join(TAB, "T_grid_full.csv"), index=False)
    cols = ["protocol", "policy", "mean_f1", "mean_f1_ci", "stream_f1", "stream_recall", "stream_fpr",
            "retrains_per_year", "train_cpu_h_per_gw_year", "gb_model_per_gw_year", "gb_raw_per_gw_year",
            "tx_per_year", "kwh_per_gw_year", "kwh_per_gw_year_ci", "kgco2e_per_gw_year"]
    T = agg[cols].copy()
    T["protocol"] = T.protocol.map(PROTO_LABEL); T["policy"] = T.policy.map(POLICY_LABEL)
    T.to_csv(os.path.join(TAB, "T_grid.csv"), index=False); md_table(T, os.path.join(TAB, "T_grid.md"), ".4g")

    # ---------------- Table: scaling with K, anchoring, sensitivity --------------------------
    sc = scale_city(agg); sc.to_csv(os.path.join(TAB, "T_scaling.csv"), index=False)
    cs = combined_scenarios(summary); cs.to_csv(os.path.join(TAB, "T_scenarios.csv"), index=False)
    an = anchoring_table(agg, measure_path=os.path.join(RES, "merkle_measure.json")); an.to_csv(os.path.join(TAB, "T_anchoring.csv"), index=False)
    md_table(an[an.policy == "every_1"], os.path.join(TAB, "T_anchoring_every1.md"), ".4g")
    se = sensitivity(summary, policy="every_1" if (summary.policy == "every_1").any() else str(summary.policy.iloc[0]),
                     protocols=tuple(p for p in ("tree_cap", "fedavg", "central") if (summary.protocol == p).any()))
    se.to_csv(os.path.join(TAB, "T_sensitivity.csv"), index=False)
    md_table(se, os.path.join(TAB, "T_sensitivity.md"), ".4g")
    facts["sensitivity_ranking_unchanged_all"] = bool(se.ranking_unchanged.all())

    # ---------------- headline facts ---------------------------------------------------------
    def g(p, pol, c):
        r = agg[(agg.protocol == p) & (agg.policy == pol)]
        return float(r[c].iloc[0]) if len(r) else float("nan")
    for p in PROTO_ORDER:
        for pol in POL_ORDER:
            for c in ("mean_f1", "stream_f1", "kwh_per_gw_year", "kgco2e_per_gw_year", "tx_per_year",
                      "retrains_per_year", "gb_model_per_gw_year", "gb_raw_per_gw_year", "train_cpu_h_per_gw_year"):
                facts[f"{p}.{pol}.{c}"] = g(p, pol, c)
    # Pareto frontier (max F1 for <= energy) over all protocol x policy means
    pts = agg[["protocol", "policy", "kwh_per_gw_year", "mean_f1"]].sort_values("kwh_per_gw_year")
    best, front = -1, []
    for _, r in pts.iterrows():
        if r.mean_f1 > best:
            best = r.mean_f1; front.append(f"{r.protocol}/{r.policy}")
    facts["pareto_frontier"] = front
    # ---- age-aware cost of the full-history tree: refit time grows with the history ----------
    # fit cpu_s = a + b * flows_in_history over the every-window retrain events, all seeds, and
    # integrate over a year of 2,920 windows (linear growth -> quadratic cumulative cost)
    ev_rows, h0_list, f_list = [], [], []
    for p in glob.glob(os.path.join(RES, "replay_tree_local_every_1_s*.json")):
        r = json.load(open(p)); cum = 0
        for j, e in enumerate(r["events"]):
            cum += e["n_flows"]; ev_rows.append((cum, e["cpu_s"]))
            (h0_list if j == 0 else f_list).append(e["n_flows"])
    if ev_rows:
        ev = np.array(ev_rows); b, a = np.polyfit(ev[:, 0], ev[:, 1], 1)
        W = ASSUMPTIONS["windows_per_year"]
        H0 = float(np.median(h0_list))            # city flows of the initial training period
        F = float(np.median(f_list))              # city flows added per window (one re-training)
        # refit k (k = 1..W) sees H0 + F*k flows of history: sum of a + b*(H0 + F*k) over the year
        full_year = a * W + b * H0 * W + b * F * W * (W + 1) / 2    # x86 CPU-s, whole city
        capped = agg[(agg.protocol == "tree_cap") & (agg.policy == "every_1")].train_cpu_h_per_gw_year
        facts["tree_full_history_fit"] = dict(intercept_s=float(a), slope_s_per_flow=float(b), n_events=len(ev), initial_flows=H0, flows_per_window=F)
        facts["tree_full_history_age_aware_cpu_h_per_gw_year"] = float(full_year / 3600 / 5)
        facts["tree_cap_cpu_h_per_gw_year"] = float(capped.iloc[0]) if len(capped) else float("nan")
    with open(os.path.join(RES, "sustain_facts.json"), "w") as f:
        json.dump(facts, f, indent=1, default=float)

    workflow_figure()

    # ================= Figure 1: F1 per window under four policies (edge tree, 1-day cap) ======
    fig, axes = plt.subplots(2, 1, figsize=(7.6, 4.8), sharex=True, gridspec_kw=dict(height_ratios=[1, 2.6]))
    s0 = seeds[0]
    w = wt.set_index("window")
    axes[0].bar(w.index, w.attack_share, color="#9a9a9a", width=0.8)
    if not os.path.exists(os.path.join(RES, f"replay_tree_cap_every_1_s{s0}.json")):   # partial grid: any protocol
        pass
    axes[0].set_ylabel("attack share"); axes[0].set_ylim(0, 1)
    day_names = list(dict.fromkeys(wt.day))                    # capture order
    for dname in day_names:
        ww = wt[wt.day == dname].window
        label = dname[:3].capitalize() if not dname[0].isdigit() else dname[5:]   # "Mon" or "02-14"
        axes[0].text((ww.min() + ww.max()) / 2, 1.02, label, ha="center", va="bottom", fontsize=8, color="#444")
    n_win = int(wt.window.max()) + 1
    w_init = 16
    for pol in ("every_1", "drift", "static"):
        pth = os.path.join(RES, f"replay_tree_cap_{pol}_s{s0}.json")
        if os.path.exists(pth):
            w_init = int(json.load(open(pth))["summary"].get("w_init", 16)); break
    styles = {"static": ("#9a9a9a", "-"), "every_8": (COL["tree_cap"], "--"), "every_1": (COL["tree_local"], "-"),
              "drift": (COL["fedavg"], "-.")}
    for pol, (c, ls) in styles.items():
        p = os.path.join(RES, f"replay_tree_cap_{pol}_s{s0}.json")
        if not os.path.exists(p):
            continue
        pw = pd.DataFrame(json.load(open(p))["per_window"])
        axes[1].plot(pw.window, pw.f1, color=c, ls=ls, lw=1.6, label=f"re-train {POLICY_LABEL[pol]}")
        rt = pw[pw.retrained_after]
        yoff = -0.07 - 0.05 * list(styles).index(pol)
        axes[1].scatter(rt.window, [yoff] * len(rt), marker="|", color=c, s=40, lw=1.5)
        axes[1].text(w_init - 0.2, yoff, POLICY_LABEL[pol], ha="right", va="center", fontsize=7.5, color=c)
    axes[1].axvspan(-0.5, w_init - 0.5, color="#f0f0f0", zorder=0)
    axes[1].text((w_init - 1) / 2, 0.95, "initial training", ha="center", fontsize=8.5, color="#555")
    axes[1].set_title(f"{PROTO_LABEL['tree_cap']}, seed {s0}", fontsize=8.5, loc="right", color="#333")
    axes[1].axhline(-0.035, color="#cccccc", lw=0.5)
    axes[1].set_ylim(-0.25, 1.02); axes[1].set_xlim(-0.5, n_win - 0.5); axes[1].set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    axes[1].set_xlabel("window (8 per capture day, equal flow count)"); axes[1].set_ylabel("F1 on the window")
    axes[0].set_xlim(-0.5, n_win - 0.5)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), fontsize=8.5, ncol=4)
    save(fig, "figS1_f1_timeline")

    # ================= Figure 2: Pareto -- detection vs energy per gateway-year (two panels) ======
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 4.3), sharey=True)
    groups = [("edge protocols", ["tree_local", "tree_cap", "mlp_local"]), ("federated and centralised", ["fedavg", "lpra", "central"])]
    handles, labels_ = [], []
    for ax, (title, protos) in zip(axes, groups):
        for p in protos:
            d = agg[agg.protocol == p]
            if d.empty:
                continue
            h = ax.errorbar(d.kwh_per_gw_year, d.stream_f1, yerr=d.stream_f1_ci, xerr=d.kwh_per_gw_year_ci, fmt=MK[p],
                            color=COL[p], ms=5.5, lw=0.8, capsize=0, label=PROTO_LABEL[p],
                            mfc="white" if p in ("tree_cap", "lpra") else COL[p])
            handles.append(h); labels_.append(PROTO_LABEL[p])
        ax.set_xscale("log"); ax.set_title(title, fontsize=9)
        ax.set_xlabel("estimated energy per gateway-year, kWh")
        _lo, _hi = agg[agg.protocol.isin(protos)].kwh_per_gw_year.min(), agg[agg.protocol.isin(protos)].kwh_per_gw_year.max()
        ax.set_xlim(_lo / 3, _hi * 6)
    axes[0].set_ylabel("stream F1 over the held-out windows"); axes[0].set_ylim(-0.03, 1.05)
    fig.legend(handles, labels_, loc="lower center", ncol=3, fontsize=9, bbox_to_anchor=(0.5, -0.02), frameon=False)
    fig.subplots_adjust(bottom=0.27, wspace=0.08)
    # frontier labels, placed by a small search so that no label overlaps another label or a marker
    fig.canvas.draw(); renderer = fig.canvas.get_renderer()
    for ax, (title, protos) in zip(axes, groups):
        pts = agg[agg.protocol.isin(protos)][["protocol", "policy", "kwh_per_gw_year", "stream_f1"]].sort_values("kwh_per_gw_year")
        from matplotlib.transforms import Bbox
        _xy = ax.transData.transform(np.c_[agg[agg.protocol.isin(protos)].kwh_per_gw_year, agg[agg.protocol.isin(protos)].stream_f1])
        allpts = [Bbox.from_extents(x - 9, y - 9, x + 9, y + 9) for x, y in _xy]      # marker footprints
        placed = []
        # frontier points (each improves on everything cheaper); one label per policy; points that sit
        # on top of each other (same energy within 10 %, F1 within 0.02) share one label
        front, best, seen = [], 0.02, set()
        for _, r in pts.iterrows():
            if r.stream_f1 <= best + 0.01:
                continue
            best = r.stream_f1
            if r.policy in seen:
                continue
            seen.add(r.policy)
            if front and abs(np.log10(r.kwh_per_gw_year / front[-1]["x"])) < 0.05 and abs(r.stream_f1 - front[-1]["y"]) < 0.02:
                front[-1] = dict(x=r.kwh_per_gw_year, y=r.stream_f1, text=front[-1]["text"] + " / " + POLICY_LABEL[r.policy], policy=r.policy)
            else:
                front.append(dict(x=r.kwh_per_gw_year, y=r.stream_f1, text=POLICY_LABEL[r.policy], policy=r.policy))
        for fr in front:
            r = pd.Series(dict(kwh_per_gw_year=fr["x"], stream_f1=fr["y"], policy=fr["policy"], text=fr["text"]))
            cands = [(-7, 6, "right", "bottom"), (7, -6, "left", "top"), (7, 6, "left", "bottom"), (-7, -6, "right", "top"),
                     (-12, 0, "right", "center"), (12, 0, "left", "center")]
            cands += [(sx * 10, sy * k, "left" if sx > 0 else "right", "bottom" if sy > 0 else "top")
                      for k in (18, 30, 42, 54) for sx in (-1, 1) for sy in (-1, 1)]
            best_c, best_score = None, None
            for dx, dy, ha, va in cands:
                ann = ax.annotate(r.text, (r.kwh_per_gw_year, r.stream_f1), textcoords="offset points",
                                  xytext=(dx, dy), fontsize=8, ha=ha, va=va)
                bb = ann.get_window_extent(renderer).expanded(1.05, 1.15)
                axbb = ax.get_window_extent(renderer)
                score = 100 * sum(bb.overlaps(o) for o in placed) + sum(bb.overlaps(m) for m in allpts) \
                        + 1000 * (bb.x0 < axbb.x0 or bb.x1 > axbb.x1 or bb.y1 > axbb.y1 or bb.y0 < axbb.y0)
                ann.remove()
                if os.environ.get("LABEL_DEBUG") == "2" and r.policy == "every_1": print("cand", (dx, dy), score, [round(v) for v in bb.extents], [round(v) for v in axbb.extents])
                if best_score is None or score < best_score:
                    best_c, best_score = (dx, dy, ha, va), score
                if score == 0:
                    break
            dx, dy, ha, va = best_c
            if os.environ.get("LABEL_DEBUG"): print("label", title, r.policy, best_c, best_score, [tuple(round(v) for v in o.extents) for o in placed])
            ann = ax.annotate(r.text, (r.kwh_per_gw_year, r.stream_f1), textcoords="offset points",
                              xytext=(dx, dy), fontsize=8, ha=ha, va=va,
                              arrowprops=dict(arrowstyle="-", lw=0.4, color="#888") if abs(dy) > 10 else None)
            placed.append(ann.get_window_extent(renderer).expanded(1.05, 1.15))
    axes[0].annotate("never / alert-rate trigger", (agg.kwh_per_gw_year.min() * 1.2, 0.01), textcoords="offset points",
                     xytext=(4, 8), fontsize=7.5, color="#555")
    save(fig, "figS2_pareto")

    # ================= Figure 3: where the energy goes (every window) ==========================
    pol = "every_1" if (agg.policy == "every_1").any() else str(agg.policy.iloc[0])   # partial grids (smoke test)
    d = agg[agg.policy == pol].set_index("protocol").reindex(PROTO_ORDER).dropna(subset=["kwh_per_gw_year"])
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    parts = [("kwh_train_edge", "training on the gateway", "#0072B2"), ("kwh_train_cloud", "training in the cloud (per gateway share)", "#CC79A7"),
             ("kwh_infer_edge", "inference", "#009E73"), ("kwh_network", "network traffic (models, raw flows, ledger)", "#E69F00")]
    bottom = np.zeros(len(d)); x = np.arange(len(d))
    for c, lab, col in parts:
        v = d[c].values if c != "kwh_train_cloud" else d[c].values / 5
        ax.bar(x, v, bottom=bottom, color=col, label=lab, width=0.6, edgecolor="white", linewidth=1); bottom += v
    ax.set_xticks(x); ax.set_xticklabels([PROTO_LABEL[p] for p in d.index], rotation=20, ha="right", fontsize=8.5)
    ax.set_ylabel(f"estimated kWh per gateway-year,\nre-training {POLICY_LABEL[pol]}"); ax.legend(fontsize=9)
    save(fig, "figS3_energy_breakdown")

    # ================= Figure 4: scaling with K and anchoring granularity =======================
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4), gridspec_kw=dict(width_ratios=[1.1, 1], wspace=0.38))
    for p in PROTO_ORDER:
        s = sc[(sc.protocol == p) & (sc.policy == pol)]
        if s.empty:
            continue
        axes[0].plot(s.K, s.kgco2e_city_year, marker=MK[p], color=COL[p], ms=4, lw=1.4, label=PROTO_LABEL[p],
                     mfc="white" if p in ("tree_cap", "lpra") else COL[p])
    idle = ASSUMPTIONS["gateway_idle_W"] * 24 * 365 / 1000 * ASSUMPTIONS["kgCO2e_per_kWh"]
    axes[0].plot([5, 100], [idle * 5, idle * 100], color="#444", ls=":", lw=1.2, label="gateways idling (2.7 W)")
    axes[0].set_xlabel("districts K"); axes[0].set_ylabel("kg CO$_2$e per city-year")
    axes[0].set_xscale("log"); axes[0].set_yscale("log")
    axes[0].legend(fontsize=9, loc="upper left", bbox_to_anchor=(-0.25, -0.2), ncol=3)
    a = an[(an.policy == pol) & an.protocol.isin(["fedavg", "tree_cap"])]
    labels, vals, cols = [], [], []
    short = dict(fedavg="FedAvg", tree_cap="Edge tree")
    for p in [q for q in ("fedavg", "tree_cap") if (a.protocol == q).any()]:
        for _, r in a[a.protocol == p].iterrows():
            labels.append(f"{short[p]}\n{r.anchoring.replace('per-', 'per ')}"); vals.append(r.ledger_gb_per_year * 1000); cols.append(COL[p])
    bars = axes[1].bar(range(len(vals)), vals, color=cols, width=0.6)
    for b_, v in zip(bars, vals):
        axes[1].text(b_.get_x() + b_.get_width() / 2, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    axes[1].set_xticks(range(len(vals))); axes[1].set_xticklabels(labels, fontsize=8, rotation=35, ha="right", rotation_mode="anchor")
    axes[1].set_ylabel("ledger growth, MB per year (K = 5)")
    for ax_, letter in zip(axes, "ab"):
        ax_.text(0.0, 1.04, f"({letter})", transform=ax_.transAxes, fontsize=10, fontweight="bold", va="bottom", ha="left")
    save(fig, "figS4_scaling_anchoring")

    # ================= Figure 5: sensitivity ====================================================
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    s = se[se.protocol == ("fedavg" if (se.protocol == "fedavg").any() else se.protocol.iloc[0])]
    names = list(dict.fromkeys(s.assumption))
    for i, nm in enumerate(names):
        lo = s[(s.assumption == nm) & (s.level == "low")].kwh_per_gw_year.iloc[0]
        hi = s[(s.assumption == nm) & (s.level == "high")].kwh_per_gw_year.iloc[0]
        mid = s[(s.assumption == nm) & (s.level == "default")].kwh_per_gw_year.iloc[0]
        ax.plot([lo, hi], [i, i], color="#E69F00", lw=6, solid_capstyle="butt"); ax.plot(mid, i, "k|", ms=10)
    ASSUMPTION_LABEL = dict(edge_slowdown="edge slowdown (2–10×)", P_edge_W="edge power (2–6 W)",
                            kWh_per_GB_network="network intensity (0.01–0.30 kWh/GB)",
                            kgCO2e_per_kWh="grid factor (0.10–0.80 kg CO$_2$e/kWh; carbon only)")
    ax.set_yticks(range(len(names))); ax.set_yticklabels([ASSUMPTION_LABEL.get(n, n) for n in names], fontsize=7); ax.set_xscale("log")
    ax.set_xlabel(f"estimated kWh per gateway-year, FedAvg, re-training {POLICY_LABEL[pol]} (bar: low–high; tick: default)")
    save(fig, "figS5_sensitivity")
    print("facts ->", os.path.join(RES, "sustain_facts.json"))


if __name__ == "__main__":
    main()
