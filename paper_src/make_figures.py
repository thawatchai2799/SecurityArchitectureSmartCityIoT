#!/usr/bin/env python3
"""
make_figures.py -- regenerate every manuscript figure at publication resolution.

Reads only results/*.csv, results/*.json and results/paper_facts.json, so the figures can never
disagree with the tables and the prose: they are drawn from the same files.

Output for each figure, in results/figures/:
    <name>.png   600 dpi raster (what MDPI asks for)
    <name>.pdf   vector version of the same plot

Usage:  python paper_src/make_figures.py
        python paper_src/make_figures.py --check     (print the numbers each figure encodes, so
                                                      they can be compared with the tables by eye)
"""
from __future__ import annotations
import os, sys, json, argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(RES, "figures")
DPI = 600

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
    "figure.autolayout": False,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})

CHECK: list[str] = []


def note(s: str) -> None:
    CHECK.append(s)


def save(fig, name: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=DPI)
    # keep a copy at the old path so the DOCX generator finds it unchanged
    fig.savefig(os.path.join(RES, f"{name}.png"), dpi=DPI)
    plt.close(fig)
    print(f"  wrote {name}.png / .pdf")


def rd_csv(n):
    p = os.path.join(RES, n)
    return pd.read_csv(p) if os.path.exists(p) else None


def rd_json(n):
    p = os.path.join(RES, n)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


F = rd_json("paper_facts.json") or {}
POC = rd_json("poc_results.json") or {}


# --------------------------------------------------------------------------- #
# Figure 1 — architecture (numbers come from paper_facts.json)
# --------------------------------------------------------------------------- #
def fig_architecture():
    g = lambda k, d="?": F.get(k, d)
    edge = f"DT-8 IDS · {g('dt_kb')} KB\n{g('dt_us')} µs/flow"
    weights = f"weights only ({g('fl_weight_kb')} KB / round) ↔ global model"
    priv = f"A3 curious cloud\nmust not receive\nraw traffic\n({g('fl_raw_mb')} MB kept local)"
    note(f"Fig 1 architecture: edge box = {g('dt_kb')} KB / {g('dt_us')} us  (Table 4, seed 42); "
         f"weights = {g('fl_weight_kb')} KB/round (Table 6); raw kept local = {g('fl_raw_mb')} MB (Table 6)")

    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    ax.set_xlim(0, 12.6); ax.set_ylim(0, 9.75); ax.axis("off"); ax.grid(False)

    def box(x, y, w, h, text, fc="#FFFFFF", fs=6.2, ec="#333", lw=0.8, zorder=2):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.10",
                                    fc=fc, ec=ec, lw=lw, zorder=zorder))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.35,
                zorder=zorder + 1)

    def arrow(x1, y1, x2, y2, color="#333", ls="-", zorder=1):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=7,
                                     color=color, lw=0.8, ls=ls, zorder=zorder))

    bands = [("L1  IoT / network traffic (public TON_IoT testbed flows)", 0.15, 1.75, "#F3F6FA"),
             ("L2  Edge AI — district gateways", 2.20, 2.05, "#EAF3E6"),
             ("L3  Permissioned consortium ledger — city agencies", 4.70, 2.15, "#FDF1DE"),
             ("L4  Cloud security orchestrator", 7.20, 2.22, "#EDE7F6")]
    for name, y0, h, c in bands:
        ax.add_patch(FancyBboxPatch((0.15, y0), 10.25, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=c, ec="#BBB", lw=0.6))
        ax.text(0.30, y0 + h - 0.12, name, fontsize=7.4, fontweight="bold", va="top", color="#444",
                bbox=dict(facecolor=c, edgecolor="none", boxstyle="square,pad=0.20"), zorder=4)

    districts = ["Transport", "Energy", "Water", "Healthcare", "e-Gov"]
    xs = [0.45 + i * 2.0 for i in range(5)]
    for x, d in zip(xs, districts):
        box(x, 0.40, 1.75, 0.85, f"{d}\nIoT devices\n& sensors", fs=5.8)
        box(x, 2.38, 1.75, 1.30, f"Gateway {d}\n{edge}\nlocal FL training", fs=6.0)
        arrow(x + 0.875, 1.25, x + 0.875, 2.38)

    for i, v in enumerate(["Municipality IT", "City Police", "Electric Utility",
                           "Water Authority", "University"]):
        box(0.50 + i * 2.0, 4.90, 1.65, 0.62, f"validator:\n{v}", fs=5.8)
    box(0.55, 5.62, 9.45, 0.82,
        "block = header · prev-hash · Merkle root · PoA round-robin proposer · ≥ 2/3+1 endorsements;\n"
        "an enrolment list controls who may submit\n"
        "tx = ALERT{district, model-id, ts, SHA-256(evidence)}\n"
        "tx = MODEL_UPDATE{round, SHA-256(weights), accepted[], quarantined[], screening stats}", fs=4.9)

    box(0.50, 7.42, 3.05, 1.45, "Alert ingestion &\ncross-district correlation\n"
                                "(rate anomaly, ≥ 3 districts\nin one 10 s bin)", fs=5.8)
    box(3.75, 7.42, 3.05, 1.45, "LPRA aggregator\nmedian/MAD distance +\ndirection screen\n"
                                "FedAvg on accepted\n→ anchor model hash", fs=5.8)
    box(7.00, 7.42, 3.20, 1.45, "Audit & provenance\nMerkle-proof check of\ndistrict alert stores\n"
                                "model-hash verification", fs=5.8)

    for x in xs:
        arrow(x + 0.55, 3.68, x + 0.55, 4.90, color="#B8860B")
    ax.text(0.50, 4.36, "alert digests (hash only)", fontsize=6.2, color="#B8860B", bbox=dict(facecolor="white", edgecolor="none", boxstyle="square,pad=0.1"), zorder=5)
    # zorder=1.5 sits between the band backgrounds (zorder 1) and the boxes
    # (zorder 2), so this arrow is hidden behind the "Electric Utility"
    # validator box and the block-rule box it geometrically crosses, and
    # stays visible everywhere else (both open gaps carry its label).
    arrow(5.30, 3.68, 5.30, 7.42, color="#2E7D32", ls="--", zorder=1.5)
    ax.text(5.45, 4.36, weights, fontsize=6.2, color="#2E7D32")
    arrow(2.00, 6.92, 2.00, 7.42, color="#B8860B")
    ax.text(2.10, 7.06, "alerts", fontsize=6.2, color="#B8860B", bbox=dict(facecolor="white", edgecolor="none", boxstyle="square,pad=0.1"), zorder=5)
    arrow(6.40, 7.42, 6.40, 6.92, color="#6A1B9A")
    ax.text(6.50, 7.06, "MODEL_UPDATE tx", fontsize=6.2, color="#6A1B9A", bbox=dict(facecolor="white", edgecolor="none", boxstyle="square,pad=0.1"), zorder=5)
    arrow(8.60, 7.42, 8.60, 6.92, color="#6A1B9A", ls="--")
    ax.text(8.70, 7.06, "Merkle proofs", fontsize=6.2, color="#6A1B9A", bbox=dict(facecolor="white", edgecolor="none", boxstyle="square,pad=0.1"), zorder=5)
    arrow(9.95, 7.42, 9.95, 3.68, color="#C62828", ls=":")
    ax.text(10.02, 4.18, "audit\ndistrict\nstore", fontsize=6.0, color="#C62828")

    ax.text(11.5, 9.58, "Adversary model", fontsize=7.4, fontweight="bold", ha="center", color="#C62828")
    box(10.60, 7.60, 1.90, 1.28, priv, fc="#FFF5F5", ec="#C62828", fs=5.1)
    box(10.60, 5.10, 1.90, 1.45, "A2 insider\nforge or delete alerts,\nrogue or impersonating\nnode,\n"
                                 "model poisoning", fc="#FFF5F5", ec="#C62828", fs=5.1)
    box(10.60, 0.45, 1.90, 1.50, "A1 external\nDDoS/DoS, scanning,\ninjection, XSS,\npassword, backdoor,\n"
                                 "ransomware, MITM", fc="#FFF5F5", ec="#C62828", fs=5.1)
    save(fig, "fig1_architecture")


# --------------------------------------------------------------------------- #
# Figure 2 — edge IDS quality and footprint
# --------------------------------------------------------------------------- #
LBL = {"LogReg": "LogReg", "DecisionTree(d=8)": "DT-8", "RandomForest(20x8)": "RF 20×8",
       "MLP(32,16)": "MLP 32-16"}
ORDER = ["LogReg", "DecisionTree(d=8)", "RandomForest(20x8)", "MLP(32,16)"]


def fig_edge():
    a, b = rd_csv("exp1_edge_ids_benchmark.csv"), rd_csv("exp1b_common_features.csv")
    if a is None or b is None:
        return
    a, b = a.set_index("model"), b.set_index("model")
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.7))
    x = np.arange(len(ORDER)); w = 0.36
    ax[0].bar(x - w / 2, [a.loc[m, "f1"] for m in ORDER], w, label="native features (54)", color="#3A6EA5")
    ax[0].bar(x + w / 2, [b.loc[m, "f1"] for m in ORDER], w, label="common features (9)", color="#E08A3C")
    for i, m in enumerate(ORDER):
        ax[0].text(i - w / 2, a.loc[m, "f1"] + 0.004, f"{a.loc[m,'f1']:.3f}", ha="center", fontsize=5.8)
        ax[0].text(i + w / 2, b.loc[m, "f1"] + 0.004, f"{b.loc[m,'f1']:.3f}", ha="center", fontsize=5.8)
    ax[0].set_xticks(x); ax[0].set_xticklabels([LBL[m] for m in ORDER])
    ax[0].set_ylim(0.85, 1.03); ax[0].set_ylabel("F1 (attack vs normal)")
    ax[0].set_title("(a) detection quality"); ax[0].legend(loc="lower right", framealpha=0.9)

    ax[1].scatter(a["latency_us_per_flow"], a["model_size_kb"], s=34, color="#3A6EA5", zorder=3)
    for m in ORDER:
        dx = 1.12 if m != "RandomForest(20x8)" else 0.45
        ha = "left" if m != "RandomForest(20x8)" else "right"
        ax[1].annotate(LBL[m], (a.loc[m, "latency_us_per_flow"] * dx, a.loc[m, "model_size_kb"]),
                       fontsize=6.6, ha=ha, va="center")
    ax[1].set_xscale("log"); ax[1].set_yscale("log")
    ax[1].set_xlim(a["latency_us_per_flow"].min() * 0.55, a["latency_us_per_flow"].max() * 2.6)
    ax[1].set_ylim(a["model_size_kb"].min() * 0.45, a["model_size_kb"].max() * 3.2)
    ax[1].set_xlabel("per-flow inference latency (µs)"); ax[1].set_ylabel("model size (KB)")
    ax[1].set_title("(b) edge footprint")
    note("Fig 2a bars = exp1_edge_ids_benchmark.csv / exp1b_common_features.csv, i.e. Tables 4 and 5: "
         + ", ".join(f"{LBL[m]} {a.loc[m,'f1']:.3f}/{b.loc[m,'f1']:.3f}" for m in ORDER))
    note("Fig 2b axes = same file's latency_us_per_flow and model_size_kb columns (Table 4)")
    fig.tight_layout()
    save(fig, "fig1_edge_ids")


# --------------------------------------------------------------------------- #
# Figure 3 — federated convergence
# --------------------------------------------------------------------------- #
def fig_federated():
    fed = POC.get("exp3_federated")
    if not fed:
        return
    fig, ax = plt.subplots(figsize=(3.9, 2.7))
    for regime, colour in (("iid", "#3A6EA5"), ("non-iid", "#E08A3C")):
        h = fed[regime]["history"]
        ax.plot([r["round"] for r in h], [r["f1"] for r in h], marker="o", ms=3, lw=1.2,
                color=colour, label=f"FedAvg, {regime}")
    cen = fed["non-iid"]["centralised_f1"]; loc = fed["non-iid"]["local_only_f1_mean"]
    ax.axhline(cen, ls="--", lw=1.0, c="#333", label=f"centralised ({cen:.3f})")
    ax.axhline(loc, ls=":", lw=1.2, c="#C62828", label=f"local-only mean ({loc:.3f})")
    ax.set_xlabel("communication round"); ax.set_ylabel("global-model F1")
    ax.set_title("Federated vs centralised vs local-only")
    lo = min(loc, min(r["f1"] for r in fed["non-iid"]["history"]))
    ax.set_ylim(lo - 0.030, cen + 0.006)          # room for the legend below the curves
    ax.legend(loc="lower center", framealpha=1.0, fontsize=6.6, ncol=2,
              borderpad=0.35, handlelength=1.6, columnspacing=0.9)
    note(f"Fig 3 lines = poc_results exp3_federated history; end points "
         f"iid {fed['iid']['federated_f1']:.4f}, non-iid {fed['non-iid']['federated_f1']:.4f}; "
         f"reference lines centralised {cen:.4f} and local-only {loc:.4f} — all four are Table 6")
    fig.tight_layout()
    save(fig, "fig2_federated")


# --------------------------------------------------------------------------- #
# Figure 4 — Byzantine aggregator grid
# --------------------------------------------------------------------------- #
AGG = ["fedavg", "median", "trimmed_mean", "krum", "multi_krum", "lpra"]
AGG_LBL = ["FedAvg", "Median", "Trimmed\nMean", "Krum", "Multi-Krum", "LPRA\n(ours)"]


def fig_byzantine():
    g = rd_csv("extA_byzantine_grid_summary.csv")
    if g is None:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    rows = ["none", "scale", "flip", "noise", "stealth"]
    for ax, n in zip(axes, (1, 2)):
        M = np.full((len(rows), len(AGG)), np.nan)
        for i, atk in enumerate(rows):
            nn = 0 if atk == "none" else n
            for j, agg in enumerate(AGG):
                sub = g[(g.attack == atk) & (g.n_att == nn) & (g.aggregator == agg)]
                if len(sub):
                    M[i, j] = sub.f1_mean.iloc[0]
        im = ax.imshow(M, vmin=0.60, vmax=1.0, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(AGG))); ax.set_xticklabels(AGG_LBL, fontsize=6.4)
        ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=7)
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                if not np.isnan(M[i, j]):
                    ax.text(j, i, f"{M[i,j]:.3f}", ha="center", va="center", fontsize=5.9,
                            color="#111")
        ax.set_title(f"({'ab'[n-1]}) {n} Byzantine district" + ("s" if n > 1 else ""))
        ax.grid(False)
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label("global-model F1", fontsize=7.5); cb.ax.tick_params(labelsize=6.5)
    q = lambda a, n, agg: g[(g.attack == a) & (g.n_att == n) & (g.aggregator == agg)].f1_mean.iloc[0]
    note(f"Fig 4 cells = extA_byzantine_grid_summary.csv = Table 9 (e.g. none/FedAvg {q('none',0,'fedavg'):.3f}, "
         f"none/LPRA {q('none',0,'lpra'):.3f}, noise-1/FedAvg {q('noise',1,'fedavg'):.3f}, "
         f"flip-2/Krum {q('flip',2,'krum'):.3f})")
    save(fig, "fig6_byzantine_grid")


# --------------------------------------------------------------------------- #
# Figure 5 — ledger overhead and latency
# --------------------------------------------------------------------------- #
def fig_ledger():
    L = POC.get("exp4_ledger")
    if not L:
        return
    fig, ax = plt.subplots(1, 2, figsize=(5.4, 2.5))
    ax[0].bar(["plain DB", "on-chain"], [L["plain_db_bytes"] / 1e6, L["onchain_bytes"] / 1e6],
              color=["#8C8C8C", "#3A6EA5"], width=0.55)
    for i, v in enumerate([L["plain_db_bytes"] / 1e6, L["onchain_bytes"] / 1e6]):
        ax[0].text(i, v + 0.05, f"{v:.2f} MB", ha="center", fontsize=6.8)
    ax[0].set_ylabel(f"storage for {L['tx_submitted']:,} alerts (MB)")
    ax[0].set_ylim(0, L["onchain_bytes"] / 1e6 * 1.25)
    ax[0].set_title(f"(a) storage overhead ×{L['storage_overhead_x']:.2f}")
    ax[1].bar(["tx confirm", "block commit"], [L["avg_tx_confirm_ms"], L["avg_block_commit_ms"]],
              color=["#3A6EA5", "#E08A3C"], width=0.55)
    for i, v in enumerate([L["avg_tx_confirm_ms"], L["avg_block_commit_ms"]]):
        ax[1].text(i, v + 0.02, f"{v:.2f} ms", ha="center", fontsize=6.8)
    ax[1].set_ylabel("mean latency (ms)")
    ax[1].set_ylim(0, max(L["avg_tx_confirm_ms"], L["avg_block_commit_ms"]) * 1.3)
    ax[1].set_title(f"(b) emulated ledger, {L['tx_per_s']/1e4:.1f} × 10⁴ tx/s")
    note(f"Fig 5 = poc_results exp4_ledger: {L['plain_db_bytes']/1e6:.2f} vs {L['onchain_bytes']/1e6:.2f} MB "
         f"(×{L['storage_overhead_x']:.2f}), confirm {L['avg_tx_confirm_ms']:.2f} ms, "
         f"commit {L['avg_block_commit_ms']:.2f} ms — the values quoted in §5.5 and Table 14 row 1")
    fig.tight_layout()
    save(fig, "fig3_ledger")


# --------------------------------------------------------------------------- #
# Figure 6 — scalability (districts, validators, block size)
# --------------------------------------------------------------------------- #
def fig_scalability():
    # NOTE (v2.0 revision): panel (a) is regenerated from table13_definitive
    # (review_response/) via extC_districts_scaling.csv.  Panels (b) and (c)
    # must be drawn from the MEASURED extC_validators_scaling.csv and
    # extC_blocksize_sweep.csv of the original run; the three-point CSVs
    # shipped in results/ for those two panels are placeholders reconstructed
    # from the text and are NOT measurements -- the committed figure keeps the
    # original measured panels.  See CHANGELOG, "Figure 7".
    c1, c2, c3 = (rd_csv("extC_districts_scaling.csv"), rd_csv("extC_validators_scaling.csv"),
                  rd_csv("extC_blocksize_sweep.csv"))
    if c1 is None or c2 is None or c3 is None:
        return
    fig, ax = plt.subplots(1, 3, figsize=(7.4, 2.5))
    styles = {("fedavg", "none"): ("#8C8C8C", "o", "FedAvg, no attack"),
              ("fedavg", "scale"): ("#C62828", "s", "FedAvg, 20% Byzantine"),
              ("lpra", "none"): ("#3A6EA5", "o", "LPRA, no attack"),
              ("lpra", "scale"): ("#2E7D32", "s", "LPRA, 20% Byzantine")}
    for (agg, atk), (col, mk, lab) in styles.items():
        s = c1[(c1.aggregator == agg) & (c1.attack == atk)].sort_values("K")
        ax[0].plot(s.K, s.f1, marker=mk, ms=3.5, lw=1.1, color=col, label=lab,
                   ls="-" if agg == "lpra" else "--")
    ax[0].set_xscale("log", base=2); ax[0].set_xticks(sorted(c1.K.unique()))
    ax[0].set_xticklabels(sorted(c1.K.unique()))
    ax[0].set_xlabel("districts K"); ax[0].set_ylabel("global-model F1")
    # Legend goes below the data band: the FedAvg-under-attack points at K=5-10
    # (0.938-0.941) sit exactly where a lower-left legend would cover them.
    ax[0].set_ylim(0.915, 0.978)
    ax[0].set_title("(a) districts"); ax[0].legend(fontsize=5.9, loc="lower right", framealpha=0.9, ncol=1)

    ax[1].plot(c2.validators, c2.tx_per_s / 1e4, marker="o", ms=3.5, lw=1.1, color="#3A6EA5")
    ax[1].set_xlabel("validators"); ax[1].set_ylabel("throughput (× 10⁴ tx/s)", color="#3A6EA5")
    ax[1].tick_params(axis="y", labelcolor="#3A6EA5")
    ax[1].set_ylim(0, c2.tx_per_s.max() / 1e4 * 1.35)
    a2 = ax[1].twinx(); a2.grid(False)
    a2.plot(c2.validators, c2.storage_overhead_x, marker="s", ms=3.5, lw=1.1, color="#C62828")
    a2.set_ylabel("storage overhead (×)", color="#C62828"); a2.tick_params(axis="y", labelcolor="#C62828")
    a2.set_ylim(1.5, 2.0)
    ax[1].set_title("(b) validators")

    ax[2].plot(c3.block_size, c3.tx_confirm_ms, marker="o", ms=3.5, lw=1.1, color="#3A6EA5")
    ax[2].set_xscale("log"); ax[2].set_yscale("log")
    ax[2].set_xlabel("block size (tx)"); ax[2].set_ylabel("confirm latency (ms)", color="#3A6EA5")
    ax[2].tick_params(axis="y", labelcolor="#3A6EA5")
    a3 = ax[2].twinx(); a3.grid(False)
    a3.plot(c3.block_size, c3.storage_overhead_x, marker="s", ms=3.5, lw=1.1, color="#C62828")
    a3.set_ylabel("storage overhead (×)", color="#C62828"); a3.tick_params(axis="y", labelcolor="#C62828")
    a3.set_ylim(1.5, 2.4)
    ax[2].set_title("(c) block size")
    note(f"Fig 6a = extC_districts_scaling.csv = Table 12; 6b = extC_validators_scaling.csv "
         f"({c2.tx_per_s.min()/1e4:.1f}-{c2.tx_per_s.max()/1e4:.1f} × 10⁴ tx/s, overhead "
         f"{c2.storage_overhead_x.min():.2f}-{c2.storage_overhead_x.max():.2f}×); 6c = extC_blocksize_sweep.csv "
         f"({c3.tx_confirm_ms.min():.2f}-{c3.tx_confirm_ms.max():.1f} ms, "
         f"{c3.storage_overhead_x.max():.2f}-{c3.storage_overhead_x.min():.2f}×) — the values quoted in §5.6")
    fig.tight_layout()
    save(fig, "fig7_scalability")


# --------------------------------------------------------------------------- #
# Figure 7 — zero-day ransomware timeline
# --------------------------------------------------------------------------- #
def fig_scenario():
    sc = rd_json("extD_scenario.json")
    if not sc:
        return
    fig, ax = plt.subplots(figsize=(6.6, 2.3))
    order = ["Healthcare", "Water", "Transport"]
    ons, fa = sc["onset_s"], sc["first_true_alert_s"]
    flag = sc.get("L4_district_anomaly_flag_s", {})
    for i, d in enumerate(order):
        ax.plot([ons[d], 480], [i, i], lw=6, color="#E8E8E8", solid_capstyle="butt", zorder=1)
        ax.plot([ons[d]], [i], marker="|", ms=11, color="#111", zorder=3)
        ax.text(ons[d], i + 0.30, f"onset {ons[d]:.0f} s", fontsize=6.4, ha="center")
        ax.plot([fa[d]], [i], marker="^", ms=5.5, color="#C62828", zorder=4)
        ax.text(fa[d] + 16, i + 0.02, f"L2 alert +{fa[d]-ons[d]:.1f} s", fontsize=6.4,
                color="#C62828", va="center")
        if d in flag:
            ax.plot([flag[d]], [i], marker="s", ms=4, color="#B8860B", zorder=4)
            ax.text(flag[d] + 16, i - 0.30, f"L4 district anomaly at {flag[d]:.0f} s", fontsize=6.0,
                    color="#B8860B", va="center")
    t = sc["L4_campaign_declared_s"]
    ax.axvline(t, ls="--", lw=1.1, color="#3A6EA5")
    ax.text(t - 8, 2.92, f"L4: city-wide campaign declared, {t:.0f} s", color="#3A6EA5",
            fontsize=6.8, ha="right")
    ax.set_yticks(range(len(order))); ax.set_yticklabels(order)
    ax.set_xlabel("simulated time (s)"); ax.set_xlim(0, 505); ax.set_ylim(-0.65, 3.25)
    ax.set_title("Zero-day ransomware campaign: per-layer detection timeline")
    note(f"Fig 7 = extD_scenario.json: delays "
         f"{', '.join(f'{d} {fa[d]-ons[d]:.2f} s' for d in order)}; campaign at {t:.0f} s — §5.8")
    fig.tight_layout()
    save(fig, "fig8_scenario_timeline")


# --------------------------------------------------------------------------- #
# Figure 8 — cross-dataset transfer
# --------------------------------------------------------------------------- #
def fig_cross():
    for view, tag, title in (("common9", "common", "(a) nine directional features"),
                             ("dirfree4", "dirfree", "(b) four direction-free features")):
        pass
    a = rd_csv("exp2_cross_dataset_f1_common9.csv")
    b = rd_csv("exp2_cross_dataset_f1_dirfree4.csv")
    if a is None and b is None:
        return
    panels = [(a, "(a) nine directional features"), (b, "(b) four direction-free features")]
    panels = [(d, t) for d, t in panels if d is not None]
    fig, axes = plt.subplots(1, len(panels), figsize=(3.9 * len(panels), 3.0))
    if len(panels) == 1:
        axes = [axes]
    for ax, (d, title) in zip(axes, panels):
        d = d.set_index(d.columns[0])
        im = ax.imshow(d.values, vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(len(d.columns))); ax.set_xticklabels(d.columns, rotation=30, ha="right")
        ax.set_yticks(range(len(d.index))); ax.set_yticklabels(d.index)
        for i in range(d.shape[0]):
            for j in range(d.shape[1]):
                v = d.values[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.6,
                        color="w" if v < 0.6 else "#111")
        ax.set_xlabel("tested on"); ax.set_ylabel("trained on")
        ax.set_title(title); ax.grid(False)
        note(f"Fig 8 {title}: diagonal mean {np.mean([d.values[i,i] for i in range(min(d.shape))]):.2f}, "
             f"off-diagonal mean "
             f"{np.mean([d.values[i,j] for i in range(d.shape[0]) for j in range(d.shape[1]) if i!=j]):.2f}"
             " — Table 13a/13b and §5.9")
    fig.subplots_adjust(wspace=0.55)
    cb = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.03)
    cb.set_label("F1", fontsize=7.5); cb.ax.tick_params(labelsize=6.5)
    save(fig, "fig5_cross_dataset")



# --------------------------------------------------------------------------- #
# Figure 9 — temporal evaluation (static vs rolling re-training)
# --------------------------------------------------------------------------- #
def fig_temporal():
    d = rd_csv("exp15_temporal_cicids.csv")
    t = rd_json("exp15_temporal_cicids.json")
    if d is None or t is None:
        return
    days = [x for x in ["monday", "tuesday", "wednesday", "thursday", "friday"] if x in set(d.day)]
    xs = np.arange(len(days))
    st = d[d.protocol == "static"].set_index("day")
    ro = d[d.protocol == "rolling"].set_index("day")
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.6))

    ax[0].axhline(t["control"]["f1"], ls="--", lw=1.1, color="#8C8C8C",
                  label=f"random split over the week ({t['control']['f1']:.2f})")
    ax[0].plot(xs, [st.loc[x, "f1"] for x in days], marker="o", ms=4, lw=1.3, color="#C62828",
               label="static: trained once on days 1–%d" % t["n_train_days"])
    rx = [i for i, x in enumerate(days) if x in ro.index]
    ax[0].plot(rx, [ro.loc[days[i], "f1"] for i in rx], marker="s", ms=4, lw=1.3, color="#2E7D32",
               label="rolling: re-trained on all earlier days")
    ax[0].axvspan(-0.4, t["n_train_days"] - 0.6, color="#3A6EA5", alpha=0.07)
    ax[0].text(0.04, 0.06, "training days", transform=ax[0].transAxes, fontsize=6.4, color="#3A6EA5")
    ax[0].set_xticks(xs); ax[0].set_xticklabels([x[:3].capitalize() for x in days])
    ax[0].set_ylim(-0.05, 1.05); ax[0].set_ylabel("F1 on that day")
    ax[0].set_title("(a) detection over the capture week")
    ax[0].set_ylim(-0.06, 1.34)                      # headroom for the legend above the curves
    ax[0].legend(fontsize=5.4, loc="upper center", ncol=1, framealpha=1.0,
                 borderpad=0.3, handlelength=1.5, labelspacing=0.25)

    w = 0.38
    test_days = [x for x in days if x in ro.index]
    tx = np.arange(len(test_days))
    ax[1].bar(tx - w / 2, [st.loc[x, "recall"] for x in test_days], w, color="#C62828", label="static")
    ax[1].bar(tx + w / 2, [ro.loc[x, "recall"] for x in test_days], w, color="#2E7D32", label="rolling")
    for i, x in enumerate(test_days):
        ax[1].text(i - w / 2, st.loc[x, "recall"] + 0.012, f"{st.loc[x,'recall']:.3f}", ha="center", fontsize=6)
        ax[1].text(i + w / 2, ro.loc[x, "recall"] + 0.012, f"{ro.loc[x,'recall']:.3f}", ha="center", fontsize=6)
    ax[1].set_xticks(tx); ax[1].set_xticklabels([x.capitalize() for x in test_days])
    ax[1].set_ylabel("recall on unseen days"); ax[1].set_ylim(0, max(0.35, ro.recall.max() * 1.3))
    ax[1].set_title("(b) value of continuous re-training"); ax[1].legend(fontsize=6.4)
    note(f"Fig 9 = exp15_temporal_cicids.csv: random-split control {t['control']['f1']:.4f}; static "
         f"Thu {st.loc['thursday','f1']:.4f} / Fri {st.loc['friday','f1']:.4f}; rolling Fri "
         f"{ro.loc['friday','f1']:.4f} — Table 15 and §5.11")
    fig.tight_layout()
    save(fig, "fig9_temporal")


# --------------------------------------------------------------------------- #
# Figure 10 — adaptive attacker: where the screen holds and where it broke
# --------------------------------------------------------------------------- #
def fig_adaptive():
    a = rd_csv("exp17_adaptive_sweep.csv")
    if a is None:
        return
    a = a[a.direction != "none"]
    ns = sorted(a.n_att.unique())
    fig, axes = plt.subplots(1, len(ns), figsize=(3.7 * len(ns), 2.7), sharey=True)
    if len(ns) == 1:
        axes = [axes]
    style = {("fedavg", "opposite"): ("#8C8C8C", "--", "o", "FedAvg, opposing"),
             ("fedavg", "orthogonal"): ("#BDBDBD", ":", "o", "FedAvg, orthogonal"),
             ("lpra_v1", "opposite"): ("#C62828", "-", "s", "LPRA v1, opposing"),
             ("lpra_v1", "orthogonal"): ("#EF9A9A", ":", "s", "LPRA v1, orthogonal"),
             ("lpra_v2", "opposite"): ("#2E7D32", "-", "^", "LPRA v2, opposing"),
             ("lpra_v2", "orthogonal"): ("#A5D6A7", ":", "^", "LPRA v2, orthogonal")}
    for ax, n in zip(axes, ns):
        sub = a[a.n_att == n]
        for (agg, d), (col, ls, mk, lab) in style.items():
            q = sub[(sub.aggregator == agg) & (sub.direction == d)].sort_values("strength")
            if q.empty:
                continue
            ax.plot(q.strength, q.f1, ls=ls, marker=mk, ms=3.5, lw=1.1, color=col, label=lab)
        ax.axvline(2.5, color="#3A6EA5", lw=0.9, ls="-.")
        ax.text(2.62, 0.30, "stage-1 threshold γ = 2.5", fontsize=5.8, color="#3A6EA5", rotation=90)
        ax.set_xscale("log"); ax.set_xlabel("attacker distance ÷ honest median distance")
        ax.set_title(f"({'ab'[list(ns).index(n)]}) {int(n)} Byzantine district" + ("s" if n > 1 else ""))
        ax.set_ylim(-0.05, 1.05)
    axes[0].set_ylabel("global-model F1")
    axes[0].legend(fontsize=5.6, loc="lower left", framealpha=0.95, ncol=1)
    def g(agg, d, s, n):
        q = a[(a.aggregator == agg) & (a.direction == d) & (a.strength == s) & (a.n_att == n)]
        return None if q.empty else q.f1.iloc[0]
    note(f"Fig 10 = exp17_adaptive_sweep.csv = Table 17: the v1 break at 2 attackers, opposing, "
         f"strength 6 is F1 {g('lpra_v1','opposite',6.0,2):.4f} against {g('lpra_v2','opposite',6.0,2):.4f} "
         f"for v2 — §5.3")
    fig.tight_layout()
    save(fig, "fig10_adaptive")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="print what each figure encodes")
    a = ap.parse_args()
    print(f"figures -> {OUT}  ({DPI} dpi PNG + PDF)")
    fig_architecture(); fig_edge(); fig_federated(); fig_byzantine()
    fig_ledger(); fig_scalability(); fig_scenario(); fig_cross()
    fig_temporal(); fig_adaptive()
    print("\nconsistency notes (compare with the tables):")
    for line in CHECK:
        print("  * " + line)


if __name__ == "__main__":
    sys.exit(main())
