#!/usr/bin/env python3
"""
make_sustain_facts.py -- every number and table of the manuscript, formatted,
in results_sustain/paper_facts_sustain.json. make_sustain_paper.js renders from this file only.
"""
import os, sys, json, glob
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sustain.lifecycle import ASSUMPTIONS, SWEEPS, PROTO_LABEL, POLICY_LABEL
RES = os.environ.get("SUSTAIN_RESULTS") or os.path.join(ROOT, "results_sustain")
T = os.path.join(RES, "tables")

agg = pd.read_csv(os.path.join(T, "T_grid_full.csv"))
facts_raw = json.load(open(os.path.join(RES, "sustain_facts.json")))
sc = pd.read_csv(os.path.join(T, "T_scaling.csv"))
an = pd.read_csv(os.path.join(T, "T_anchoring.csv"))
se = pd.read_csv(os.path.join(T, "T_sensitivity.csv"))
wt = pd.read_csv(os.path.join(T, "T_windows.csv"))
summary = pd.read_csv(os.path.join(RES, "summary.csv"))
F = {}
PROTOS = ["tree_local", "tree_cap", "mlp_local", "fedavg", "lpra", "central"]
POLS = ["static", "every_8", "every_4", "every_2", "every_1", "trigger", "drift", "oracle", "adwin", "kswin", "ddm", "drift_fb"]


def g(p, pol, c):
    r = agg[(agg.protocol == p) & (agg.policy == pol)]
    return float(r[c].iloc[0]) if len(r) else float("nan")


def pm(p, pol, c, nd=3):
    return f"{g(p, pol, c):.{nd}f} ± {g(p, pol, c + '_ci'):.{nd}f}"


def f3(x, nd=3):
    return f"{x:.{nd}f}"


def fi(x):
    """int for display; empty string when the value is missing (partial grids)."""
    try:
        return int(x)
    except (TypeError, ValueError):
        return ""


F["n_seeds"] = facts_raw["n_seeds"]; F["seeds"] = "42–46"
F["n_runs"] = int(len(summary)); F["n_windows"] = int(wt.window.max()) + 1
F["w_init"] = int(summary.w_init.iloc[0]); F["n_test"] = F["n_windows"] - F["w_init"]
F["flows_per_window"] = f"{int(wt.flows.iloc[0]):,}"
F["flows_total"] = f"{int(wt.flows.sum()):,}"
# feature count: stored in the replay summary by newer code; older replay files predate the field,
# in which case it is recovered from the raw-export cost (77 x 4 B + 1 B per flow, Table 2)
_rp = glob.glob(os.path.join(RES, "replay_*_s*.json"))
_nf = max([int(json.load(open(x))["summary"].get("n_feats") or 0) for x in _rp] or [0])
F["n_feats"] = _nf if _nf else 77

# ---- detection headline numbers ------------------------------------------------------------
for p in PROTOS:
    for pol in POLS:
        F[f"sf1_{p}_{pol}"] = pm(p, pol, "stream_f1")
        F[f"sf1v_{p}_{pol}"] = f3(g(p, pol, "stream_f1"))
        F[f"mf1_{p}_{pol}"] = pm(p, pol, "mean_f1")
        F[f"fpr_{p}_{pol}"] = f3(g(p, pol, "stream_fpr"), 4)
        F[f"kwh_{p}_{pol}"] = f3(g(p, pol, "kwh_per_gw_year"), 4)
        F[f"co2_{p}_{pol}"] = f3(g(p, pol, "kgco2e_per_gw_year"), 4)
        F[f"tx_{p}_{pol}"] = f"{g(p, pol, 'tx_per_year'):,.0f}"
        F[f"rt_{p}_{pol}"] = f"{g(p, pol, 'retrains_per_year'):,.0f}"
        F[f"cpuh_{p}_{pol}"] = f3(g(p, pol, "train_cpu_h_per_gw_year"), 3)
        F[f"share_{p}_{pol}"] = f"{100 * g(p, pol, 'upkeep_share_of_idle'):.2f}"
edge_fed = ["tree_cap", "mlp_local", "fedavg"]
F["sf1_static_max"] = f3(max(g(p, "static", "stream_f1") for p in PROTOS))
F["sf1_daily_min"] = f3(min(g(p, "every_8", "stream_f1") for p in PROTOS))
F["sf1_daily_max"] = f3(max(g(p, "every_8", "stream_f1") for p in PROTOS))
F["sf1_every2_min"] = f3(min(g(p, "every_2", "stream_f1") for p in PROTOS))
F["sf1_every2_max"] = f3(max(g(p, "every_2", "stream_f1") for p in PROTOS))
F["sf1_every1_edge_min"] = f3(min(g(p, "every_1", "stream_f1") for p in ["tree_cap", "mlp_local", "fedavg"]))
F["sf1_every1_edge_max"] = f3(max(g(p, "every_1", "stream_f1") for p in ["tree_cap", "mlp_local", "fedavg"]))
# drift trigger savings (tree_cap)
# re-training events of the drift trigger per replay (same windows in every seed for the 2017 stream)
_dr = summary[(summary.protocol == "tree_cap") & (summary.policy == "drift")].n_retrain
F["drift_events"] = int(round(_dr.mean())) if len(_dr) else 0
F["drift_events_range"] = (f"{int(_dr.min())}" if _dr.min() == _dr.max() else f"{int(_dr.min())}–{int(_dr.max())}") if len(_dr) else ""
F["drift_share_pct"] = f"{100 * g('tree_cap', 'drift', 'retrains_per_year') / g('tree_cap', 'every_1', 'retrains_per_year'):.1f}"
F["drift_cpu_saving_pct"] = f"{100 * (1 - g('tree_cap', 'drift', 'train_cpu_h_per_gw_year') / g('tree_cap', 'every_1', 'train_cpu_h_per_gw_year')):.0f}"
F["drift_tx_saving_pct"] = f"{100 * (1 - g('fedavg', 'drift', 'tx_per_year') / g('fedavg', 'every_1', 'tx_per_year')):.1f}"
# costs
F["kwh_max_edgefed"] = f3(max(g(p, pol, "kwh_per_gw_year") for p in PROTOS if p != "central" for pol in POLS), 4)
F["kwh_min_nonzero"] = f3(min(g(p, "every_1", "kwh_per_gw_year") for p in PROTOS), 4)
F["kwh_idle"] = f3(ASSUMPTIONS["gateway_idle_W"] * 24 * 365 / 1000, 1)
F["share_max_pct"] = f"{100 * max(g(p, pol, 'upkeep_share_of_idle') for p in PROTOS for pol in POLS):.2f}"
F["central_vs_tree_x"] = f"{g('central', 'every_1', 'kwh_per_gw_year') / g('tree_cap', 'every_1', 'kwh_per_gw_year'):.1f}"
F["gb_model_fedavg"] = f3(g("fedavg", "every_1", "gb_model_per_gw_year"), 3)
F["gb_raw_central"] = f3(g("central", "every_1", "gb_raw_per_gw_year"), 2)
F["gb_raw_central_drift"] = f3(g("central", "drift", "gb_raw_per_gw_year"), 2)
F["mb_ledger_fedavg"] = f"{g('fedavg', 'every_1', 'tx_per_year') * ASSUMPTIONS['bytes_per_tx'] / 1e6:.0f}"
F["mb_ledger_tree"] = f"{g('tree_cap', 'every_1', 'tx_per_year') * ASSUMPTIONS['bytes_per_tx'] / 1e6:.0f}"
fit = facts_raw.get("tree_full_history_fit", dict(intercept_s=float("nan"), slope_s_per_flow=float("nan"), n_events=0))
F["tree_slope_us"] = f"{fit['slope_s_per_flow'] * 1e6:.1f}"; F["tree_fit_n"] = fit["n_events"]
_age = facts_raw.get("tree_full_history_age_aware_cpu_h_per_gw_year", float("nan"))
F["tree_age_cpu_h"] = f"{_age:,.0f}"
F["tree_cap_cpu_h"] = f3(facts_raw.get("tree_cap_cpu_h_per_gw_year", float("nan")), 2)
# steady-state bound of the capped tree: the fitted line evaluated at a full cap in every district
# (K x 160,000 flows of city history), x 2,920 refits per year, per gateway
_cap_s = fit["intercept_s"] + fit["slope_s_per_flow"] * 5 * 160000
F["tree_cap_event_s"] = f"{_cap_s:.1f}"
F["tree_cap_steady_cpu_h"] = f3(_cap_s / 5 * 2920 / 3600, 2)
F["tree_age_pi_h"] = f"{_age * ASSUMPTIONS['edge_slowdown']:,.0f}"
F["history_flows_year"] = f"{ASSUMPTIONS['windows_per_year'] * int(wt.flows.iloc[0]) / 1e6:.0f}"
# memory of the uncapped history after a year: flows x features x 4 bytes (float32), city and per district
_hist_flows = ASSUMPTIONS['windows_per_year'] * int(wt.flows.iloc[0]) + int(fit.get("initial_flows", 0))
F["history_gb_city"] = f"{_hist_flows * F['n_feats'] * 4 / 1e9:.0f}"
F["history_gb_district"] = f"{_hist_flows * F['n_feats'] * 4 / 1e9 / 5:.1f}"
# scaling
def s(p, K, c):
    r = sc[(sc.protocol == p) & (sc.policy == "every_1") & (sc.K == K)][c]
    return float(r.iloc[0]) if len(r) else float("nan")
F["co2_city100_tree"] = f3(s("tree_cap", 100, "kgco2e_city_year"), 2)
F["co2_city100_central"] = f3(s("central", 100, "kgco2e_city_year"), 1)
F["co2_city100_idle"] = f"{ASSUMPTIONS['gateway_idle_W'] * 24 * 365 / 1000 * ASSUMPTIONS['kgCO2e_per_kWh'] * 100:,.0f}"
_idle100 = ASSUMPTIONS['gateway_idle_W'] * 24 * 365 / 1000 * ASSUMPTIONS['kgCO2e_per_kWh'] * 100
F["idle_vs_tree_x"] = f"{round(_idle100 / s('tree_cap', 100, 'kgco2e_city_year') / 10) * 10:,.0f}"
F["tx_fedavg_k100"] = f"{s('fedavg', 100, 'tx_year') / 1e6:.2f}"
F["gb_fedavg_k100"] = f3(s("fedavg", 100, "ledger_gb_year"), 1)
# anchoring
def a(p, pol, mode, c):
    r = an[(an.protocol == p) & (an.policy == pol) & (an.anchoring == mode)][c]
    return r.iloc[0] if len(r) else float("nan")
F["anch_round_mb"] = f"{a('fedavg', 'every_1', 'per-round', 'ledger_gb_per_year') * 1000:.0f}"
F["anch_event_mb"] = f"{a('fedavg', 'every_1', 'per-event', 'ledger_gb_per_year') * 1000:.0f}"
F["anch_round_red"] = f"{100 * a('fedavg', 'every_1', 'per-round', 'ledger_reduction'):.0f}"
F["anch_event_red"] = f"{100 * a('fedavg', 'every_1', 'per-event', 'ledger_reduction'):.0f}"
F["proof_bytes_round"] = fi(a("fedavg", "every_1", "per-round", "proof_bytes"))
F["proof_bytes_event"] = fi(a("fedavg", "every_1", "per-event", "proof_bytes"))
F["merkle_us_round"] = f"{a('fedavg', 'every_1', 'per-round', 'merkle_cpu_us_per_batch'):.0f}"
F["merkle_us_event"] = f"{a('fedavg', 'every_1', 'per-event', 'merkle_cpu_us_per_batch'):.0f}"
F["verify_us_round"] = f"{a('fedavg', 'every_1', 'per-round', 'verify_cpu_us'):.1f}"
F["verify_us_event"] = f"{a('fedavg', 'every_1', 'per-event', 'verify_cpu_us'):.1f}"
# sensitivity -- assumptions are named in prose, as in the assumptions table
ASSUMPTION_LABEL = dict(edge_slowdown="edge slowdown (x)", P_edge_W="edge power (W)",
                        kWh_per_GB_network="network intensity (kWh/GB)", kgCO2e_per_kWh="grid factor (kg CO2e/kWh)")
F["sens_unchanged"] = bool(se.ranking_unchanged.all())
F["sens_flips"] = "; ".join(sorted({f"{ASSUMPTION_LABEL.get(r.assumption, r.assumption)} = {r.value:g}" for _, r in se[~se.ranking_unchanged].iterrows()}))
_t, _f = g('tree_cap', 'every_1', 'kwh_per_gw_year'), g('fedavg', 'every_1', 'kwh_per_gw_year')
F["tree_vs_fed_ratio"] = f"{_t / _f:.1f}" if _f else ""
_lo = se[(se.assumption == "kWh_per_GB_network") & (se.level == "low") & (se.protocol == "central")].kwh_per_gw_year
_hi = se[(se.assumption == "kWh_per_GB_network") & (se.level == "high") & (se.protocol == "central")].kwh_per_gw_year
lo = _lo.iloc[0] if len(_lo) else float("nan"); hi = _hi.iloc[0] if len(_hi) else float("nan")
F["sens_central_lo"] = f3(lo, 3); F["sens_central_hi"] = f3(hi, 3)
_tl = se[(se.assumption == "kWh_per_GB_network") & (se.level == "low") & (se.protocol == "tree_cap")].kwh_per_gw_year
F["sens_central_lo4"] = f3(lo, 4); F["sens_tree_lo4"] = f3(_tl.iloc[0] if len(_tl) else float("nan"), 4)
F["tree_vs_fed_kwh"] = f"{g('tree_cap','every_1','kwh_per_gw_year'):.4f} vs {g('fedavg','every_1','kwh_per_gw_year'):.4f}"
# assumptions
for k, v in ASSUMPTIONS.items():
    F[f"A_{k}"] = v
F["A_windows_per_year"] = f"{ASSUMPTIONS['windows_per_year']:,}"
F["param_bytes"] = f"{int(summary.param_bytes.iloc[0]):,}"

# ---- tables -------------------------------------------------------------------------------
# Table 1: windows per day
FAMILY_LABEL = {"ftp - patator": "FTP-Patator", "ssh - patator": "SSH-Patator", "dos hulk": "DoS Hulk",
                "dos slowhttptest": "DoS Slowhttptest", "dos slowloris": "DoS slowloris", "dos goldeneye": "DoS GoldenEye",
                "heartbleed": "Heartbleed", "web attack - brute force": "Web Attack Brute Force",
                "web attack - sql injection": "Web Attack SQL Injection", "web attack - xss": "Web Attack XSS",
                "infiltration": "Infiltration", "bot": "Bot", "portscan": "PortScan", "ddos": "DDoS",
                "ssh - bruteforce": "SSH-Bruteforce", "ftp - bruteforce": "FTP-BruteForce",
                "dos attacks - goldeneye": "DoS GoldenEye", "dos attacks - slowloris": "DoS Slowloris",
                "dos attacks - hulk": "DoS Hulk", "dos attacks - slowhttptest": "DoS SlowHTTPTest",
                "ddos attacks - loic - http": "DDoS LOIC-HTTP", "ddos attack - hoic": "DDoS HOIC",
                "ddos attack - loic - udp": "DDoS LOIC-UDP", "brute force - xss": "Brute Force XSS",
                "sql injection": "SQL Injection", "brute force - web": "Brute Force Web", "infilteration": "Infiltration"}
def fam(x):
    return FAMILY_LABEL.get(x.lower(), x)
from decimal import Decimal, ROUND_HALF_UP
def _r3(v):
    return str(Decimal(repr(float(v))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
rows = []
for d in list(dict.fromkeys(wt.day)):
    w = wt[wt.day == d]
    fams = sorted({f.strip() for x in w.families.fillna("") for f in str(x).split(",") if f.strip()})
    new = [f.strip() for x in w.first_seen.fillna("") for f in str(x).split(",") if f.strip()]
    _dl = str(d)
    if _dl[:4].isdigit():                                   # 2018 stream: ISO date -> "Wed 14 Feb"
        import datetime as _dt
        _dd = _dt.date.fromisoformat(_dl); _dl = _dd.strftime("%a %d %b").replace(" 0", " ")
    rows.append([_dl.capitalize() if not _dl[0].isupper() else _dl, f"{int(w.window.min())}–{int(w.window.max())}", f"{int(w.flows.sum()):,}",
                 f"{_r3(w.attack_share.min())}–{_r3(w.attack_share.max())}", ", ".join(fam(x) for x in new) if new else "(none new)"])
F["tab_windows"] = rows
# Table 4: stream F1 grid
F["tab_grid"] = [[PROTO_LABEL[p]] + [pm(p, pol, "stream_f1") for pol in ["static", "every_8", "every_4", "every_2", "every_1", "drift", "oracle"]] for p in PROTOS]
F["tab_grid_mean"] = [[PROTO_LABEL[p]] + [pm(p, pol, "mean_f1") for pol in ["static", "every_8", "every_4", "every_2", "every_1", "drift", "oracle"]] for p in PROTOS]
# Worked example of Equation (1): FedAvg, re-training every window, mean over seeds
_fe = summary[(summary.protocol == "fedavg") & (summary.policy == "every_1")]
if len(_fe):
    _s = ASSUMPTIONS["windows_per_year"] / float(_fe.n_test_windows.iloc[0]); _K = 5
    _tau_tr = float(_fe.retrain_cpu_s.mean()); _tau_inf = float(_fe.infer_cpu_s.mean())
    _b_mod = float((_fe.bytes_up + _fe.bytes_down).mean()); _b_led = float(_fe.tx.mean()) * ASSUMPTIONS["bytes_per_tx"]
    _e_comp = _s / _K * ASSUMPTIONS["edge_slowdown"] * ASSUMPTIONS["P_edge_W"] * (_tau_tr + _tau_inf) / 3.6e6
    _e_net = _s / _K * ASSUMPTIONS["kWh_per_GB_network"] * (_b_mod + _b_led) / 1e9
    F["wx_s"] = f"{_s:.2f}"; F["wx_tau_tr"] = f"{_tau_tr:,.1f}"; F["wx_tau_inf"] = f"{_tau_inf:,.1f}"
    F["wx_b_mod_mb"] = f"{_b_mod / 1e6:,.1f}"; F["wx_tx"] = f"{float(_fe.tx.mean()):,.0f}"; F["wx_b_led_mb"] = f"{_b_led / 1e6:,.1f}"
    F["wx_e_comp"] = f"{_e_comp:.4f}"; F["wx_e_net"] = f"{_e_net:.4f}"; F["wx_e_total"] = f"{_e_comp + _e_net:.4f}"
    F["wx_co2"] = f"{(_e_comp + _e_net) * ASSUMPTIONS['kgCO2e_per_kWh']:.4f}"
# ledger peer electricity, an upper bound for the limitations section: tx per year at the measured
# Fabric throughput of the previous article (146 tx/s), with the whole network drawing 100 W meanwhile
_tx_fed = g("fedavg", "every_1", "tx_per_year")
F["ledger_peer_s"] = f"{_tx_fed / 146:,.0f}"; F["ledger_peer_kwh"] = f"{_tx_fed / 146 * 100 / 3.6e6:.3f}"
F["dfpr_tree"] = f3(g("tree_cap", "drift", "stream_fpr") - g("tree_cap", "every_1", "stream_fpr"), 3)
F["dfpr_mlp"] = f3(g("mlp_local", "drift", "stream_fpr") - g("mlp_local", "every_1", "stream_fpr"), 2)
# LPRA screen activity: quarantined client updates out of all client updates (rounds x K)
_lp = summary[(summary.protocol == "lpra") & (summary.policy == "every_1")]
F["quar_lpra_every_1"] = f"{_lp.quarantined.mean():,.0f}" if len(_lp) else ""
F["updates_lpra_every_1"] = f"{(_lp.fl_rounds * 5).mean():,.0f}" if len(_lp) else ""
F["sf1v_tree_cap_static"] = f3(g("tree_cap", "static", "stream_f1")); F["sf1v_fedavg_static"] = f3(g("fedavg", "static", "stream_f1"))
F["sf1v_fedavg_every_8"] = f3(g("fedavg", "every_8", "stream_f1")); F["sf1v_mlp_local_every_1"] = f3(g("mlp_local", "every_1", "stream_f1"))
F["sf1v_tree_cap_kswin"] = f3(g("tree_cap", "kswin", "stream_f1")); F["sf1v_central_kswin"] = f3(g("central", "kswin", "stream_f1"))
F["sf1v_tree_cap_adwin"] = f3(g("tree_cap", "adwin", "stream_f1")); F["sf1v_mlp_local_adwin"] = f3(g("mlp_local", "adwin", "stream_f1"))
F["sf1v_mlp_local_ddm"] = f3(g("mlp_local", "ddm", "stream_f1")); F["sf1v_tree_cap_ddm"] = f3(g("tree_cap", "ddm", "stream_f1"))
F["rt_tree_cap_kswin_n"] = f"{g('tree_cap', 'kswin', 'retrains_per_year') / 2920 * F['n_test']:.0f}" if F.get("n_test") else ""
F["rt_tree_cap_adwin_n"] = f"{g('tree_cap', 'adwin', 'retrains_per_year') / 2920 * F['n_test']:.0f}" if F.get("n_test") else ""
F["rt_tree_cap_ddm_n"] = f"{g('tree_cap', 'ddm', 'retrains_per_year') / 2920 * F['n_test']:.0f}" if F.get("n_test") else ""
F["sf1v_mlp_local_drift"] = f3(g("mlp_local", "drift", "stream_f1")); F["sf1v_central_drift"] = f3(g("central", "drift", "stream_f1"))
# Combined best / default / worst scenarios (every assumption at once; worst also 24 windows a day)
_csp = os.path.join(T, "T_scenarios.csv")
if os.path.exists(_csp):
    cs = pd.read_csv(_csp)
    F["tab_scen"] = []
    for p in PROTOS:
        if p == "tree_local":
            continue
        row = [PROTO_LABEL[p]]
        for sc in ("best", "default", "worst"):
            d = cs[(cs.scenario == sc) & (cs.protocol == p) & (cs.policy == "every_1")]
            row += [f3(d.kwh_per_gw_year.iloc[0], 4), f"{d.share_of_idle_pct.iloc[0]:.2f}"] if len(d) else ["", ""]
        F["tab_scen"].append(row)
    def _cs(sc, p, c):
        d = cs[(cs.scenario == sc) & (cs.protocol == p) & (cs.policy == "every_1")]
        return float(d[c].iloc[0]) if len(d) else float("nan")
    F["scen_worst_central_kwh"] = f3(_cs("worst", "central", "kwh_per_gw_year"), 2)
    F["scen_worst_central_share"] = f"{_cs('worst', 'central', 'share_of_idle_pct'):.1f}"
    F["scen_worst_tree_kwh"] = f3(_cs("worst", "tree_cap", "kwh_per_gw_year"), 3)
    F["scen_worst_tree_share"] = f"{_cs('worst', 'tree_cap', 'share_of_idle_pct'):.1f}"
    F["scen_worst_ratio"] = f"{_cs('worst', 'central', 'kwh_per_gw_year') / _cs('worst', 'tree_cap', 'kwh_per_gw_year'):.1f}"
    F["scen_worst_fed_kwh"] = f3(_cs("worst", "fedavg", "kwh_per_gw_year"), 3)
    F["scen_best_central_kwh"] = f3(_cs("best", "central", "kwh_per_gw_year"), 4)
    F["scen_best_tree_kwh"] = f3(_cs("best", "tree_cap", "kwh_per_gw_year"), 4)
    F["scen_best_fed_kwh"] = f3(_cs("best", "fedavg", "kwh_per_gw_year"), 4)
    F["scen_worst_central_co2"] = f3(_cs("worst", "central", "kgco2e_per_gw_year"), 2)
    F["scen_worst_max_share"] = f"{cs[(cs.scenario == 'worst') & (cs.policy == 'every_1')].share_of_idle_pct.max():.1f}"
    F["scen_worst_central_share_idle24"] = f"{_cs('worst', 'central', 'share_of_idle_pct') * 2.7 / 2.4:.1f}"
    F["scen_worst_tree_co2"] = f3(_cs("worst", "tree_cap", "kgco2e_per_gw_year"), 3)
    F["scen_best_central_co2"] = f3(_cs("best", "central", "kgco2e_per_gw_year"), 4)
# raw counts behind the worked example (city totals over the held-out windows, then per gateway-year)
if len(_fe):
    F["wx_tr_city_year_s"] = f"{_tau_tr * _s:,.0f}"; F["wx_tr_gw_year_s"] = f"{_tau_tr * _s / _K:,.0f}"
    F["wx_tr_gw_year_h"] = f"{_tau_tr * _s / _K / 3600:.3f}"
    F["wx_edge_s"] = f"{(_tau_tr + _tau_inf) * _s / _K * ASSUMPTIONS['edge_slowdown']:,.0f}"
    F["wx_bytes_city_year_gb"] = f"{(_b_mod + _b_led) * _s / 1e9:.3f}"; F["wx_b_mod_year_gb"] = f"{_b_mod * _s / 1e9:.3f}"; F["wx_b_led_year_gb"] = f"{_b_led * _s / 1e9:.3f}"; F["wx_b_led_gw_year_gb"] = f"{_b_led * _s / _K / 1e9:.3f}"; F["wx_bytes_gw_year_gb"] = f"{(_b_mod + _b_led) * _s / _K / 1e9:.3f}"
    F["wx_e_city"] = f"{(_e_comp + _e_net) * _K:.4f}"
# labelling volume: every policy that keeps re-training eventually trains on every flow of the stream
F["labels_per_year_m"] = f"{ASSUMPTIONS['windows_per_year'] * int(wt.flows.iloc[0]) / 1e6:.1f}"
F["labels_per_gw_day_k"] = f"{8 * int(wt.flows.iloc[0]) / 5 / 1e3:.0f}"
# Paired differences per seed (same seed = same sampling, partition and initialisation), stream F1
from scipy import stats as _st
def _paired(p, a, b, col="stream_f1"):
    A = summary[(summary.protocol == p) & (summary.policy == a)].set_index("seed")[col]
    B = summary[(summary.protocol == p) & (summary.policy == b)].set_index("seed")[col]
    common = sorted(set(A.index) & set(B.index))
    if len(common) < 2:
        return None
    d = (A.loc[common] - B.loc[common]).values
    m = float(d.mean()); sd = float(d.std(ddof=1)); n = len(d)
    h = float(_st.t.ppf(0.975, n - 1) * sd / n ** 0.5) if n > 1 else 0.0
    pval = float(_st.ttest_rel(A.loc[common].values, B.loc[common].values).pvalue) if sd > 0 else 1.0
    return m, h, pval, n
F["tab_paired"] = []
for _p in ("tree_cap", "mlp_local", "fedavg", "central"):
    for _a in ("drift", "drift_fb", "kswin"):
        r = _paired(_p, _a, "every_1")
        if r is None:
            continue
        m, h, pval, n = r
        F["tab_paired"].append([PROTO_LABEL[_p], POLICY_LABEL[_a] + " − every window", f"{m:+.3f}".replace("-", "\u2212"), f"[{m - h:+.3f}, {m + h:+.3f}]".replace("-", "\u2212"), f"{pval:.3f}" if pval >= 0.001 else "< 0.001"])
        key = f"pd_{_p}_{_a}"
        _mn = lambda v: f"{v:+.3f}".replace("-", "\u2212")
        F[key] = _mn(m); F[key + "_ci"] = f"[{_mn(m - h)}, {_mn(m + h)}]"; F[key + "_p"] = f"{pval:.3f}" if pval >= 0.001 else "< 0.001"
F["has_fallback"] = bool((agg.policy == "drift_fb").any())
for _p in PROTOS:
    F[f"sf1v_{_p}_drift_fb"] = f3(g(_p, "drift_fb", "stream_f1"))
    F[f"rt_{_p}_drift_fb"] = f"{g(_p, 'drift_fb', 'retrains_per_year'):,.0f}" if F["has_fallback"] else ""
    F[f"kwh_{_p}_drift_fb"] = f3(g(_p, "drift_fb", "kwh_per_gw_year"), 4)
    F[f"cpuh_{_p}_drift_fb"] = f3(g(_p, "drift_fb", "train_cpu_h_per_gw_year"), 3)
# Non-annualised costs: Wh per re-training event per gateway, and per million flows the gateway sees
_flows_gw_test = int(wt.flows.iloc[0]) * F["n_test"] / 5
F["tab_unit"] = []
for _p in ("tree_cap", "mlp_local", "fedavg", "lpra", "central"):
    k_ = g(_p, "every_1", "kwh_per_gw_year"); rt_ = g(_p, "every_1", "retrains_per_year")
    per_event_wh = 1000 * k_ / rt_ if rt_ else float("nan")
    per_mflow_wh = 1000 * k_ / (ASSUMPTIONS["windows_per_year"] * int(wt.flows.iloc[0]) / 5 / 1e6)
    F["tab_unit"].append([PROTO_LABEL[_p], f"{per_event_wh:.4f}", f"{per_mflow_wh:.2f}"])
    F[f"wh_event_{_p}"] = f"{per_event_wh:.4f}"; F[f"wh_mflow_{_p}"] = f"{per_mflow_wh:.2f}"
    # traffic-volume scaling at the defaults: the cost per flow is held constant, so the upkeep is
    # proportional to the flows the gateway sees; break-even = the daily flow count at which the
    # upkeep equals the gateway's idle electricity (2.7 W x 8,760 h)
    _idle_wh = ASSUMPTIONS["gateway_idle_W"] * 24 * 365
    F[f"be_mflow_day_{_p}"] = f"{_idle_wh / per_mflow_wh / 365:.1f}"
    F[f"share_1m_day_{_p}"] = f"{100 * per_mflow_wh * 365 / _idle_wh:.1f}"
F["flows_gw_day_k"] = f"{8 * int(wt.flows.iloc[0]) / 5 / 1e3:.0f}"
# Trigger comparison: our drift trigger against the standard detectors (only when they were run)
DETECTORS = ["drift", "adwin", "kswin", "ddm", "oracle"]
F["has_detectors"] = bool(all((agg.policy == pol).any() for pol in ("adwin", "kswin", "ddm")))
F["tab_triggers"] = []
if F["has_detectors"]:
    for p in ("tree_cap", "mlp_local", "fedavg", "central"):     # LPRA and the full-history tree are in Table S5
        for pol in DETECTORS:
            if not ((agg.protocol == p) & (agg.policy == pol)).any():
                continue
            F["tab_triggers"].append([PROTO_LABEL[p], POLICY_LABEL[pol], pm(p, pol, "stream_f1"),
                                      f3(g(p, pol, "stream_fpr"), 4), f"{g(p, pol, 'retrains_per_year'):,.0f}",
                                      f3(g(p, pol, "train_cpu_h_per_gw_year"), 3),
                                      f3(g(p, pol, "trigger_cpu_h_per_gw_year"), 4)])
    for pol in ("adwin", "kswin", "ddm"):
        F[f"rt_tree_cap_{pol}"] = f"{g('tree_cap', pol, 'retrains_per_year'):,.0f}"
        F[f"sf1v_tree_cap_{pol}"] = f3(g("tree_cap", pol, "stream_f1"))
        F[f"trig_cpuh_{pol}"] = f3(g("tree_cap", pol, "trigger_cpu_h_per_gw_year"), 4)
        F[f"trig_cpuh_max_{pol}"] = f3(max(g(_pp, pol, "trigger_cpu_h_per_gw_year") for _pp in PROTOS), 4)
F["tab_fpr"] = [[PROTO_LABEL[p]] + [f3(g(p, pol, "stream_fpr"), 4) for pol in ["every_8", "every_4", "every_2", "every_1", "drift", "oracle"]] for p in PROTOS]
# Table 5: cost, every window
F["tab_cost"] = [[PROTO_LABEL[p], F[f"rt_{p}_every_1"], F[f"cpuh_{p}_every_1"], f3(g(p, "every_1", "gb_model_per_gw_year"), 3),
                  f3(g(p, "every_1", "gb_raw_per_gw_year"), 2), F[f"tx_{p}_every_1"], F[f"kwh_{p}_every_1"], F[f"co2_{p}_every_1"], F[f"share_{p}_every_1"]] for p in PROTOS]
F["tab_cost_drift"] = [[PROTO_LABEL[p], F[f"rt_{p}_drift"], F[f"cpuh_{p}_drift"], f3(g(p, "drift", "gb_model_per_gw_year"), 3),
                  f3(g(p, "drift", "gb_raw_per_gw_year"), 2), F[f"tx_{p}_drift"], F[f"kwh_{p}_drift"], F[f"co2_{p}_drift"], F[f"share_{p}_drift"]] for p in PROTOS]
# Tables 8/9 split: measured quantities vs the edge-class energy/carbon scenario
F["tab_cost_measured"] = []
F["tab_cost_scenario"] = []
for pol in ("every_1", "drift"):
    for pr in PROTOS:
        F["tab_cost_measured"].append([PROTO_LABEL[pr], POLICY_LABEL[pol], F[f"rt_{pr}_{pol}"], F[f"cpuh_{pr}_{pol}"],
                                       f3(g(pr, pol, "gb_model_per_gw_year"), 3), f3(g(pr, pol, "gb_raw_per_gw_year"), 2), F[f"tx_{pr}_{pol}"]])
        F["tab_cost_scenario"].append([PROTO_LABEL[pr], POLICY_LABEL[pol], f3(g(pr, pol, "kwh_train_edge") + g(pr, pol, "kwh_train_cloud") / 5, 4),
                                       f3(g(pr, pol, "kwh_infer_edge"), 5), f3(g(pr, pol, "kwh_network"), 4),
                                       F[f"kwh_{pr}_{pol}"], F[f"co2_{pr}_{pol}"], F[f"share_{pr}_{pol}"]])
# Table 6: assumptions
F["tab_assump"] = [
    ["Windows per year", F["A_windows_per_year"], "8 per day × 365; the year repeats the capture", "—"],
    ["x86 host power while one core works (W)", "12", "energy estimate of [1]", "—"],
    ["Edge gateway power while one core works (W)", "3", "energy estimate of [1]; Pi 4 measured 2.4–2.9 W idle, 6.7–7.3 W four-core load [11]", "2–6"],
    ["Edge slowdown vs. this x86 core (×)", "5", "assumed; bracketed by the 2–10× sweep", "2–10"],
    ["Network electricity intensity (kWh/GB)", "0.06", "Aslan et al. 2018, fixed line, 2015 [9]", "0.01–0.30"],
    ["Ledger bytes per anchored record (B)", "6,076", "Fabric measurement of [1]", "—"],
    ["Grid emission factor (kg CO2e/kWh)", "0.4371", "Thailand Greenhouse Gas Management Organization (TGO), announced 28 May 2025 (value for 2022) [12]", "0.10–0.80"],
    ["Gateway idle draw (W)", "2.7", "literature range 2.4–2.9 W [11]", "—"],
]
# Table 7: anchoring (fedavg every_1 and drift)
F["tab_anchor"] = []
for pol in ["every_1", "drift"]:
    for mode in ["per-record", "per-round", "per-event"]:
        rr = an[(an.protocol == "fedavg") & (an.policy == pol) & (an.anchoring == mode)]
        if rr.empty:
            continue
        r = rr.iloc[0]
        F["tab_anchor"].append([POLICY_LABEL[pol], mode, fi(r.batch), f"{r.tx_per_year:,.0f}", f"{r.ledger_gb_per_year * 1000:.0f}",
                                f"{100 * r.ledger_reduction:.0f}", fi(r.proof_bytes), f"{r.merkle_cpu_us_per_batch:.1f}", f"{r.verify_cpu_us:.1f}"])
# Table 8: sensitivity (kWh per gateway-year, every window, three protocols)
F["tab_sens"] = []
for nm in SWEEPS:
    row = [ASSUMPTION_LABEL.get(nm, nm)]
    for lvl in ["low", "default", "high"]:
        d = se[(se.assumption == nm) & (se.level == lvl)]
        row.append(f"{d.value.iloc[0]:g}" if len(d) else "")
        for p in ["tree_cap", "fedavg", "central"]:
            dd = d[d.protocol == p].kwh_per_gw_year
            row.append(f3(dd.iloc[0], 4) if len(dd) else "")
    F["tab_sens"].append(row)
with open(os.path.join(RES, "paper_facts_sustain.json"), "w") as f:
    json.dump(F, f, indent=1, default=float)
print("wrote", len(F), "facts")
