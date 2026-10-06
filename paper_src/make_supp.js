const path = require("path");
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, ImageRun } = require("docx");
const ROOT = path.resolve(__dirname, "..");
const RES = path.join(ROOT, "results") + path.sep;
const FACTS = fs.existsSync(RES + "paper_facts.json")
  ? JSON.parse(fs.readFileSync(RES + "paper_facts.json", "utf8")) : {};
const missing = new Set();
function fact(k) { if (FACTS[k] === undefined || FACTS[k] === null) { missing.add(k); return null; } return FACTS[k]; }
function P(strings, ...keys) {
  const out = [];
  strings.forEach((s2, i) => { if (s2) out.push(t(s2));
    if (i < keys.length) { const v = fact(keys[i]); out.push(v === null ? TBD(`[${keys[i]}]`) : t(String(v))); } });
  return out;
}
function factTable(headers, key, widths, fs2 = 17) {
  const rows = fact(key);
  if (!rows) return table(headers, [[TBD(`[${key}: run the experiment, then paper_src/make_facts.py]`)]
    .concat(Array(headers.length - 1).fill(""))], widths, fs2);
  return table(headers, rows, widths, fs2);
}
const F = "Times New Roman";
const t = (x, o = {}) => new TextRun({ text: x, font: F, size: 20, ...o });
const TBD = (s) => new TextRun({ text: s, font: F, size: 20, bold: true, color: "C00000", highlight: "yellow" });
const p = (x, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 276 }, children: Array.isArray(x) ? x : [t(x)], ...o });
const h1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: s, font: F, size: 22, bold: true, color: "000000" })] });
const cap = (s) => new Paragraph({ spacing: { before: 80, after: 160 }, children: [t(s, { size: 18 })] });
function table(headers, rows, widths, fs = 17) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (txt, w, bold, shade) => new TableCell({ width: { size: w, type: WidthType.DXA }, shading: shade ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined, margins: { top: 40, bottom: 40, left: 60, right: 60 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [typeof txt === "object" && txt !== null ? txt : new TextRun({ text: String(txt), font: F, size: fs, bold })] })] });
  const mk = (cells, bold, shade) => new TableRow({ children: cells.map((c, i) => cell(c, widths[i], bold, shade)) });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, borders: { top: { style: BorderStyle.SINGLE, size: 6 }, bottom: { style: BorderStyle.SINGLE, size: 6 }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "999999" }, insideVertical: { style: BorderStyle.NONE } }, rows: [mk(headers, true, true), ...rows.map(r => mk(r, false, false))] });
}


// ---- revision (v2.0): supplementary items regenerated from review_response/*.json
const RR = path.join(ROOT, "review_response") + path.sep;
const RJ = (n) => fs.existsSync(RR + n) ? JSON.parse(fs.readFileSync(RR + n, "utf8")) : null;
const f3 = (x) => (Math.round(x * 1000) / 1000).toFixed(3);
function rrTable(headers, file, mapper, widths, fs2 = 17) {
  const d = RJ(file);
  if (!d) return table(headers, [[TBD(`[${file}: run review_response/ scripts]`)].concat(Array(headers.length - 1).fill(""))], widths, fs2);
  return table(headers, mapper(d), widths, fs2);
}


// ---- row builders for Tables S11-S15 (v2.2.0); each returns a placeholder row when its JSON is absent
const f4 = (x) => (Math.round(x * 10000) / 10000).toFixed(4);
const missingRow = (file, n) => [[TBD(`[${file}: run review_response/ scripts]`)].concat(Array(n - 1).fill(""))];
function s11rows() {
  const fl = RJ("table13_flame_k20_50_summary.json"), fl001 = RJ("table13_flame_k20_50_summary_lam0.001.json");
  if (!fl || !fl001) return missingRow("table13_flame_k20_50_summary*.json", 8);
  const aggName = { fedavg: "FedAvg", flame: "FLAME (λ = 0.01)", lpra: "LPRA v2" };
  const row = (r, name) => [r.K, name, r.attack === "none" ? "none" : "scale", r.n_att, `${f4(r.f1)} ± ${f4(r.f1_sd)}`,
    `${r.honest_rej} of ${(r.K - r.n_att) * 10}`,
    r.aggregator === "fedavg" ? "—" : (r.n_att ? `${r.att_rej_sum} of ${r.n_att * 30}` : "—"),
    r.aggregator === "fedavg" ? "—" : (r.n_att ? `${r.caught_mean.toFixed(0)} of 10` : "—")];
  const out = [];
  for (const K of [20, 50]) {
    for (const r of fl.filter(r => r.K === K)) out.push(row(r, aggName[r.aggregator]));
    for (const r of fl001.filter(r => r.K === K && r.aggregator === "flame")) out.push(row(r, "FLAME (λ = 0.001)"));
  }
  return out;
}
function s12rows() {
  const pl = RJ("table13_attacker_placement_summary.json"); if (!pl) return missingRow("table13_attacker_placement_summary.json", 9);
  const out = [];
  for (const K of [5, 10, 20, 50]) {
    const fa = pl.find(r => r.K === K && r.agg === "fedavg"), lp = pl.find(r => r.K === K && r.agg === "lpra");
    lp.placements.forEach((q, i) => {
      const fq = fa.placements[i];
      out.push([K, K === 5 ? (i === 0 ? "fixed (district 0)" : `district ${i}`) : (i === 0 ? "fixed" : `random ${i}`), q.attackers.join(", "), q.families.join(", "), f4(fq.f1),
        `${f4(q.f1)} ± ${f4(q.f1_sd_seeds)}`, `${q.att_mean.toFixed(0)} of ${lp.attacker_rounds}`,
        `${q.hon_min}–${q.hon_max} of ${lp.honest_district_rounds}`, `${q.caught_mean.toFixed(0)} of 10`]);
    });
    out.push([K, "over placements", "", "", `${f4(fa.f1_mean)} ± ${f4(fa.f1_sd)} [${f4(fa.f1_min)}, ${f4(fa.f1_max)}]`,
      `${f4(lp.f1_mean)} ± ${f4(lp.f1_sd)} [${f4(lp.f1_min)}, ${f4(lp.f1_max)}]`, `${lp.att_rej_mean} of ${lp.attacker_rounds}`,
      `${lp.hon_rej_min}–${lp.hon_rej_max} of ${lp.honest_district_rounds}`, `${lp.caught_mean} of 10`]);
  }
  return out;
}
function s13rows() {
  const fk = RJ("fk_boundary_sweep_summary.json"); if (!fk) return missingRow("fk_boundary_sweep_summary.json", 10);
  const out = [];
  for (const K of [9, 11]) for (const f of [2, 3, 4, 5, 6]) for (const attack of ["scale", "flip", "noise", "adaptive"]) {
    const fa = fk.find(r => r.K === K && r.f === f && r.attack === attack && r.agg === "fedavg");
    const v2 = fk.find(r => r.K === K && r.f === f && r.attack === attack && r.agg === "lpra_v2");
    const v1 = fk.find(r => r.K === K && r.f === f && r.attack === attack && r.agg === "lpra_v1");
    out.push([K, f, (f / K).toFixed(2), attack, `${f4(fa.f1_mean)} ± ${f4(fa.f1_sd)}`, `${f4(v2.f1_mean)} ± ${f4(v2.f1_sd)}`,
      v2.att_rej.replace('-', '–'), v2.hon_rej.replace('-', '–'), v2.caught.replace('-', '–'), v1 ? `${f4(v1.f1_mean)} ± ${f4(v1.f1_sd)}; hon ${v1.hon_rej}` : "—"]);
  }
  return out;
}
const COMP = path.join(ROOT, "fabric", "blockfile_composition.json");
const compNames = [["endorser_cert", "Endorser identities (X.509 certificate + MSP id), two per transaction"], ["payload_header", "Payload header: channel header + signature header (client certificate, nonce)"],
  ["action_header", "Action header: signature header again (client certificate, nonce)"], ["rwset", "Read/write set (_lifecycle reads + cityanchor read/write of the alert key)"],
  ["response_events_ccid", "Chaincode response (repeats the stored alert) + chaincode id; no events"], ["proposal_payload", "Proposal payload: the AnchorAlert arguments"],
  ["endorser_signature", "Endorser signatures (two)"], ["envelope_signature", "Client signature over the envelope"], ["block_metadata", "Block metadata (orderer signature, validity flags), share per transaction"],
  ["proposal_hash", "Proposal hash"], ["block_header", "Block header hashes, share per transaction"]];
function s14rows() {
  if (!fs.existsSync(COMP)) return missingRow("fabric/blockfile_composition.json", 3);
  const comp = JSON.parse(fs.readFileSync(COMP, "utf8"));
  const rows = compNames.map(([k, name]) => [name, comp.per_tx_bytes[k].toFixed(0), comp.share[k].toFixed(1)]);
  rows.push(["Protobuf framing, length prefixes, configuration transactions (share)", (comp.file_bytes_per_tx - compNames.reduce((a, [k]) => a + comp.per_tx_bytes[k], 0)).toFixed(0), (100 - compNames.reduce((a, [k]) => a + comp.share[k], 0)).toFixed(1)]);
  rows.push(["Block file per transaction", comp.file_bytes_per_tx.toFixed(0), "100.0"]);
  return rows;
}
function s14b() {
  if (!fs.existsSync(COMP)) return missingRow("fabric/blockfile_composition.json", 3);
  const du = JSON.parse(fs.readFileSync(COMP, "utf8")).ledgersData_du_bytes_2026_10_05;
  const rest = du.total - du.chains_blockfile - du.chains_index - du.stateLeveldb - du.historyLeveldb;
  return [["Block file (chains/chains/mychannel/blockfile_000000)", du.chains_blockfile.toLocaleString(), (100 * du.chains_blockfile / du.total).toFixed(1)],
    ["Block index (chains/index)", du.chains_index.toLocaleString(), (100 * du.chains_index / du.total).toFixed(1)],
    ["State database (stateLeveldb)", du.stateLeveldb.toLocaleString(), (100 * du.stateLeveldb / du.total).toFixed(1)],
    ["History database (historyLeveldb)", du.historyLeveldb.toLocaleString(), (100 * du.historyLeveldb / du.total).toFixed(1)],
    ["Other (pvtdataStore, bookkeeper, configHistory, fileLock, ledgerProvider, directory overhead)", rest.toLocaleString(), (100 * rest / du.total).toFixed(1)],
    ["ledgersData total (5 Oct 2026; 24,311,978 on 21 Aug 2026 before LevelDB compaction)", du.total.toLocaleString(), "100.0"]];
}
function s15rows() {
  const out = [];
  for (const lam of ["0.001", "0.01", "0.1"]) {
    const fc = RJ(`flame_comparison_lam${lam}.json`); if (!fc) return missingRow("flame_comparison_lam*.json", 9);
    for (const r of fc) out.push([lam, r.attack, r.n_att, `${f4(r.flame.f1)} ± ${f4(r.flame.f1_sd)}`, f4(r.fedavg.f1), f4(r.lpra.f1),
      r.n_att ? `${r.flame.att_rej} of ${30 * r.n_att}` : "—", `${r.flame.hon_rej} of ${30 * (5 - r.n_att)}`, r.flame.mean_kept.toFixed(2)]);
  }
  return out;
}

const rules = [
  ["41,084", "ATTACK", "0.999", "backdoor, scanning", "TCP · pkt_ratio > 0.159 · no TLS · http_status ≤ 50 · src_pkts ≤ 6 · not ICMP · not DNS"],
  ["6,788", "normal", "0.998", "normal", "no reply pkts (pkt_ratio ≫ 1) · 4.5 µs < duration ≤ 0.315 s · src_ip_bytes > 113 · not HTTP · src_pkts ≤ 160"],
  ["2,627", "ATTACK", "1.000", "ddos, dos", "UDP · 0.50 < byte_ratio ≤ 2.43 · dns_RD · bytes/pkt(src) ≤ 80.8 · duration ≤ 0.10 s · src_ip_bytes > 62"],
  ["2,515", "normal", "1.000", "normal", "UDP · byte_ratio ≤ 0.50 · src_pkts ≤ 1 · not dns_rejected · src_ip_bytes ≤ 64"],
  ["2,026", "normal", "1.000", "normal", "TCP · pkt_ratio ≤ 0.159 · dst_ip_bytes ≤ 20"],
  ["1,449", "ATTACK", "0.989", "xss, password", "TCP · pkt_ratio > 0.159 · no TLS · http_status ≤ 50 · src_pkts > 6 · dst_ip_bytes ≤ 4.3 KB"],
  ["1,077", "ATTACK", "1.000", "ransomware", "TCP · pkt_ratio ≤ 0.159 · dst_ip_bytes > 48 · duration ≤ 0.16 ms"],
  ["1,031", "normal", "1.000", "normal", "UDP · byte_ratio ≤ 0.50 · src_pkts ≤ 1 · src_ip_bytes > 69 · DNS query · not dns_RD"],
  ["915", "normal", "1.000", "normal", "no reply pkts · duration > 0.315 s · 1.7 < bytes/pkt(src) ≤ 516 · conn_state S0 · UDP"],
  ["594", "normal", "0.992", "normal", "UDP · byte_ratio ≤ 0.50 · src_pkts ≤ 1 · 64 < src_ip_bytes ≤ 69"],
  ["467", "ATTACK", "0.999", "ransomware, xss", "TCP · pkt_ratio ≤ 0.159 · 20 < dst_ip_bytes ≤ 42 · duration ≤ 0.16 ms"],
  ["358", "ATTACK", "0.930", "injection, mitm", "TCP · pkt_ratio > 0.159 · no TLS · http_status ≤ 50 · src_pkts > 6 · dst_ip_bytes > 4.4 KB"],
];
const supp = new Document({ styles: { default: { document: { run: { font: F, size: 20 } } } }, sections: [{
  properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
  children: [
    new Paragraph({ children: [new TextRun({ text: "Supplementary Material", font: F, size: 28, bold: true })] }),
    p([t("Thawatchai Chomsiri 1 and Suwichai Phunsa 2,* — 1 Department of Information Technology, Research Center of Information Technology for the Future; 2 Department of Creative Media, Digital Contents for Development Research Unit; both Faculty of Informatics, Mahasarakham University, Mahasarakham 44150, Thailand. * Correspondence: suwichai.p@msu.ac.th", { size: 18 })]),
    p([t("for: A Multi-Layer Security Architecture for Smart-City IoT with Measured Limits: Edge Intrusion Detection, Screened Federated Learning and Ledger-Anchored Model Provenance", { italics: true })]),
    p([t("Experiment identifiers refer to Table 3 of the main text; result files are produced by run_poc.py and run_extended.py in the released code.", { size: 18 })]),
    h1("Table S1. Multi-class attack typing on TON_IoT (random forest 30 × 12, 54 native features, 70/30 stratified split)"),
    factTable(["Class", "Precision", "Recall", "F1", "Test support"], "tab_multiclass", [2200, 1600, 1600, 1600, 2026]),
    new Paragraph({ spacing: { before: 80, after: 160 }, children:
      P`Overall accuracy ${"mc_acc_pct"}%, macro-F1 ${"mc_macro_f1"}; ${"mc_worst"} (${"mc_worst_support"} test samples) is the weakest class (F1 ${"mc_worst_f1"}) and overlaps with normal traffic. Source: exp1m_multiclass_ton_iot.csv.`
        .map(r => new TextRun({ ...r, size: 18 })) }),
    h1("Table S2. Perimeter firewall-policy replication (Internet Firewall Data Set [18], 65,532 log entries)"),
    p([...P`Task: predict whether the firewall action is allow (0) or deny/drop/reset (1) from flow statistics alone (bias-aware, no ports) versus with the destination and NAT-destination ports added. The result is unambiguous: the best model reaches F1 = ${"fw_noport_f1"} without ports and ${"fw_port_f1"} with them, a difference of ${"fw_gain"} F1 points, so the ports carry no information that the flow counters do not already carry. The reason is mechanical rather than behavioural: a blocked flow receives no reply, so "Bytes Received" and "pkts_received" are zero, and the action is almost a deterministic function of the counters. This is exactly the kind of near-tautological task that a bias-aware evaluation must flag, and it is why the perimeter experiment is reported here as a sanity check rather than as evidence for the architecture: replicating a firewall's own decisions from its own accounting is not intrusion detection. The behavioural question — whether the traffic the firewall admits is benign — is the one Sections 5.1–5.8 answer, and there identifier-free features do not make the task trivial.`]),
    factTable(["Features", "Model", "F1", "ROC-AUC", "FPR"], "tab_firewall", [2400, 2400, 1400, 1400, 1426]),
    h1("Table S3. Native-view edge IDS results on the additional datasets (E12; exp1c_native_*.csv)"),
    factTable(["Dataset", "Rows", "Features", "Best model", "F1", "ROC-AUC", "FPR", "Latency (µs)"],
      "tab_native_extra", [1500, 1000, 1000, 1500, 900, 1000, 900, 1226]),
    h1("Table S4. LPRA joint threshold sensitivity: c_min \u00d7 \u03b3, with and without attack (K = 5, 10 rounds, seeds 42\u201344)"),
    rrTable(["Regime", "c_min", "\u03b3", "F1 (mean)", "Honest rejections", "Attacker rejections"], "threshold_sensitivity.json",
      d => d.map(r => [r.regime, r.c_min.toFixed(1), r.gamma.toFixed(1), f3(r.f1), `${r.hon} / ${r.hon_denom}`, r.att_denom ? `${r.att} / ${r.att_denom}` : "n/a"]),
      [1900, 900, 900, 1300, 2000, 2000]),
    cap("Without an attack, c_min is inactive up to 0.2 and then excludes honest clients; \u03b3 matters only at 1.5. Under the s = 6 opposing adaptive attack all eighteen cells are identical: Stage 1 alone is sufficient and the direction test is never binding. The submitted S4 swept \u03b3 alone at K = 20; those honest rejections were a partitioning artefact (Section 5.6) and the sweep is superseded. Source: review_response/threshold_sensitivity.json."),
    h1("Table S5. Leave-one-family-out F1 on TON_IoT: centralised tree, centralised MLP, federated MLP (E12 extension)"),
    rrTable(["Held-out family", "Test flows", "DT-8, centralised", "MLP 32-16, centralised", "MLP 32-16, federated (LPRA v2, K = 5)"], "loao_federated.json",
      d => { const rows = d.map(r => [r.family, r.n_test.toLocaleString(), f3(r.dt_f1), f3(r.mlp_central_f1), f3(r.lpra_f1)]);
             const m = k => f3(d.reduce((a, r) => a + r[k], 0) / d.length); rows.push(["mean", "", m("dt_f1"), m("mlp_central_f1"), m("lpra_f1")]); return rows; },
      [1900, 1300, 1900, 2000, 2200]),
    cap("Train on the other eight families plus benign; test on the held-out family plus held-out benign, on the 60k-flow sample used by the federated experiments (so the tree column is not the full-data run of Table 11: on ransomware the tree\u2019s recall on the unseen family is 0.81 there and 0.98 here). Model class accounts for about half the gap (ransomware: 0.365 centralised and 0.363 federated for the MLP), federation for the rest (MITM: 0.776 \u2192 0.412). Source: review_response/loao_federated.json."),
    h1("Table S6. Cross-dataset F1 on the nine directional features (E12)"),
    p("Datasets that do not separate the two flow directions (CICIoT2023) cannot appear in this view; they are covered by the direction-free matrix in Table 13 of the main text."),
    factTable(["Train \\ Test", "TON_IoT", "CIC-IDS2017", "UNSW-NB15"], "tab_cross_common",
      [2400, 1900, 1900, 1900]),
    h1("Table S7. Aggregator behaviour without the symbols of Table 9 (E5)"),
    factTable(["Aggregator", "No-attack F1", "Honest rejections, no attack (district-rounds)",
               "Attacker catch rate, scale (1 attacker)", "Honest rejections under attack"],
      "tab_agg_detail", [1700, 1500, 2200, 1600, 2100]),
    new Paragraph({ spacing: { before: 80, after: 160 }, children:
      P`Catch rate is the number of rounds out of ${"e5_rounds"} in which every attacker was quarantined, averaged over ${"e5_seeds"} seeds; rejections are counted in district-rounds over the same runs. Krum rejects K − 1 clients per round by construction, which is why its honest-rejection count is the largest and its no-attack F1 the lowest. Source: extA_byzantine_grid_summary.csv.`
        .map(r => new TextRun({ ...r, size: 18 })) }),

    h1("Table S7 (extension). Krum and Multi-Krum inside and outside n > 2f + 2 (f = 2; flip and scale attacks; seeds 42\u201344)"),
    rrTable(["K", "Attack", "Aggregator", "n > 2f+2", "F1 (mean \u00b1 s.d.)", "Attacker rej. (per seed)", "Honest \u201crej.\u201d (per seed)", "Rounds all caught", "What the count is"], "krum_regime.json",
      d => d.map(r => [r.K, r.attack, r.agg, r.in_regime ? "yes" : "no", `${f3(r.f1_mean)} \u00b1 ${f3(r.f1_sd)}`, `${r.att_rej.join("/")} of 20`, `${r.hon_rej.join("/")} of ${r.honest_n * 10}`, `${r.caught.join("/")} of 10`, r.agg === "lpra" ? "quarantine" : "non-selection"])
             .sort((a, b) => a[1].localeCompare(b[1]) || a[0] - b[0] || a[2].localeCompare(b[2])),
      [500, 700, 1200, 800, 1500, 1500, 1500, 1300, 1400], 15),
    cap("Under flip with two attackers, K = 5 reproduces Table 9\u2019s Krum instability (0.677 \u00b1 0.372) and it disappears at K = 7 and 9, where the condition holds. Krum\u2019s honest \u201crejections\u201d are non-selection by a single-winner rule and are not comparable to LPRA\u2019s quarantine decisions. Source: review_response/krum_regime.json."),
    // v2.1: the decision-tree leaves table (Table S5 in the submitted supplement) is renumbered S8; it was dropped by
    // mistake when S5 became the leave-one-family-out table in v2.0. Content unchanged.
    h1("Table S8. The most-populated leaves of the depth-8 decision tree (test split)"),
    factTable(["Test flows", "Prediction", "Purity", "Dominant true types", "Rule (conjunction of splits from the root)"],
      "tab_tree_rules", [1000, 1000, 800, 1700, 4526], 15),
    new Paragraph({ spacing: { before: 80, after: 160 }, children:
      P`The tree has ${"tree_leaves"} leaves at depth ${"tree_depth"}. pkt_ratio = src_pkts / (dst_pkts + 10⁻⁶), so a value much larger than 1 means the flow received no reply packets; purity is the fraction of the leaf's training samples in the predicted class. Source: exp8b_tree_rules.csv.`
        .map(r => new TextRun({ ...r, size: 18 })) }),
    h1("Section S9. Equivalence of the released and the corrected screen_updates()"),
    p("The released screen_updates() ranked the majority fallback over all K clients rather than over S\u2081 and lacked the INCONCLUSIVE branch; both are corrected in v2.0.0. The grid below re-runs Table 13\u2019s configurations under both versions and counts rounds whose accepted set differed: none did, and INCONCLUSIVE was never reached, so no reported number depends on the discrepancy."),
    rrTable(["K", "Seed", "Attack", "F1 released", "F1 corrected", "Honest rej. rel / corr", "Attacker rej. rel / corr", "Rounds differing", "INCONCLUSIVE"], "compare_scalability.json",
      d => d.map(r => [r.K, r.seed, r.attack, f3(r.f1_rel), f3(r.f1_pap), `${r.hon_rel} / ${r.hon_pap}`, `${r.att_rel} / ${r.att_pap}`, r.rounds_differ, r.inconclusive_rounds]),
      [500, 600, 800, 1100, 1100, 1500, 1600, 1200, 1300], 15),
    h1("Table S10. Extended tamper test against the emulated ledger (E19)"),
    rrTable(["Attack", "Attacker holds", "Detected", "verify_chain() result"], "tamper_extended.json",
      d => d.map(r => [r.attack.replace(/^\d\s/, ""), r.keys, r.detected ? "yes" : "NO", r.msg.split("(")[0].trim().slice(0, 70)]),
      [3200, 1500, 1000, 3600]),
    cap("Five validators, quorum four. Truncation and a quorum re-sign are not detected and are stated as limits in Sections 5.5 and 6.5. Source: review_response/tamper_extended.json."),
    // ---- Tables S11-S15 (release v2.2.0, second review round); the same data and captions as review_response/build_supp_addendum.js
    h1("Table S11. FLAME at K = 20 and 50 under the Table 13 protocol (20% Byzantine under the scaling attack, 10 rounds, seeds 42–44, F1 averaged over the last three rounds, mean ± population s.d. over seeds, 60k-flow sample, orphan-free partition; FLAME after its Algorithm 1, λ = 0.01 and 0.001)"),
    table(["K", "Aggregator", "Attack", "Attackers", "F1 (mean ± s.d.)", "Honest rejections (mean per seed, of honest district-rounds)", "Attacker rejections (all seeds)", "Rounds all attackers rejected (mean per seed)"], s11rows(), [500, 1300, 800, 900, 1500, 1900, 1400, 1400], 15),
    cap("Round 2 (Reviewer 1, C2): FLAME is implemented after Algorithm 1 of Nguyen et al. — cosine distance between the local models themselves, HDBSCAN with min_cluster_size = ⌊K/2⌋ + 1, min_samples = 1 and a single cluster allowed, clipping to the median norm over all K updates, an equal-weight mean of the admitted set and Gaussian noise σ = λ · S_t with λ = 0.01, the value FLAME used for its NIDS scenario (review_response/flame_impl.py). FedAvg and LPRA rows reproduce Table 13 exactly (same seeds, partition and sample). HDBSCAN forms a cluster in every round and admits 11–14 of 20 and 27–34 of 50 districts (every round logged in table13_flame_k20_50_clusterlog.json), so with no attack FLAME discards about two fifths of the honest district-rounds at both sizes (cost 0.025 F1 at K = 20 — 0.032 at λ = 0.001 — and 0.012 at K = 50); under the scaling attack it excludes every attacker (120 of 120, 300 of 300) and still discards 41 of 160 and 126 of 400 honest district-rounds. Two earlier runs are superseded and kept: table13_flame_k20_50_sklearn_defaults.json (scikit-learn’s HDBSCAN defaults, no cluster in any round) and table13_flame_k20_50_v2.1.0.json (cosine on the updates Wᵢ − G and λ = 0.001; it reported only 35 of 120 and 112 of 300 attacker-rounds excluded, an artefact of clustering the updates, withdrawn). Only the scaling attack was run at K = 20 and 50. Source: table13_flame_k20_50_summary.json and table13_flame_k20_50_summary_lam0.001.json (table13_flame_k20_50.py --lam)."),
    h1("Table S12. Attacker placement (E20): the Table 13 protocol with the Byzantine set varied (scaling attack, 20% Byzantine, 10 rounds, seeds 42–44, F1 averaged over the last three rounds)"),
    table(["K", "Placement", "Byzantine districts", "Dominant families they own", "FedAvg F1", "LPRA v2 F1 (mean ± s.d. over seeds)", "LPRA attacker rejections (mean per seed)", "LPRA honest rejections (range over seeds)", "Rounds all attackers rejected"], s12rows(), [450, 1000, 1300, 1900, 1000, 1500, 1100, 1100, 900], 14),
    cap("Round 2 (Reviewer 1, C3): every poisoning experiment in the paper makes the first n_att districts Byzantine. Here all five single-attacker placements are run at K = 5, and the fixed set plus four random draws (numpy default_rng(1000 + p), without replacement) at K = 10, 20 and 50, each under the three training seeds; the “fixed” row of each K is the published Table 13 placement. Families follow the orphan-free partition’s ownership rule (for K ≤ 9 family i belongs to district i mod K, so a district can own two; for K > 9 district d owns family d mod 9). The quarantine decision is placement-independent (every attacker quarantined in every round under every placement; honest rejections 0 at K = 5 and 50, 0–6 of 80 at K = 10 — Table 13’s fixed placement: 0–3 — and 0–6 of 160 at K = 20, as in Table 13); F1 after quarantine depends on how much of one family’s dominant share the quarantined districts owned — the 0.938–0.939 placements are those that quarantine a district holding most of the ransomware share — and the fixed placement is the most favourable to LPRA’s F1 at K = 10 and 50, equal-highest to three decimals at K = 5 and within 0.004 of the highest at K = 20. Source: table13_attacker_placement.json and _summary.json (table13_attacker_placement.py)."),
    h1("Table S13. Byzantine-fraction sweep (E21): K = 9 and 11, f = 2–6 Byzantine districts, 10 rounds, seeds 42–44, fixed placement (districts 0…f−1), F1 averaged over the last three rounds (mean ± population s.d.)"),
    table(["K", "f", "f/K", "Attack", "FedAvg F1", "LPRA v2 F1", "v2 attacker rej. (range / total)", "v2 honest rej. (range / total)", "v2 rounds all attackers rejected", "LPRA v1 (adaptive only): F1; honest rej."], s13rows(), [400, 350, 500, 800, 1200, 1200, 1300, 1300, 1100, 1700], 14),
    cap("Round 2 (Reviewer 3, point 3). Attacks: scale (×10 update), label flip, Gaussian-noise weights, and the colluding adaptive attacker of Table 10 (opposing direction, strength s = 6, all attackers sending the same vector — the worst case for a median). Three regimes: the screen holds to f/K ≈ 0.36 (every scaled, noisy and adaptive attacker quarantined in 10/10 rounds; label flipping, visible only to the direction test, is the first to slip, from f/K = 0.33); it degrades without inverting at 0.44–0.45 (adaptive attackers 30–34 of 40 and 36–40 of 50 quarantined with 6–14 honest rejections, F1 0.96; LPRA v1 collapses here as it did at K = 5, f = 2); and it inverts above one half, where the identical colluding vectors are the median (adaptive: every honest district rejected, F1 0.14; flip: F1 0.15 against FedAvg’s 0.59–0.71; scale: no attacker rejected, F1 equal to FedAvg’s). The INCONCLUSIVE branch was never reached in the 270 runs; in such a round every district would count as rejected. Source: fk_boundary_sweep.json and _summary.json (fk_boundary_sweep.py)."),
    h1("Table S14. Composition of the Fabric ledger bytes of Table 15 (E22): the E13 peer’s block file decoded transaction by transaction"),
    table(["Component of one anchored-alert transaction", "Bytes per transaction", "% of block file"], s14rows(), [5400, 1500, 1200], 16),
    table(["ledgersData on disk (peer0.org1)", "Bytes", "%"], s14b(), [5400, 1500, 1200], 16),
    cap("Round 2 (Reviewer 3, point 4). The block file of the E13 ledger (408 blocks; 4,004 endorser transactions = 4,001 AnchorAlert invocations + 3 chaincode-lifecycle transactions; 3 configuration transactions; 8,006 endorsements) is read by fabric/bench/decode_blockfile.py, a dependency-free parser of fabric’s block serialization and protobuf wire format whose layout and field numbers were checked against the fabric release-2.5 source. X.509 certificates alone are 3,907 bytes of the 5,480 bytes a transaction occupies (71%; 73% of the whole file): the client’s certificate appears in both the payload header and the action header and each of the two endorsements carries the endorser’s, so 16,014 certificate copies of only a handful of distinct certificates (ten in the whole file, 769–1,034 bytes each) sit in the 4,004 transactions. The AnchorAlert arguments themselves are 160 bytes; the stored JSON alert appears twice (in the write set and in the chaincode response). The 60.8 MB per 10,000 alerts of Table 15 is 24,311,978 bytes / 4,001 alerts × 10,000, a linear extrapolation; the on-disk total measured on 5 October 2026 is 1.04 MB smaller than on 21 August because LevelDB compacted the index and state databases after a restart, the block file being unchanged. Source: fabric/blockfile_composition.json (fabric/bench/decode_blockfile.py)."),
    h1("Table S15. FLAME at K = 5 for three noise levels λ (E18; three seeds, 10 rounds, F1 averaged over the last three rounds)"),
    table(["λ", "Attack", "Attackers", "FLAME F1 (mean ± s.d.)", "FedAvg F1", "LPRA v2 F1", "FLAME attacker rejections", "FLAME honest rejections", "Mean admitted of 5"], s15rows(), [600, 900, 900, 1500, 1000, 1000, 1300, 1300, 1000], 15),
    cap("Round 2 (Reviewer 1, C2(b)–(c)). FLAME derives λ = (1/ε)·√(2 ln(1.25/δ)) from a per-scenario privacy budget and used λ = 0.001 for image classification and word prediction and λ = 0.01 for its network-intrusion-detection scenario; the main text uses 0.01. At λ = 0.001 and 0.01 every cell sits on the three-district plateau of 0.939 and the admitted set is three of five in 176–179 of 180 rounds; at λ = 0.1 the noise lifts F1 off that plateau by an amount that varies with the draw (between-seed s.d. 0.004–0.013), which is a sensitivity to report, not a benefit to claim. Noise is seeded from the previous global model, so every cell reproduces on its own. Source: flame_comparison_lam0.001.json, flame_comparison_lam0.01.json (= flame_comparison.json) and flame_comparison_lam0.1.json (compare_flame.py --lam)."),
    h1("Figure S1. Cross-dataset F1 heat maps (E12)"),
    ...(fs.existsSync(RES + "fig5_cross_dataset_dirfree4.png")
      ? [new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(RES + "fig5_cross_dataset_dirfree4.png"), transformation: { width: 380, height: 310 } })] })]
      : [p([TBD("[fig5_cross_dataset_dirfree4.png appears once the extra datasets are in data/ and run_poc.py has been re-run]")])]),
  ] }] });
Packer.toBuffer(supp).then(b => { fs.writeFileSync(path.join(ROOT, "Supplementary_Material.docx"), b); if (missing.size) console.log("supp placeholders:", [...missing].join(", ")); });

const cover = new Document({ styles: { default: { document: { run: { font: F, size: 22 } } } }, sections: [{
  properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
  children: [
    p([t("Dr. Thawatchai Chomsiri", { bold: true, size: 22 })]),
    p([t("Department of Information Technology, Research Center of Information Technology for the Future,")]),
    p([t("Faculty of Informatics, Mahasarakham University, Mahasarakham 44150, Thailand; thawatchai.c@msu.ac.th")]),
     p([t("21 August 2026")]),
    p([t("Prof. Dr. Pierluigi Siano, Editor-in-Chief, Smart Cities (MDPI)", { size: 22 })]),
    p([t("Dear Professor Siano,", { size: 22 })]),
    p("Please find enclosed the manuscript \"A Multi-Layer Trustworthy Security Architecture for Smart-City IoT: Edge AI Intrusion Detection, Poisoning-Resilient Federated Learning and Ledger-Anchored Model Provenance\", which my co-author Suwichai Phunsa (corresponding author) and I would like to submit as an Article to Smart Cities."),
    p("Smart-city platforms connect thousands of IoT devices across transport, energy, water, healthcare and e-government, so that district gateways become attack entry points and security logs become evidence that several independent agencies must trust. Intrusion detection, federated learning and blockchain auditing have each been studied in isolation; the manuscript evaluates them together, on real traffic, and quantifies the trade-offs a city operator actually faces."),
    p("The main contributions are: (i) a four-layer architecture with an explicit threat model that also covers insider attacks on the security system itself; (ii) LPRA, a ledger-anchored poisoning-resilient aggregation rule for the federated layer whose accept/quarantine decisions are recorded on a consortium ledger, benchmarked against FedAvg, Median, Trimmed Mean, Krum and Multi-Krum with one and two Byzantine districts—LPRA matches Multi-Krum under attack while, unlike the classical robust rules, costing nothing when no attack is present (they lose 3.2 F1 points to district heterogeneity) and, unlike Krum, remaining stable when two of five districts are malicious; (iii) a bias-aware, dataset-agnostic feature schema enabling cross-dataset evaluation across IoT and enterprise traffic; and (iv) a validity and scalability study (unseen-attack families, feature ablation, five-seed confidence intervals, 5–50 districts, 3–15 validators) plus a replayed zero-day ransomware scenario that reports time-to-detect per layer. All experiments are reproducible from a single-command open-source pipeline."),
    p("The work falls within the journal's scope under Core Technologies & Methods (AI/ML, IoT, blockchain, cloud/edge), Key Application Areas (urban governance, sustainable and resilient infrastructure) and the cross-cutting themes of cybersecurity & privacy and AI governance. The manuscript has not been published and is not under consideration elsewhere. In the interest of full disclosure: a separate manuscript by the same authors, on extreme class imbalance and explainability in firewall log classification, is currently under review at another journal. It uses three of the same public datasets (CIC-IDS2017, UNSW-NB15 and the UCI Internet Firewall Data Set) but shares no result, model, figure or text with this submission; the present work is about a multi-layer city architecture and uses those datasets only as stand-ins for municipal data-centre traffic in the cross-dataset experiment. Section 4.1 states this in the manuscript itself. The authors declare no conflict of interest."),
        p("Thank you for considering this manuscript."), p("Sincerely,"), p([t("Thawatchai Chomsiri", { bold: true })]),
    p([t("Department of Information Technology, Research Center of Information Technology for the Future, Faculty of Informatics, Mahasarakham University; thawatchai.c@msu.ac.th", { size: 18 })]),
    p([t("Corresponding author for this submission: Suwichai Phunsa, suwichai.p@msu.ac.th", { size: 18 })]),
  ] }] });
Packer.toBuffer(cover).then(b => { fs.writeFileSync(path.join(ROOT, "Cover_Letter.docx"), b); console.log("ok"); });
