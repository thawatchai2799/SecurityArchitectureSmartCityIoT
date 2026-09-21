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
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [typeof txt === "string" ? new TextRun({ text: txt, font: F, size: fs, bold }) : txt] })] });
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
    h1("Table S11. FLAME at K = 20 and 50 under the Table 13 protocol (20% Byzantine under the scaling attack, 10 rounds, seeds 42\u201344, F1 averaged over the last three rounds, mean \u00b1 population s.d. over seeds, 60k-flow sample, orphan-free partition)"),
    rrTable(["K", "Aggregator", "Attack", "Attackers", "F1 (mean \u00b1 s.d.)", "Honest rejections (mean per seed, of honest district-rounds)", "Attacker rejections (all seeds)", "Rounds all attackers rejected (mean per seed)"], "table13_flame_k20_50_summary.json",
      d => d.map(r => [r.K, { fedavg: "FedAvg", flame: "FLAME", lpra: "LPRA v2" }[r.aggregator], r.attack, r.n_att,
        `${(Math.round(r.f1 * 10000) / 10000).toFixed(4)} \u00b1 ${(Math.round(r.f1_sd * 10000) / 10000).toFixed(4)}`,
        `${r.honest_rej} of ${(r.K - r.n_att) * 10}`,
        r.aggregator === "fedavg" || !r.n_att ? "\u2014" : `${r.att_rej_sum} of ${r.n_att * 30}`,
        r.aggregator === "fedavg" || !r.n_att ? "\u2014" : `${r.caught_mean.toFixed(0)} of 10`]),
      [500, 1000, 800, 900, 1500, 2000, 1500, 1500], 15),
    cap("Section 5.3 tested FLAME only at K = 5, the regime its authors identify as weakest for clustering. FedAvg and LPRA rows reproduce Table 13 exactly (same seeds, partition and sample). HDBSCAN is run with FLAME\u2019s own settings (min_cluster_size = \u230aK/2\u230b + 1, min_samples = 1, single cluster allowed, cosine distance; every round logged in review_response/table13_flame_k20_50_clusterlog.json): it forms a cluster in every round and keeps about 11 of 20 and 30 of 50 districts (the \u230aK/2\u230b + 1 floor is 11 and 26), so FLAME discards about 87 of 200 and 195 of 500 honest district-rounds per seed with no attack (cost 0.033 and 0.011 F1 against FedAvg) and, under the scaling attack, excludes only 35 of 120 and 112 of 300 attacker-rounds, finishing at K = 20 below undefended FedAvg. An earlier run with scikit-learn\u2019s HDBSCAN defaults (no single cluster allowed) found no cluster in any round; it is kept as review_response/table13_flame_k20_50_sklearn_defaults.json and superseded. Only the scaling attack was run at K = 20 and 50. Source: review_response/table13_flame_k20_50_summary.json (table13_flame_k20_50.py)."),
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
