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
    p([t("for: A Multi-Layer Trustworthy Security Architecture for Smart-City IoT: Edge AI Intrusion Detection, Poisoning-Resilient Federated Learning and Ledger-Anchored Model Provenance", { italics: true })]),
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
    h1("Table S4. LPRA threshold sensitivity at K = 20 districts (extreme non-IID; 4 of 20 Byzantine under 'scale'; 10 rounds; seed 42)"),
    factTable(["γ (stage-1 floor)", "Attack", "Global F1", "Rounds all attackers caught", "Honest rejections (district-rounds)"],
      "tab_gamma", [1700, 1900, 1400, 2200, 1826]),
    new Paragraph({ spacing: { before: 80, after: 160 }, children:
      P`γ = ${"gamma_lo"}–5 give identical results, showing that the remaining honest rejections at K = 20 come from the direction test (c_min = 0.2) rather than from the distance test; γ = ${"gamma_hi"} reduces them from ${"gamma_lo_rej"} to ${"gamma_hi_rej"} per 10 rounds (F1 ${"gamma_hi_f1"}) while still catching every attacker. Source: extC_lpra_gamma_sensitivity_K20.csv.`
        .map(r => new TextRun({ ...r, size: 18 })) }),
    h1("Table S5. The most-populated leaves of the depth-8 decision tree (test split)"),
    factTable(["Test flows", "Prediction", "Purity", "Dominant true types", "Rule (conjunction of splits from the root)"],
      "tab_tree_rules", [1000, 1000, 800, 1700, 4526], 15),
    new Paragraph({ spacing: { before: 80, after: 160 }, children:
      P`The tree has ${"tree_leaves"} leaves at depth ${"tree_depth"}. pkt_ratio = src_pkts / (dst_pkts + 10⁻⁶), so a value much larger than 1 means the flow received no reply packets; purity is the fraction of the leaf's training samples in the predicted class. Source: exp8b_tree_rules.csv.`
        .map(r => new TextRun({ ...r, size: 18 })) }),
    h1("Table S7. Aggregator behaviour without the symbols of Table 9 (E5)"),
    factTable(["Aggregator", "No-attack F1", "Honest rejections, no attack (district-rounds)",
               "Attacker catch rate, scale (1 attacker)", "Honest rejections under attack"],
      "tab_agg_detail", [1700, 1500, 2200, 1600, 2100]),
    new Paragraph({ spacing: { before: 80, after: 160 }, children:
      P`Catch rate is the number of rounds out of ${"e5_rounds"} in which every attacker was quarantined, averaged over ${"e5_seeds"} seeds; rejections are counted in district-rounds over the same runs. Krum rejects K − 1 clients per round by construction, which is why its honest-rejection count is the largest and its no-attack F1 the lowest. Source: extA_byzantine_grid_summary.csv.`
        .map(r => new TextRun({ ...r, size: 18 })) }),

    h1("Table S6. Cross-dataset F1 on the nine directional features (E12)"),
    p("Datasets that do not separate the two flow directions (CICIoT2023) cannot appear in this view; they are covered by the direction-free matrix in Table 13 of the main text."),
    factTable(["Train \\ Test", "TON_IoT", "CIC-IDS2017", "UNSW-NB15"], "tab_cross_common",
      [2400, 1900, 1900, 1900]),
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
