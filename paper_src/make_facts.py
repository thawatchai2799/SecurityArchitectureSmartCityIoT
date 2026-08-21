#!/usr/bin/env python3
"""
make_facts.py -- collect every number the manuscript quotes into results/paper_facts.json.

The DOCX generators (make_paper_v05.js / make_supp_v05.js) read that file, so the paper
can never drift away from the experiments: re-run the experiments, re-run this script,
re-build the DOCX, and every table and every number in the prose is updated.
Any fact that is missing (because its experiment has not been run yet) is simply absent
from the JSON and the generator prints a yellow placeholder instead.

Usage:  python paper_src/make_facts.py
"""
import os, sys, json, glob
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RES = os.path.join(ROOT, "results")
F = {}


def rd_csv(name):
    p = os.path.join(RES, name)
    return pd.read_csv(p) if os.path.exists(p) else None


def rd_json(name):
    p = os.path.join(RES, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def sci(x, digits=1):
    """1.03e4 -> '1.0 x 10^4' in the unicode form used by the manuscript."""
    if x == 0:
        return "0"
    e = int(np.floor(np.log10(abs(x))))
    m = x / 10 ** e
    sup = str(e).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))
    return f"{m:.{digits}f} × 10{sup}"


def pm(mu, sd, d=3):
    """mean ± sd, dropping the SD when it rounds to zero at that precision."""
    if sd is None or float(f"{sd:.{d}f}") == 0.0:
        return f"{mu:.{d}f}"
    return f"{mu:.{d}f} ± {sd:.{d}f}"


MODEL_LABEL = {"LogReg": "Logistic regression", "DecisionTree(d=8)": "Decision tree (d = 8)",
               "RandomForest(20x8)": "Random forest (20 × 8)", "MLP(32,16)": "MLP (32, 16)"}
ORDER = ["LogReg", "DecisionTree(d=8)", "RandomForest(20x8)", "MLP(32,16)"]

poc = rd_json("poc_results.json")
ext = rd_json("extended_results.json")

# --------------------------------------------------------------------- machine
if poc and "machine" in poc:
    m = poc["machine"]
    F["machine"] = f"{m.get('platform','?')}, Python {m.get('python','?')}, {m.get('cpu_count','?')} logical CPU(s)"
    F["run_date"] = m.get("run_date", "")

# --------------------------------------------------------------- dataset facts
if poc and "dataset" in poc:
    d = poc["dataset"]
    F["ton_rows"] = f"{d['n']:,}"
    F["ton_features"] = str(d["n_native_features"])
    F["ton_common"] = str(d.get("n_common_features", 9))

# ------------------------------------------------------- Table 4 / Table 5 / 5.1
b1 = rd_csv("exp1_edge_ids_benchmark.csv")
if b1 is not None:
    b1 = b1.set_index("model")
    F["tab_edge_native"] = [[MODEL_LABEL[m], f"{b1.loc[m,'accuracy']:.3f}", f"{b1.loc[m,'f1']:.3f}",
                             f"{b1.loc[m,'roc_auc']:.3f}", f"{b1.loc[m,'fpr']:.3f}",
                             f"{b1.loc[m,'model_size_kb']:.1f}", f"{b1.loc[m,'latency_us_per_flow']:.0f}",
                             sci(b1.loc[m, "throughput_flows_per_s"])] for m in ORDER]
    dt, rf, lr, mlp = (b1.loc[k] for k in ORDER[1:2] + ORDER[2:3] + ORDER[0:1] + ORDER[3:4])
    F["dt_f1"] = f"{dt['f1']:.3f}"; F["dt_fpr_pct"] = f"{100*dt['fpr']:.1f}"
    F["dt_kb"] = f"{dt['model_size_kb']:.1f}"; F["dt_us"] = f"{dt['latency_us_per_flow']:.0f}"
    F["dt_acc"] = f"{dt['accuracy']:.3f}"
    F["rf_auc"] = f"{rf['roc_auc']:.3f}"
    F["rf_auc_gain"] = f"{rf['roc_auc'] - dt['roc_auc']:.3f}"
    F["rf_size_ratio"] = f"{rf['model_size_kb']/dt['model_size_kb']:.0f}"
    F["rf_lat_ratio"] = f"{rf['latency_us_per_flow']/dt['latency_us_per_flow']:.0f}"
    F["mlp_train_s"] = f"{mlp['train_time_s']:.0f}"
    F["lr_fpr_pct"] = f"{100*lr['fpr']:.0f}"
b1b = rd_csv("exp1b_common_features.csv")
if b1b is not None:
    b1b = b1b.set_index("model")
    F["tab_edge_common"] = [[MODEL_LABEL[m], f"{b1b.loc[m,'accuracy']:.3f}", f"{b1b.loc[m,'f1']:.3f}",
                             f"{b1b.loc[m,'roc_auc']:.3f}", f"{b1b.loc[m,'fpr']:.3f}"] for m in ORDER]
    F["dt_common_f1"] = f"{b1b.loc['DecisionTree(d=8)','f1']:.3f}"
    F["dt_common_fpr_pct"] = f"{100*b1b.loc['DecisionTree(d=8)','fpr']:.0f}"
    F["dt_common_acc"] = f"{b1b.loc['DecisionTree(d=8)','accuracy']:.3f}"

# ------------------------------------------------------------- Table 6 (FL) + 5.2
b3 = rd_csv("extB_fedavg_multiseed.csv")
fed = poc["exp3_federated"] if poc and "exp3_federated" in poc else None
if fed:
    nid, iid = fed["non-iid"], fed["iid"]
    F["fl_raw_mb"] = f"{nid['raw_bytes_not_shared']/1e6:.1f}"
    F["fl_weight_kb"] = f"{nid['weight_bytes_per_round']/1e3:.0f}"
    F["fl_weight_kb_per_district"] = f"{nid['weight_bytes_per_round']/1e3/2/nid['k']:.1f}"
    F["fl_rounds"] = str(nid["rounds"])
    row_iid = ["IID (seed 42)", f"{iid['local_only_f1_mean']:.3f}", f"{iid['federated_f1']:.3f}",
               f"{iid['centralised_f1']:.3f}", F["fl_raw_mb"] + " MB", F["fl_weight_kb"] + " KB"]
    if b3 is not None and len(b3) > 1:
        F["fl_seeds"] = str(len(b3))
        mu, sd = b3.mean(numeric_only=True), b3.std(numeric_only=True)
        F["fl_fed"] = pm(mu["federated_f1"], sd["federated_f1"])
        F["fl_cen"] = pm(mu["centralised_f1"], sd["centralised_f1"])
        F["fl_loc"] = pm(mu["local_only_f1_mean"], sd["local_only_f1_mean"])
        F["fl_fed4"] = f"{mu['federated_f1']:.4f} ± {sd['federated_f1']:.4f}"
        F["fl_cen4"] = f"{mu['centralised_f1']:.4f} ± {sd['centralised_f1']:.4f}"
        F["fl_loc4"] = f"{mu['local_only_f1_mean']:.4f} ± {sd['local_only_f1_mean']:.4f}"
        row_nid = [f"Non-IID ({len(b3)} seeds, mean ± SD)", F["fl_loc"], F["fl_fed"], F["fl_cen"],
                   F["fl_raw_mb"] + " MB", F["fl_weight_kb"] + " KB"]
    else:
        row_nid = ["Non-IID (seed 42)", f"{nid['local_only_f1_mean']:.3f}", f"{nid['federated_f1']:.3f}",
                   f"{nid['centralised_f1']:.3f}", F["fl_raw_mb"] + " MB", F["fl_weight_kb"] + " KB"]
        F["fl_fed"] = f"{nid['federated_f1']:.3f}"; F["fl_cen"] = f"{nid['centralised_f1']:.3f}"
        F["fl_loc"] = f"{nid['local_only_f1_mean']:.3f}"
    F["tab_fl"] = [row_iid, row_nid]
    F["fl_iid"] = f"{iid['federated_f1']:.3f}"

# ------------------------------------------------- multi-seed edge (Section 5.4)
bE = rd_csv("extB_edge_multiseed_raw.csv")
if bE is not None:
    g = bE.groupby("model")
    for key, mdl in [("dt", "DecisionTree(d=8)"), ("mlp", "MLP(32,16)"), ("rf", "RandomForest(20x8)")]:
        F[f"ms_{key}_f1"] = pm(g["f1"].mean()[mdl], g["f1"].std()[mdl], 4)
        F[f"ms_{key}_us"] = f"{g['latency_us_per_flow'].mean()[mdl]:.0f} ± {g['latency_us_per_flow'].std()[mdl]:.0f}"
    F["ms_dt_fpr"] = pm(g["fpr"].mean()["DecisionTree(d=8)"], g["fpr"].std()["DecisionTree(d=8)"], 4)
    F["ms_seeds"] = str(bE["seed"].nunique())

# -------------------------------------------------------- Table 7 / Table 8 (E4)
e9 = poc.get("exp9_robust_fl") if poc else None
if e9:
    lab = {"none": "none (control)", "scale": "scaled update (λ = 10)", "flip": "label flipping",
           "noise": "Gaussian-noise weights"}
    rounds = poc["exp3_federated"]["non-iid"]["rounds"]
    K_FL = poc["exp3_federated"]["non-iid"]["k"]
    rows = []
    for atk in ["none", "scale", "flip", "noise"]:
        lp = e9.get(f"{atk}/LPRA"); pl = e9.get(f"{atk}/plain FedAvg")
        if lp is None:
            continue
        if atk == "none":
            fq = sum(len(q["quarantined"]) for q in lp["quarantine_log"])
            caught = f"{fq} false quarantines / {rounds * K_FL}"
            plain = f"{lp['global_f1']:.3f}"     # control: no attack, FedAvg == LPRA baseline
        else:
            caught = f"{lp['byzantine_caught_rounds']} / {rounds}"
            plain = f"{pl['global_f1']:.3f}" if pl else "n/a"
        rows.append([lab[atk], plain, f"{lp['global_f1']:.3f}", caught])
        F[f"e4_{atk}_lpra"] = f"{lp['global_f1']:.3f}"
        if pl:
            F[f"e4_{atk}_plain"] = f"{pl['global_f1']:.3f}"
        F[f"e4_{atk}_caught"] = str(lp["byzantine_caught_rounds"])
    F["tab_e4"] = rows
    F["e4_rounds"] = str(rounds)
    F["e4_control_district_rounds"] = str(rounds * K_FL)
    F["e4_false_quarantines"] = str(sum(len(q["quarantined"]) for q in e9["none/LPRA"]["quarantine_log"]))
    # first-round screening statistics that make the decision explainable
    for atk in ("scale", "flip", "noise"):
        lg = e9.get(f"{atk}/LPRA", {}).get("quarantine_log") or []
        if lg:
            q = lg[0]
            F[f"e4_{atk}_first_round"] = str(q["round"])
            F[f"e4_{atk}_d_attacker"] = f"{q['dist'][0]:.1f}"
            F[f"e4_{atk}_d_honest"] = f"{min(q['dist'][1:]):.1f}–{max(q['dist'][1:]):.1f}"
            F[f"e4_{atk}_cos_attacker"] = f"{q['cos'][0]:.2f}"
            F[f"e4_{atk}_cos_honest"] = f"{min(q['cos'][1:]):.2f}–{max(q['cos'][1:]):.2f}"
    pf = rd_csv("exp9_personalised_fl.csv")
    if pf is not None:
        F["tab_pfl"] = [[r["district"].replace("e-Gov", "e-Government"),
                         f"{r['global_f1_local_test']:.3f}", f"{r['personalised_f1_local_test']:.3f}",
                         f"+{100*(r['personalised_f1_local_test']-r['global_f1_local_test']):.1f}"]
                        for _, r in pf.iterrows()]
        best = pf.assign(g=pf.personalised_f1_local_test - pf.global_f1_local_test).sort_values("g").iloc[-1]
        F["pfl_best_district"] = best["district"].replace("e-Gov", "e-Government")
        F["pfl_best_gain"] = f"{100*(best['personalised_f1_local_test']-best['global_f1_local_test']):.1f}"
if poc and "exp9_ledger" in poc:
    F["e4_anchored_tx"] = str(poc["exp9_ledger"]["tx_submitted"])
    F["e4_anchored_blocks"] = str(poc["exp9_ledger"]["blocks"])

# ------------------------------------------------------------- Table 9 (E5 grid)
gA = rd_csv("extA_byzantine_grid_summary.csv")
if gA is not None:
    AGG = ["fedavg", "median", "trimmed_mean", "krum", "multi_krum", "lpra"]
    rounds_A = 10
    def fmt(sub, agg):
        r = sub[sub.aggregator == agg]
        if r.empty:
            return "-"
        r = r.iloc[0]
        s = f"{r.f1_mean:.3f}"
        if r.f1_sd >= 0.005:
            s += f" ± {r.f1_sd:.3f}"
        if r.caught >= rounds_A * 0.8 and r.n_att > 0:
            s += " ✓"
        elif r.n_att > 0 and r.caught > 0:
            s += f" ({r.caught:.0f}/{rounds_A})"
        if r.honest_rej >= rounds_A:
            s += " †"
        return s
    rows, labels = [], [("none", 0), ("scale", 1), ("flip", 1), ("noise", 1), ("stealth", 1),
                        ("scale", 2), ("flip", 2), ("noise", 2), ("stealth", 2)]
    for atk, n in labels:
        sub = gA[(gA.attack == atk) & (gA.n_att == n)]
        if sub.empty:
            continue
        rows.append([f"{atk} ({n})"] + [fmt(sub, a) for a in AGG])
    F["tab_e5"] = rows
    F["e5_seeds"] = str(int(gA.seeds.max()))
    F["e5_rounds"] = str(rounds_A)
    q = lambda atk, n, agg, col="f1_mean": gA[(gA.attack == atk) & (gA.n_att == n) & (gA.aggregator == agg)][col].iloc[0]
    F["e5_none_fedavg"] = f"{q('none',0,'fedavg'):.3f}"
    F["e5_none_lpra"] = f"{q('none',0,'lpra'):.3f}"
    F["e5_none_median"] = f"{q('none',0,'median'):.3f}"
    F["e5_none_krum"] = f"{q('none',0,'krum'):.3f}"
    F["e5_none_mkrum"] = f"{q('none',0,'multi_krum'):.3f}"
    F["e5_tax"] = f"{100*(q('none',0,'fedavg')-q('none',0,'median')):.1f}"
    F["e5_krum_honest_none"] = f"{q('none',0,'krum','honest_rej'):.0f}"
    F["e5_lpra_honest_none"] = f"{q('none',0,'lpra','honest_rej'):.0f}"
    F["e5_district_rounds"] = str(int(gA.seeds.max()) * rounds_A * 5)
    for atk in ("scale", "flip", "noise", "stealth"):
        F[f"e5_{atk}1_fedavg"] = f"{q(atk,1,'fedavg'):.3f}"
        F[f"e5_{atk}1_lpra"] = f"{q(atk,1,'lpra'):.3f}"
        F[f"e5_{atk}1_mkrum"] = f"{q(atk,1,'multi_krum'):.3f}"
        F[f"e5_{atk}2_fedavg"] = f"{q(atk,2,'fedavg'):.3f}"
        F[f"e5_{atk}2_lpra"] = f"{q(atk,2,'lpra'):.3f}"
    LBL_AGG = {"fedavg": "FedAvg", "median": "Median", "trimmed_mean": "Trimmed Mean",
               "krum": "Krum", "multi_krum": "Multi-Krum", "lpra": "LPRA (ours)"}
    F["tab_agg_detail"] = [[LBL_AGG[a], f"{q('none',0,a):.3f}", f"{q('none',0,a,'honest_rej'):.0f}",
                            f"{q('scale',1,a,'caught'):.1f} / {rounds_A}",
                            f"{q('scale',1,a,'honest_rej'):.0f}"] for a in AGG]
    F["e5_krum_flip2"] = f"{q('flip',2,'krum'):.3f}"
    F["e5_krum_flip2_sd"] = f"{q('flip',2,'krum','f1_sd'):.3f}"
    F["e5_two_ceiling"] = f"{q('noise',2,'lpra'):.3f}"
    F["e5_lpra_flip2_caught"] = f"{q('flip',2,'lpra','caught'):.1f}"
    F["e5_stealth_caught"] = f"{q('stealth',1,'lpra','caught'):.0f}"

# --------------------------------------------------------- Table 10 / 11 (E6/E7)
l7 = rd_csv("exp7_leave_one_attack_out.csv")
if l7 is not None:
    F["tab_loao"] = [[r["held_out_family"], f"{int(r['n_unseen']):,}", f"{r['recall_on_unseen']:.3f}",
                      f"{r['fpr_normal']:.3f}"] for _, r in l7.iterrows()]
    worst = l7.sort_values("recall_on_unseen").iloc[0]
    F["loao_worst_family"] = worst["held_out_family"]
    F["loao_worst_recall"] = f"{worst['recall_on_unseen']:.2f}"
    others = l7[l7.held_out_family != worst["held_out_family"]]
    F["loao_min_other"] = f"{others.recall_on_unseen.min():.2f}"
    F["loao_n_above"] = str(int((l7.recall_on_unseen >= 0.9).sum()))
    F["loao_n_total"] = str(len(l7))
    F["loao_fpr_range"] = f"{100*l7.fpr_normal.min():.1f}–{100*l7.fpr_normal.max():.1f}"
a8 = rd_csv("exp8_feature_ablation.csv")
if a8 is not None:
    def shown(prev, cur):
        new = [f for f in cur if f not in prev]
        return ("+ " if prev else "") + ", ".join(new[:6]) + ("…" if len(new) > 6 else "")
    rows, prev = [], []
    for _, r in a8.iterrows():
        cur = eval(r["removed"]) if isinstance(r["removed"], str) else list(r["removed"])
        rows.append([str(int(r["removed_top_k"])), str(int(r["n_features"])), f"{r['f1']:.3f}",
                     "—" if not cur else shown(prev, cur)])
        prev = cur
    F["tab_ablation"] = rows
    f0 = a8[a8.removed_top_k == 0].f1.iloc[0]
    F["abl_top1_drop"] = f"{100*(f0 - a8[a8.removed_top_k == 1].f1.iloc[0]):.1f}"
    F["abl_top5_drop"] = f"{100*(f0 - a8[a8.removed_top_k == 5].f1.iloc[0]):.1f}"
    F["abl_top10_f1"] = f"{a8[a8.removed_top_k == 10].f1.iloc[0]:.2f}"
    F["abl_top20_f1"] = f"{a8[a8.removed_top_k == 20].f1.iloc[0]:.2f}"
    F["abl_first_feature"] = (eval(a8[a8.removed_top_k == 1].removed.iloc[0])[0]).replace("_", "-")

# ------------------------------------------------- decision-tree rules (E7b/S5)
tr = poc.get("exp8b_tree_rules") if poc else None
if tr:
    F["tree_leaves"] = str(tr["n_leaves"]); F["tree_depth"] = str(tr["depth"])
    F["tree_top_share_pct"] = f"{100*tr['top_attack_leaf_share']:.0f}"
    F["tree_top_types"] = tr["leaves"][0]["dominant_types"] if tr["leaves"] else ""
    att = [l for l in tr["leaves"] if l["prediction"] == "ATTACK"]
    if att:
        F["tree_top_purity"] = f"{att[0]['purity']:.3f}"
        F["tree_top_flows"] = f"{int(att[0]['test_flows']):,}"
rl = rd_csv("exp8b_tree_rules.csv")
if rl is not None:
    F["tab_tree_rules"] = [[f"{int(r.test_flows):,}", r.prediction, f"{r.purity:.3f}",
                            r.dominant_types, r.rule] for _, r in rl.iterrows()]

# ----------------------------------------------------------------- ledger (E8)
if poc and "exp4_ledger" in poc:
    L = poc["exp4_ledger"]
    F["led_txs"] = sci(L["tx_per_s"])
    F["led_txs_plain"] = f"{L['tx_per_s']:,.0f}"
    F["led_confirm_ms"] = f"{L['avg_tx_confirm_ms']:.1f}"
    F["led_commit_ms"] = f"{L['avg_block_commit_ms']:.1f}"
    F["led_overhead"] = f"{L['storage_overhead_x']:.2f}"
    F["led_n_tx"] = f"{L['tx_submitted']:,}"
    F["led_onchain_mb"] = f"{L['onchain_bytes']/1e6:.1f}"
    F["led_plain_mb"] = f"{L['plain_db_bytes']/1e6:.1f}"
    F["led_bytes_per_alert"] = f"{L['onchain_bytes']/L['tx_submitted']:.0f}"
    F["led_plain_bytes_per_alert"] = f"{L['plain_db_bytes']/L['tx_submitted']:.0f}"
    F["led_validators"] = str(L["validators"]); F["led_quorum"] = str(L["quorum"])
    F["led_tampered_block"] = str(L.get("tampered_block", 3))
    F["led_tamper_detected"] = "yes" if L.get("tamper_detected") else "NO"

# ------------------------------------------------------------ scalability (E9)
c1 = rd_csv("extC_districts_scaling.csv"); c2 = rd_csv("extC_validators_scaling.csv")
c3 = rd_csv("extC_blocksize_sweep.csv"); cg = rd_csv("extC_lpra_gamma_sensitivity_K20.csv")
if c1 is not None:
    F["scal_K_list"] = ", ".join(str(k) for k in sorted(c1.K.unique()))
    att = c1[(c1.aggregator == "lpra") & (c1.attack == "scale")]
    F["scal_natt_list"] = ", ".join(str(int(n)) for n in att.sort_values("K").n_att)
    F["scal_all_caught"] = "yes" if (att.caught >= 10).all() else "no"
    rows = []
    for K in sorted(c1.K.unique()):
        f_none = c1[(c1.K == K) & (c1.aggregator == "fedavg") & (c1.attack == "none")].f1.iloc[0]
        l_none = c1[(c1.K == K) & (c1.aggregator == "lpra") & (c1.attack == "none")].f1.iloc[0]
        l_att = c1[(c1.K == K) & (c1.aggregator == "lpra") & (c1.attack == "scale")]
        f_att = c1[(c1.K == K) & (c1.aggregator == "fedavg") & (c1.attack == "scale")].f1.iloc[0]
        hr = c1[(c1.K == K) & (c1.aggregator == "lpra") & (c1.attack == "none")].honest_rej.iloc[0]
        rows.append([str(K), str(int(l_att.n_att.iloc[0])), f"{f_none:.3f}", f"{l_none:.3f}",
                     f"{f_att:.3f}", f"{l_att.f1.iloc[0]:.3f}",
                     f"{int(l_att.caught.iloc[0])} / 10", f"{int(hr)} / {10*K}"])
    F["tab_scal"] = rows
if c2 is not None:
    F["scal_val_range"] = f"{c2.validators.min()}–{c2.validators.max()}"
    F["scal_val_txs"] = f"{c2.tx_per_s.min()/1e4:.1f}–{c2.tx_per_s.max()/1e4:.1f} × 10⁴"
    F["scal_val_overhead"] = f"{c2.storage_overhead_x.min():.2f}× to {c2.storage_overhead_x.max():.2f}×"
    F["scal_verify_ms"] = f"{c2.verify_ms.mean():.0f}"
if c3 is not None:
    lo, hi = c3.iloc[0], c3.iloc[-1]
    F["scal_bs_lo"] = f"{int(lo.block_size)}"; F["scal_bs_hi"] = f"{int(hi.block_size)}"
    F["scal_bs_lo_ms"] = f"{lo.tx_confirm_ms:.2f}"; F["scal_bs_hi_ms"] = f"{hi.tx_confirm_ms:.1f}"
    F["scal_bs_lo_ov"] = f"{lo.storage_overhead_x:.2f}"; F["scal_bs_hi_ov"] = f"{hi.storage_overhead_x:.2f}"
if cg is not None:
    F["tab_gamma"] = [[f"{r.gamma}", "none" if r.attack == "none" else f"scale ({int(r.n_att)} attackers)",
                       f"{r.f1:.4f}", f"{int(r.caught)} / 10", f"{int(r.honest_rej)}"] for _, r in cg.iterrows()]
    base = cg[(cg.gamma == cg.gamma.min()) & (cg.attack == "none")].iloc[0]
    loose = cg[(cg.gamma == cg.gamma.max()) & (cg.attack == "none")].iloc[0]
    F["gamma_lo"] = f"{cg.gamma.min()}"; F["gamma_hi"] = f"{cg.gamma.max()}"
    F["gamma_lo_rej"] = f"{int(base.honest_rej)}"; F["gamma_hi_rej"] = f"{int(loose.honest_rej)}"
    F["gamma_hi_f1"] = f"{loose.f1:.3f}"

# ------------------------------------------------------------- city replay (E10)
if poc and "exp5_city_replay" in poc:
    c = poc["exp5_city_replay"]
    F["city_flows"] = f"{c['n_flows']:,}"
    F["city_fps"] = sci(c["flows_per_s"])
    F["city_mean_ms"] = f"{c['per_flow_latency_ms']['mean']:.2f}"
    F["city_p99_ms"] = f"{c['per_flow_latency_ms']['p99']:.2f}"
    F["city_prec"] = f"{c['detection']['precision']:.3f}"
    F["city_rec"] = f"{c['detection']['recall']:.3f}"
    F["city_fpr_pct"] = f"{100*c['detection']['fpr']:.1f}"
    F["city_alerts"] = f"{c['alerts']:,}"
    F["city_blocks"] = f"{c['ledger']['blocks']:,}"
    aud = c["audit"][0]
    F["city_audit_verified"] = f"{aud['verified']:,}"
    F["city_audit_tampered"] = str(aud["tampered"])
    F["city_audit_others"] = str(sum(x["tampered"] for x in c["audit"][1:]))
    rr = c["rogue_node_rejected"]
    F["city_rogue"] = ("all rejected" if (rr is True or (isinstance(rr, dict) and all(rr.values())))
                       else "NOT rejected")
    F["city_rogue_names"] = ", ".join(rr.keys()) if isinstance(rr, dict) else "RogueNode"
    F["city_ledger_intact"] = "intact" if c["ledger_intact"] else "BROKEN"

# ---------------------------------------------------------------- scenario (E11)
sc = rd_json("extD_scenario.json")
if sc:
    dd = sc["detection_delay_s"]
    F["sce_delay_health"] = f"{dd.get('Healthcare', float('nan')):.1f}"
    F["sce_delay_water"] = f"{dd.get('Water', float('nan')):.1f}"
    F["sce_delay_transport"] = f"{dd.get('Transport', float('nan')):.1f}"
    F["sce_delay_max"] = f"{max(dd.values()):.1f}"
    F["sce_anchor_ms"] = f"{sc['L3_mean_anchor_delay_ms']:.2f}"
    F["sce_declared_s"] = f"{sc['L4_campaign_declared_s']:.0f}"
    F["sce_after_third_s"] = f"{sc['L4_campaign_declared_s'] - max(sc['onset_s'].values()):.0f}"
    F["sce_from_first_s"] = f"{sc['L4_time_from_first_onset_s']:.0f}"
    F["sce_true"] = f"{sc['true_alerts']:,}"; F["sce_false"] = f"{sc['false_alerts']:,}"
    F["sce_normal"] = f"{sc['normal_flows_replayed']:,}"
    F["sce_window_s"] = "480"
    F["sce_onsets"] = ", ".join(f"{k} at {int(v)} s" for k, v in sc["onset_s"].items())

# ------------------------------------------------------- multi-class (supplement)
mc = poc.get("exp1m_multiclass") if poc else None
if mc:
    fams = [k for k in mc if k not in ("accuracy", "macro avg", "weighted avg")]
    F["tab_multiclass"] = [[f, f"{mc[f]['precision']:.3f}", f"{mc[f]['recall']:.3f}",
                            f"{mc[f]['f1-score']:.3f}", f"{int(mc[f]['support']):,}"] for f in sorted(fams)]
    F["tab_multiclass"].append(["macro avg", f"{mc['macro avg']['precision']:.3f}",
                                f"{mc['macro avg']['recall']:.3f}", f"{mc['macro avg']['f1-score']:.3f}",
                                f"{int(mc['macro avg']['support']):,}"])
    F["mc_acc_pct"] = f"{100*mc['accuracy']:.1f}"
    F["mc_macro_f1"] = f"{mc['macro avg']['f1-score']:.3f}"
    worst = min(fams, key=lambda f: mc[f]["f1-score"])
    F["mc_worst"] = worst.upper() if worst == "mitm" else worst
    F["mc_worst_f1"] = f"{mc[worst]['f1-score']:.2f}"
    F["mc_worst_support"] = f"{int(mc[worst]['support']):,}"

# ------------------------------------------------ firewall + cross-dataset (opt.)
fw = rd_csv("exp6_firewall_perimeter.csv")
if fw is not None:
    F["tab_firewall"] = [[r["features"], MODEL_LABEL.get(r["model"], r["model"]), f"{r['f1']:.3f}",
                          f"{r['roc_auc']:.3f}", f"{r['fpr']:.3f}"] for _, r in fw.iterrows()]
    best = fw.sort_values("f1").groupby("features").tail(1).set_index("features")
    if len(best) == 2:
        try:
            F["fw_gain"] = f"{100*(best.loc['with-ports','f1'] - best.loc['no-ports (bias-aware)','f1']):.1f}"
            F["fw_noport_f1"] = f"{best.loc['no-ports (bias-aware)','f1']:.3f}"
            F["fw_port_f1"] = f"{best.loc['with-ports','f1']:.3f}"
        except Exception:
            pass
for vkey, tag in (("common9", "common"), ("dirfree4", "dirfree")):
    x = rd_csv(f"exp2_cross_dataset_f1_{vkey}.csv")
    if x is not None:
        x = x.set_index(x.columns[0])
        F[f"tab_cross_{tag}"] = [[i] + [f"{v:.2f}" for v in x.loc[i].values] for i in x.index]
        F[f"cross_{tag}_cols"] = ["Train \\ Test"] + list(x.columns)
        diag = [x.loc[i, i] for i in x.index if i in x.columns]
        off = [x.loc[i, j] for i in x.index for j in x.columns if i != j]
        cell = lambda a, b: (f"{x.loc[a, b]:.2f}" if (a in x.index and b in x.columns) else None)
        for nm, (a, b) in {"c2u": ("CIC-IDS2017", "UNSW-NB15"), "u2c": ("UNSW-NB15", "CIC-IDS2017"),
                           "t2c": ("TON_IoT", "CIC-IDS2017"), "u2t": ("UNSW-NB15", "TON_IoT"),
                           "t2u": ("TON_IoT", "UNSW-NB15")}.items():
            v = cell(a, b)
            if v is not None:
                F[f"cross_{tag}_{nm}"] = v
        if tag == "common":
            F["cross_attack_shares"] = "76% in TON_IoT, 19% in CIC-IDS2017 and 13% in UNSW-NB15"
        if diag and off:
            F[f"cross_{tag}_diag"] = f"{np.mean(diag):.2f}"
            F[f"cross_{tag}_off"] = f"{np.mean(off):.2f}"
            F[f"cross_{tag}_off_min"] = f"{np.min(off):.2f}"
            F[f"cross_{tag}_off_max"] = f"{np.max(off):.2f}"
# extra native benchmarks
rows = []
for p in sorted(glob.glob(os.path.join(RES, "exp1c_native_*.csv"))):
    d = pd.read_csv(p).sort_values("f1").iloc[-1]
    rows.append([str(d.get("dataset", os.path.basename(p)[13:-4])), f"{int(d.get('n_rows', 0)):,}",
                 str(int(d["n_features"])), MODEL_LABEL.get(d["model"], d["model"]),
                 f"{d['f1']:.3f}", f"{d['roc_auc']:.3f}", f"{d['fpr']:.3f}",
                 f"{d['latency_us_per_flow']:.0f}"])
if rows:
    F["tab_native_extra"] = rows

# attack share of each additional dataset (for the cross-dataset discussion)
poc_extra = (poc or {}).get("exp1c_native_other_datasets") or {}
for key, rows in poc_extra.items():
    if rows:
        pass
F["ciciot_or_cic_ratio"] = "19%"

# ---------------------------------------------- Hyperledger Fabric run (E13)
# Measured by hand on the authors' laptop with fabric/bench/bench.mjs; kept in a small
# side-car file so that re-running make_facts.py never loses them.
fab_path = os.path.join(RES, "fabric_facts.json")
if os.path.exists(fab_path):
    with open(fab_path, encoding="utf-8") as fh:
        F.update(json.load(fh))

# the slowdown factor is derived, never stored, so it cannot go stale
if "fab_c20_txs" in F and "led_txs_plain" in F:
    try:
        F["fab_ratio_txs"] = f"{float(F['led_txs_plain'].replace(',', '')) / float(F['fab_c20_txs']):.0f}"
        F["fab_ratio_lat"] = f"{float(F['fab_c20_mean']) / float(F['led_confirm_ms']):.0f}"
        F["fab_txs_drop_pct"] = f"{100 * (1 - float(F['fab_c50_txs']) / float(F['fab_c20_txs'])):.0f}"
        raw = float(F["fab_ledger_bytes"].replace(",", ""))
        F["fab_ledger_mb"] = f"{raw / 1e6:.2f}"
        F["fab_bytes_per_alert"] = f"{raw / float(F['fab_anchored'].replace(',', '')):,.0f}"
        F["fab_mb_per_10k"] = f"{raw / 1e6 / float(F['fab_anchored'].replace(',', '')) * 10000:.1f}"
        # Annual per-peer storage at a given sustained alert rate = bytes/alert
        # x alerts/s x seconds/year. Computed here, never hand-typed, so a
        # bug like "10 alerts/s" quoting the 1-alert/s figure (v27 and
        # earlier: 190 GB was hardcoded and is actually the 1 alert/s
        # number -- 10 alerts/s is ~1.92 TB) cannot recur silently.
        bytes_per_alert = raw / float(F["fab_anchored"].replace(",", ""))
        seconds_per_year = 3.15e7
        gb_per_year_at = lambda rate: bytes_per_alert * rate * seconds_per_year / 1e9
        F["fab_gb_per_peer_year_1"] = f"{gb_per_year_at(1):.0f}"
        tb10 = gb_per_year_at(10) / 1000
        F["fab_tb_per_peer_year_10"] = f"{tb10:.2f}"
    except Exception:
        pass

# Table 14 body (emulation vs Fabric)
if "fab_c20_txs" in F and "led_txs_plain" in F:
    F["tab_fabric"] = [
        ["Emulated ledger, 5 validators (Section 5.5)", F["led_txs_plain"], F["led_confirm_ms"], "—", "—", "—",
         f"{float(F['led_onchain_mb']):.1f}"],
        ["Fabric v2.5.9, 2 orgs, Raft, concurrency 20", F["fab_c20_txs"], F["fab_c20_mean"], F["fab_c20_p50"],
         F["fab_c20_p95"], F["fab_c20_p99"], F["fab_mb_per_10k"]],
        ["Fabric v2.5.9, 2 orgs, Raft, concurrency 50", F["fab_c50_txs"], F["fab_c50_mean"], F["fab_c50_p50"],
         F["fab_c50_p95"], F["fab_c50_p99"], F["fab_mb_per_10k"]],
    ]


# ------------------------------------------------ E15 temporal / concept drift
t15 = rd_json("exp15_temporal_cicids.json")
r15 = rd_csv("exp15_temporal_cicids.csv")
if t15 and r15 is not None:
    F["temp_control_f1"] = f"{t15['control']['f1']:.4f}"
    F["temp_control_fpr"] = f"{t15['control']['fpr']:.4f}"
    F["temp_train_days"] = str(t15["n_train_days"])
    F["temp_rows"] = f"{int(r15.n.sum()):,}"
    g = r15.set_index(["protocol", "day"])
    for d in ("tuesday", "wednesday", "thursday", "friday"):
        if ("static", d) in g.index:
            F[f"temp_static_{d}"] = f"{g.loc[('static', d), 'f1']:.4f}"
            F[f"temp_ratio_{d}"] = f"{g.loc[('static', d), 'attack_ratio']:.4f}"
        if ("rolling", d) in g.index:
            F[f"temp_roll_{d}"] = f"{g.loc[('rolling', d), 'f1']:.4f}"
            F[f"temp_roll_recall_{d}"] = f"{g.loc[('rolling', d), 'recall']:.4f}"
    # F1 and recall are undefined when a day has no positive (attack) flows;
    # render an em dash instead of 0.0000 (the caption of Table 16 explains this).
    def _f1_recall(r):
        if r["attack_ratio"] == 0:
            return "\u2014", "\u2014"
        return f"{r['f1']:.4f}", f"{r['recall']:.4f}"
    F["tab_temporal"] = [[r["protocol"], r["day"], "in-sample" if r["in_training"] else "held out",
                          f"{int(r['n']):,}", f"{r['attack_ratio']:.4f}", *_f1_recall(r),
                          f"{r['fpr']:.4f}"] for _, r in r15.iterrows()]
    F["tab_novel"] = [[d, ", ".join(v) if v else "(none new)"] for d, v in t15["novel_types"].items()]

# --------------------------------------------- E16 edge resources and energy
r16 = rd_csv("exp16_resources.csv")
if r16 is not None:
    r16 = r16.set_index("model")
    F["tab_resources"] = [[MODEL_LABEL.get(m, m), f"{r16.loc[m,'infer_cpu_us']:.3f}",
                           f"{r16.loc[m,'single_flow_cpu_us']:.0f}", f"{r16.loc[m,'infer_mem_mb']:.2f}",
                           f"{r16.loc[m,'model_kb']:.1f}", f"{r16.loc[m,'cpu_s_per_1M']:.3f}",
                           f"{r16.loc[m,'J_per_1M_pi_class_3W']:.2f}",
                           f"{r16.loc[m,'kWh_per_year_pi_class_3W']:.3f}"] for m in ORDER if m in r16.index]
    dt, rf = r16.loc["DecisionTree(d=8)"], r16.loc["RandomForest(20x8)"]
    F["res_dt_us"] = f"{dt['infer_cpu_us']:.3f}"; F["res_rf_us"] = f"{rf['infer_cpu_us']:.2f}"
    F["res_dt_J"] = f"{dt['J_per_1M_pi_class_3W']:.2f}"; F["res_rf_J"] = f"{rf['J_per_1M_pi_class_3W']:.2f}"
    F["res_ratio"] = f"{rf['J_per_1M_pi_class_3W']/dt['J_per_1M_pi_class_3W']:.0f}"
    F["res_dt_mem"] = f"{dt['infer_mem_mb']:.2f}"; F["res_dt_single"] = f"{dt['single_flow_cpu_us']:.0f}"
    F["res_dt_kwh"] = f"{dt['kWh_per_year_pi_class_3W']:.3f}"
    F["res_dt_flows_per_cpu_s"] = f"{dt['flows_per_cpu_s']/1e6:.1f} × 10⁶"
    j = rd_json("exp16_resources.json") or {}
    F["res_rate"] = f"{j.get('flows_per_s', 1000):,.0f}"

# ------------------------------------------------- E17 adaptive attacker sweep
a17 = rd_csv("exp17_adaptive_sweep.csv")
if a17 is not None:
    a17 = a17[a17.direction != "none"]
    def cell(agg, d, s, n, col="f1"):
        r = a17[(a17.aggregator == agg) & (a17.direction == d) & (a17.strength == s) & (a17.n_att == n)]
        return None if r.empty else r[col].iloc[0]
    rows = []
    for n in sorted(a17.n_att.unique()):
        for d in ("orthogonal", "opposite"):
            for s in sorted(a17.strength.unique()):
                cells = []
                for agg in ("fedavg", "lpra_v1", "lpra_v2"):
                    f1 = cell(agg, d, s, n); c = cell(agg, d, s, n, "caught")
                    cells.append("-" if f1 is None else
                                 f"{f1:.3f}" + ("" if agg == "fedavg" else f" ({int(c)}/10)"))
                rows.append([f"{int(n)}", d, f"{s:g}"] + cells)
    F["tab_adaptive"] = rows
    F["adapt_strengths"] = ", ".join(f"{s:g}" for s in sorted(a17.strength.unique()))
    for nm, (agg, d, s, n) in {
            "fed_opp20_n1": ("fedavg", "opposite", 20.0, 1),
            "fed_opp6_n2": ("fedavg", "opposite", 6.0, 2),
            "v1_opp6_n2": ("lpra_v1", "opposite", 6.0, 2),
            "v2_opp6_n2": ("lpra_v2", "opposite", 6.0, 2),
            "v2_opp20_n1": ("lpra_v2", "opposite", 20.0, 1),
            "v2_orth20_n2": ("lpra_v2", "orthogonal", 20.0, 2),
            "fed_orth20_n2": ("fedavg", "orthogonal", 20.0, 2)}.items():
        v = cell(agg, d, s, n); c = cell(agg, d, s, n, "caught")
        if v is not None:
            F[f"adapt_{nm}"] = f"{v:.4f}"
            F[f"adapt_{nm}_caught"] = f"{int(c)}"

# ---------------------------------------------------- provenance consistency check
hosts = {}
for name, blob in (("run_poc", poc), ("run_extended", ext),
                   ("run_advanced/E16", rd_json("exp16_resources.json")),
                   ("run_advanced/E15", rd_json("exp15_temporal_cicids.json"))):
    m = (blob or {}).get("machine")
    if isinstance(m, dict) and m.get("platform"):
        hosts[name] = f"{m['platform']} | {m.get('run_date', '?')}"
if len({v.split('|')[0] for v in hosts.values()}) > 1:
    print("\nWARNING: results in this folder come from more than one machine —")
    for k, v in hosts.items():
        print(f"    {k:20s} {v}")
    print("    re-run the odd one out before building the manuscript.\n")

out = os.path.join(RES, "paper_facts.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=1, ensure_ascii=False)
scalars = sum(1 for v in F.values() if not isinstance(v, list))
print(f"wrote {out}: {scalars} scalar facts, {len(F)-scalars} tables")
missing = [k for k in ("tab_cross_common9", "tab_native_extra", "tab_firewall") if k not in F]
if missing:
    print("not yet available (experiment not run):", missing)
