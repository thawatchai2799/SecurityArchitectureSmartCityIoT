"""
lifecycle.py
------------
From measured CPU-seconds, bytes and transactions to energy, carbon and storage per
gateway-year and per city-year -- with every assumption named, in one place, and swept.

The replay (chrono.py) measures a capture week: 40 windows, 24 of them after the initial
training. This module scales what one *test window* cost to a year of operation and converts
it with the ASSUMPTIONS table below. Nothing in it is a wattmeter reading; the structure is the
one E15 of the previous article (Chomsiri & Phunsa 2026) used (measured CPU time x stated board power), extended to
training, model traffic and anchoring, and every entry of ASSUMPTIONS can be replaced by a
measurement without changing anything else (that is the plan for the Raspberry-Pi validation).

ASSUMPTIONS (defaults; each swept in sensitivity())
    windows_per_year     8 windows/day x 365 days  = 2920. A window of the capture holds
                         sample_per_day/8 flows (~20,000); the year is assumed to repeat the
                         capture week's traffic and attack mix (a scenario, not a forecast).
    P_x86_W              12 W   sustained package power of the x86 host while one core works
                                (E15 of the article; the CPU-seconds were measured on x86)
    P_edge_W             3 W    Raspberry-Pi-class gateway, one core busy (E15 of the article)
    edge_slowdown        5x     CPU time of the same single-threaded sklearn computation on a
                                Pi-4-class ARM core relative to this x86 core (to be replaced by
                                the Pi measurement; swept 2x-10x)
    kWh_per_GB_network   0.06   electricity intensity of fixed-line data transmission
                                (Aslan et al. 2018, J. Ind. Ecol., 2015 value; swept 0.01-0.3,
                                the upper end being a mobile-access figure)
    bytes_per_tx         6,076  measured on the Fabric test network of the article
                                (fabric/fabric_facts.json: 24,311,978 B / 4,001 anchored tx)
    kgCO2e_per_kWh       0.4371 Thailand grid, TGO announcement of 28 May 2025 (value for 2022);
                                swept 0.1-0.8 to cover other grids
    gateway_idle_W       2.7    idle draw of a Raspberry-Pi-4-class gateway, the baseline that the
                                detection upkeep is compared against (24 h x 365 d)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

ASSUMPTIONS = dict(
    windows_per_year=8 * 365,
    P_x86_W=12.0,
    P_edge_W=3.0,
    edge_slowdown=5.0,
    kWh_per_GB_network=0.06,
    bytes_per_tx=6076,
    kgCO2e_per_kWh=0.4371,
    gateway_idle_W=2.7,       # Raspberry Pi 4 idle draw, for the baseline the upkeep is compared against
)

SWEEPS = dict(                      # low, default, high -- for the sensitivity table
    edge_slowdown=(2.0, 5.0, 10.0),
    P_edge_W=(2.0, 3.0, 6.0),
    kWh_per_GB_network=(0.01, 0.06, 0.30),
    kgCO2e_per_kWh=(0.10, 0.4371, 0.80),
)

PROTO_LABEL = dict(tree_local="Edge tree (full history)", tree_cap="Edge tree (1-day history)",
                   mlp_local="Edge MLP (continual)", fedavg="FedAvg", lpra="LPRA", central="Centralised")
POLICY_LABEL = dict(static="never", every_1="every window", every_2="every 2", every_4="every 4",
                    every_8="daily", trigger="alert-rate trigger", drift="drift trigger", oracle="F1 < 0.5 (reference)",
                    adwin="ADWIN", kswin="KSWIN", ddm="DDM", drift_fb="drift + daily fallback")


def annualise(row: pd.Series, A: dict = ASSUMPTIONS, k: int = 5) -> dict:
    """One replay summary row -> per-gateway-year and per-city-year figures."""
    nt = row["n_test_windows"]
    scale = A["windows_per_year"] / nt                       # test windows -> one year
    # ---- compute: training (retraining) and inference, per gateway ------------------------ #
    # the replay's CPU-seconds are the whole city's (all K districts, serially); per gateway / K.
    # For the federated protocols the aggregation step is tiny next to the local epochs and is
    # charged to the gateways too (conservative for the gateway, generous to the cloud).
    train_cpu_gw = row["retrain_cpu_s"] * scale / k           # x86 CPU-s per gateway-year
    infer_cpu_gw = row["infer_cpu_s"] * scale / k
    _tg = row.get("trigger_cpu_s", 0.0)                       # ADWIN / KSWIN / DDM only; absent (NaN) in older replay files
    trigger_cpu_gw = (0.0 if _tg is None or _tg != _tg else float(_tg)) * scale / k
    if row["protocol"] == "central":                          # training happens in the cloud, not on the gateway
        train_kwh_edge = 0.0
        train_kwh_cloud = train_cpu_gw * k * A["P_x86_W"] / 3.6e6
    else:
        train_kwh_edge = train_cpu_gw * A["edge_slowdown"] * A["P_edge_W"] / 3.6e6
        train_kwh_cloud = 0.0
    infer_kwh_edge = infer_cpu_gw * A["edge_slowdown"] * A["P_edge_W"] / 3.6e6
    trigger_kwh_edge = trigger_cpu_gw * A["edge_slowdown"] * A["P_edge_W"] / 3.6e6   # the detector runs on the gateway
    # ---- traffic across the district boundary --------------------------------------------- #
    gb_model = (row["bytes_up"] + row["bytes_down"]) * scale / k / 1e9     # per gateway-year
    gb_raw = row["raw_bytes"] * scale / k / 1e9
    gb_ledger = row["tx"] * A["bytes_per_tx"] * scale / 1e9                 # per city-year (shared ledger)
    net_kwh = (gb_model + gb_raw) * A["kWh_per_GB_network"] + gb_ledger / k * A["kWh_per_GB_network"]
    tx_year = row["tx"] * scale
    retrains_year = row["n_retrain"] * scale
    kwh_gw = train_kwh_edge + infer_kwh_edge + trigger_kwh_edge + net_kwh + train_kwh_cloud / k
    kwh_idle = A["gateway_idle_W"] * 24 * 365 / 1000
    out = dict(protocol=row["protocol"], policy=row["policy"], seed=row["seed"],
               mean_f1=row["mean_f1"], stream_f1=row["stream_f1"], stream_recall=row["stream_recall"],
               stream_fpr=row["stream_fpr"], missed_attacks=row["missed_attacks"],
               retrains_per_year=retrains_year, train_cpu_h_per_gw_year=train_cpu_gw / 3600,
               trigger_cpu_h_per_gw_year=trigger_cpu_gw / 3600, kwh_trigger_edge=trigger_kwh_edge,
               train_gflop_per_gw_year=row["retrain_gflop"] * scale / k,
               kwh_train_edge=train_kwh_edge, kwh_train_cloud=train_kwh_cloud, kwh_infer_edge=infer_kwh_edge,
               gb_model_per_gw_year=gb_model, gb_raw_per_gw_year=gb_raw, gb_ledger_per_city_year=gb_ledger,
               kwh_network=net_kwh, tx_per_year=tx_year,
               kwh_per_gw_year=kwh_gw, kwh_per_city_year=kwh_gw * k,
               kwh_gateway_idle_year=kwh_idle, upkeep_share_of_idle=kwh_gw / kwh_idle,
               kgco2e_per_gw_year=kwh_gw * A["kgCO2e_per_kWh"],
               kgco2e_per_city_year=kwh_gw * k * A["kgCO2e_per_kWh"])
    return out


def lifecycle_table(summary: pd.DataFrame, A: dict = ASSUMPTIONS, k: int = 5) -> pd.DataFrame:
    rows = [annualise(r, A, k) for _, r in summary.iterrows()]
    return pd.DataFrame(rows)


def aggregate_seeds(lt: pd.DataFrame) -> pd.DataFrame:
    """Mean and 95 % CI (t, n-1 dof) over seeds for every numeric column."""
    from scipy import stats
    g = lt.groupby(["protocol", "policy"])
    num = [c for c in lt.columns if c not in ("protocol", "policy", "seed")]
    mean = g[num].mean()
    n = g.size()
    sd = g[num].std(ddof=1).fillna(0)
    t = pd.Series({pp: (stats.t.ppf(0.975, max(nn - 1, 1)) if nn > 1 else 0.0) for pp, nn in n.items()})
    ci = sd.mul(t, axis=0).div(np.sqrt(n), axis=0)
    out = mean.copy()
    for c in num:
        out[c + "_ci"] = ci[c]
    out["n_seeds"] = n
    return out.reset_index()


COMBINED = dict(                   # every assumption at its most favourable / default / least favourable value at once
    best=dict(windows_per_year=8 * 365, P_edge_W=2.0, edge_slowdown=2.0, kWh_per_GB_network=0.01, kgCO2e_per_kWh=0.10),
    default=dict(),
    worst=dict(windows_per_year=24 * 365, P_edge_W=6.0, edge_slowdown=10.0, kWh_per_GB_network=0.30, kgCO2e_per_kWh=0.80),
)


def combined_scenarios(summary: pd.DataFrame, k: int = 5, policies=("every_1", "drift")) -> pd.DataFrame:
    """Best / default / worst case with every assumption moved at once (the one-at-a-time sweep is
    sensitivity()); the worst case also runs the gateway 24 windows a day instead of 8, i.e. it
    assumes the capture's hourly traffic around the clock. Mean over seeds."""
    rows = []
    for name, over in COMBINED.items():
        A = dict(ASSUMPTIONS); A.update(over)
        lt = lifecycle_table(summary, A, k)
        lt = lt[lt.policy.isin(policies)].groupby(["protocol", "policy"]).mean(numeric_only=True).reset_index()
        for _, r in lt.iterrows():
            rows.append(dict(scenario=name, protocol=r.protocol, policy=r.policy, windows_per_year=A["windows_per_year"],
                             kwh_per_gw_year=r.kwh_per_gw_year, kgco2e_per_gw_year=r.kgco2e_per_gw_year,
                             share_of_idle_pct=100 * r.upkeep_share_of_idle))
    return pd.DataFrame(rows)


def scale_city(agg: pd.DataFrame, ks=(5, 10, 20, 50, 100)) -> pd.DataFrame:
    """Per-city-year energy and ledger growth as a function of the number of districts.
    Gateway-side costs are linear in K by construction; the ledger grows with tx, which for the
    federated protocols is (K+1) per round -- so its share rises with K."""
    rows = []
    for _, r in agg.iterrows():
        for K in ks:
            per_gw = r["kwh_per_gw_year"]
            tx = r["tx_per_year"]
            if r["protocol"] in ("fedavg", "lpra"):
                tx = tx * (K + 1) / (5 + 1)            # (K+1) tx per round instead of 6
            elif r["protocol"] in ("tree_local", "tree_cap", "mlp_local"):
                tx = tx * K / 5                         # one anchor per district per retrain
            rows.append(dict(protocol=r["protocol"], policy=r["policy"], K=K,
                             kwh_city_year=per_gw * K, kgco2e_city_year=r["kgco2e_per_gw_year"] * K,
                             tx_year=tx, ledger_gb_year=tx * ASSUMPTIONS["bytes_per_tx"] / 1e9,
                             mean_f1=r["mean_f1"]))
    return pd.DataFrame(rows)


def sensitivity(summary: pd.DataFrame, k: int = 5, protocols=("tree_cap", "fedavg", "central"),
                policy="every_1") -> pd.DataFrame:
    """One-at-a-time sweep of every assumption; reports kWh and kgCO2e per gateway-year and
    whether the ranking of the protocols changes."""
    rows = []
    base = lifecycle_table(summary, ASSUMPTIONS, k)
    base = base[(base.policy == policy) & base.protocol.isin(protocols)].groupby("protocol").mean(numeric_only=True)
    protocols = tuple(p for p in protocols if p in base.index)
    if not protocols:
        return pd.DataFrame(columns=["assumption", "level", "value", "protocol", "policy", "kwh_per_gw_year",
                                     "kgco2e_per_gw_year", "ranking", "ranking_unchanged"])
    base_rank = tuple(base.sort_values("kwh_per_gw_year").index)
    for name, (lo, mid, hi) in SWEEPS.items():
        for lvl, val in (("low", lo), ("default", mid), ("high", hi)):
            A = dict(ASSUMPTIONS); A[name] = val
            lt = lifecycle_table(summary, A, k)
            lt = lt[(lt.policy == policy) & lt.protocol.isin(protocols)].groupby("protocol").mean(numeric_only=True)
            rank = tuple(lt.sort_values("kwh_per_gw_year").index)
            for p in protocols:
                rows.append(dict(assumption=name, level=lvl, value=val, protocol=p, policy=policy,
                                 kwh_per_gw_year=lt.loc[p, "kwh_per_gw_year"],
                                 kgco2e_per_gw_year=lt.loc[p, "kgco2e_per_gw_year"],
                                 ranking=" < ".join(rank), ranking_unchanged=(rank == base_rank)))
    return pd.DataFrame(rows)
