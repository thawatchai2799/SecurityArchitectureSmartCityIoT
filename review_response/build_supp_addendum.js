const path = require("path");
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType } = require("docx");

const EV = __dirname + "/";
const J = (n) => JSON.parse(fs.readFileSync(EV + n, "utf8"));
const F = "Times New Roman";
const t = (x, o = {}) => new TextRun({ text: x, font: F, size: 20, ...o });
const p = (x, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 276 }, children: Array.isArray(x) ? x : [t(x)], ...o });
const FILL = { G: "C6EFCE", P: "FFC7CE", Y: "FFEB9C", V: "E4D0F5", S: "D9D9D9" };
const sh = (fill) => ({ type: ShadingType.CLEAR, fill, color: "auto" });
const h1 = (s, fill) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: s, font: F, size: 22, bold: true, color: "000000", shading: fill ? sh(fill) : undefined })] });
const note = (s) => new Paragraph({ spacing: { before: 80, after: 160 }, children: [t(s, { size: 18 })] });
function table(headers, rows, widths, fs = 17) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (txt, w, bold, shade) => new TableCell({ width: { size: w, type: WidthType.DXA }, shading: shade ? { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } : undefined, margins: { top: 40, bottom: 40, left: 60, right: 60 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: String(txt), font: F, size: fs, bold })] })] });
  const mk = (cells, bold, shade) => new TableRow({ children: cells.map((c, i) => cell(c, widths[i], bold, shade)) });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, borders: { top: { style: BorderStyle.SINGLE, size: 6 }, bottom: { style: BorderStyle.SINGLE, size: 6 }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE }, insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "999999" }, insideVertical: { style: BorderStyle.NONE } }, rows: [mk(headers, true, true), ...rows.map(r => mk(r, false, false))] });
}
const f3 = (x) => (Math.round(x * 1000) / 1000).toFixed(3);

// ---------------- S4: joint c_min x gamma sweep
const sens = J("threshold_sensitivity.json");
const s4rows = sens.map(r => [r.regime, r.c_min.toFixed(1), r.gamma.toFixed(1), f3(r.f1),
  `${r.hon} / ${r.hon_denom}`, r.att_denom ? `${r.att} / ${r.att_denom}` : "n/a"]);

// ---------------- S5: leave-one-family-out
const loao = J("loao_federated.json");
const s5rows = loao.map(r => [r.family, r.n_test.toLocaleString(), f3(r.dt_f1), f3(r.mlp_central_f1), f3(r.lpra_f1)]);
const mean = (k) => f3(loao.reduce((a, r) => a + r[k], 0) / loao.length);
s5rows.push(["mean", "", mean("dt_f1"), mean("mlp_central_f1"), mean("lpra_f1")]);

// ---------------- S7 addition: Krum in and out of regime, under flip (the attack behind Table 9's 0.677) and scale
const krum = J("krum_regime.json");
const s7rows = krum.map(r => [r.K, r.attack, r.agg, r.in_regime ? "yes" : "no", `${f3(r.f1_mean)} ± ${f3(r.f1_sd)}`,
  `${r.att_rej.join("/")} of 20`, `${r.hon_rej.join("/")} of ${r.honest_n * 10}`, `${r.caught.join("/")} of 10`,
  r.agg === "lpra" ? "quarantine" : "non-selection"])
  .sort((a, b) => a[1].localeCompare(b[1]) || a[0] - b[0] || a[2].localeCompare(b[2]));

// ---------------- S9: equivalence check
const eq = J("compare_scalability.json");
const s9rows = eq.map(r => [r.K, r.seed, r.attack, f3(r.f1_rel), f3(r.f1_pap), `${r.hon_rel} / ${r.hon_pap}`,
  `${r.att_rel} / ${r.att_pap}`, r.rounds_differ, r.inconclusive_rounds]);
const totalRounds = eq.length * 10, differ = eq.reduce((a, r) => a + r.rounds_differ, 0);

// ---------------- S10: extended tamper test
const tam = J("tamper_extended.json");
// ---------------- S11: FLAME at K = 20 and 50 under the Table 13 protocol (authors' extension of Section 5.3)
const fl = J("table13_flame_k20_50_summary.json");
const f4 = (x) => (Math.round(x * 10000) / 10000).toFixed(4);
const aggName = { fedavg: "FedAvg", flame: "FLAME", lpra: "LPRA v2" };
const s11rows = fl.map(r => [r.K, aggName[r.aggregator], r.attack === "none" ? "none" : "scale", r.n_att,
  `${f4(r.f1)} \u00b1 ${f4(r.f1_sd)}`,
  `${r.honest_rej} of ${(r.K - r.n_att) * 10}`,
  r.aggregator === "fedavg" ? "\u2014" : (r.n_att ? `${r.att_rej_sum} of ${r.n_att * 30}` : "\u2014"),
  r.aggregator === "fedavg" ? "\u2014" : (r.n_att ? `${r.caught_mean.toFixed(0)} of 10` : "\u2014")]);
const s10rows = tam.map(r => [r.attack.replace(/^\d\s/, ""), r.keys, r.detected ? "yes" : "NO", r.msg.split("(")[0].trim().slice(0, 70)]);

const doc = new Document({ styles: { default: { document: { run: { font: F, size: 20 } } } }, sections: [{
  properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
  children: [
    new Paragraph({ children: [new TextRun({ text: "Supplementary Material — addendum for the revised manuscript (revise-v30)", font: F, size: 24, bold: true })], spacing: { after: 120 } }),
    p("This addendum replaces Table S4, adds Table S5, Section S9 and Tables S10 and S11, and extends Table S7 of the submitted Supplementary Material. The former Table S5 (decision-tree leaves) becomes Table S8, unchanged. Every number here is regenerated from the revised repository (release v2.1.0); the scripts are in review_response/ and each table names its source file."),
    p([t("Colour key (same as the revised manuscript and the response letter): ", { bold: true }), t("green = added or replaced for Reviewer 1", { shading: sh(FILL.G) }), t("; "), t("pink = for Reviewer 3", { shading: sh(FILL.P) }), t("; "), t("yellow = for Reviewer 2", { shading: sh(FILL.Y) }), t("; "), t("purple = for the Academic Editor (algorithm\u2013implementation agreement; experiments re-run after correction)", { shading: sh(FILL.V) }), t("; "), t("grey = changed by the authors on their own initiative (self-review corrections and the pre-submission additions; Table S11)", { shading: sh(FILL.S) }), t(". Each section heading below is shaded with the colour of the reviewer whose comment it answers, or grey where the authors added it unasked (Table S11); every number in this addendum was regenerated under release v2.1.0 as the Academic Editor asked, and the numbers that moved relative to the first revision because of the authors\u2019 own corrections are listed in the repository CHANGELOG (v2.1).")]),

    h1("Table S4. LPRA joint threshold sensitivity: c_min × γ, with and without attack (K = 5, 10 rounds, seeds 42–44)", FILL.G),
    table(["Regime", "c_min", "γ", "F1 (mean)", "Honest rejections", "Attacker rejections"], s4rows, [1900, 900, 900, 1300, 2000, 2000]),
    note("Without an attack, c_min is inactive up to 0.2 and then excludes honest clients; γ matters only at 1.5. Under the s = 6 opposing adaptive attack with two attackers, all eighteen cells are identical: the Stage-1 magnitude test alone is sufficient and the direction test is never binding, so c_min is unconstrained by this attack. The submitted S4 swept γ alone at K = 20; those honest rejections were a partitioning artefact (main text Section 5.6) and the sweep is superseded. Source: threshold_sensitivity.json (compare_sensitivity.py)."),

    h1("Table S5. Leave-one-family-out F1 on TON_IoT: centralised tree, centralised MLP, federated MLP (E12 extension)", FILL.G),
    table(["Held-out family", "Test flows", "DT-8, centralised", "MLP 32-16, centralised", "MLP 32-16, federated (LPRA v2, K = 5)"], s5rows, [1900, 1300, 1900, 2000, 2200]),
    note("Train on the other eight families plus benign; test on the held-out family plus held-out benign, on the 60k-flow sample used by the federated experiments (so the tree column is not the full-data run of Table 11: on ransomware the tree\u2019s recall on the unseen family is 0.81 there and 0.98 here). The MLP is the network the federated layer uses; the centralised MLP was trained for 31 epochs (one bootstrap epoch plus the 15 × 2 local epochs of the E3 budget) and the federated one for 10 rounds × 2 local epochs = 20, so the centralised control had more, not fewer, passes over the data. Model class accounts for about half the gap (ransomware: 0.365 centralised and 0.363 federated for the MLP), federation for the rest (MITM: 0.776 → 0.412). Source: loao_federated.json (compare_loao.py)."),

    h1("Table S7 (extension). Krum and Multi-Krum inside and outside the resilience condition n > 2f + 2 (f = 2; flip and scale attacks; seeds 42–44)", FILL.G),
    table(["K", "Attack", "Aggregator", "n > 2f+2", "F1 (mean \u00b1 s.d.)", "Attacker rej. (per seed)", "Honest \u201crej.\u201d (per seed)", "Rounds all caught", "What the count is"], s7rows, [500, 700, 1200, 800, 1500, 1500, 1500, 1300, 1400], 15),
    note("Under the flip attack with two attackers, K = 5 \u2014 where n > 2f + 2 fails and _krum_scores() uses a single nearest neighbour \u2014 reproduces the instability of Table 9: Krum scores 0.677 \u00b1 0.372, and in one of three seeds it selects an attacker in all ten rounds. At K = 7 and K = 9, where the condition holds, the instability disappears: Krum holds at 0.938 \u00b1 0.000 and both attackers are non-selected in every round of every seed. Under the scale attack Krum is stable at every K (0.938\u20130.940), so that attack never exercised the condition. Krum\u2019s honest \u201crejections\u201d are non-selection by a single-winner rule and rise with K for that reason alone (67%, 80%, 86% of honest district-rounds); they are not comparable to LPRA\u2019s quarantine decisions, and the main-text Table 9 caption and this table label them as non-selection. Source: krum_regime.json (compare_krum.py)."),

    h1("Section S9. Equivalence of the released and the corrected screen_updates()", FILL.G),
    p(`The released screen_updates() differed from Algorithm 1 in two ways: its majority fallback ranked cosine over all K clients rather than over S\u2081, and it lacked the INCONCLUSIVE branch. Both are corrected in release v2.0.0. The table re-runs the scalability grid under both versions on the same seeds, partitions and attacks and counts the rounds in which the accepted set differed. Over ${eq.length} configurations and ${totalRounds} aggregation rounds, ${differ} rounds differed and the INCONCLUSIVE branch was never reached, so no reported number depends on the discrepancy. A synthetic far-but-direction-aligned attacker does separate the two (the released fallback readmits it and displaces an honest client); the paper\u2019s rule is the one the code now implements.`),
    table(["K", "Seed", "Attack", "F1 released", "F1 corrected", "Honest rej. rel / corr", "Attacker rej. rel / corr", "Rounds differing", "INCONCLUSIVE rounds"], s9rows, [500, 600, 800, 1100, 1100, 1500, 1600, 1200, 1300], 15),
    note("Grid as in Table 13: K in {5, 10, 20, 50}, 20% Byzantine under the scaling attack, seeds 42\u201344, orphan-free partition; its LPRA rows match Table 13\u2019s per-seed values. An earlier run used one scaled attacker at every K with the same outcome (no round differed); it is kept as compare_scalability_one_attacker.json. Source: compare_scalability.json (compare_scale.py); the K = 5 adaptive-attack conditions in compare_k5_adaptive.log show the same identity."),

    h1("Table S10. Extended tamper test against the emulated ledger (E19)", FILL.P),
    table(["Attack", "Attacker holds", "Detected", "verify_chain() result"], s10rows, [3200, 1500, 1000, 3600]),
    note("Five validators, quorum four. Two attacks are not detected and are stated as limits in main-text Sections 5.5 and 6.5: truncation leaves an internally consistent shorter chain, and a chain re-signed with a validator quorum is accepted as intact (the honest-majority bound of Proof-of-Authority, measured). Source: tamper_extended.json (compare_tamper.py)."),
    h1("Table S11. FLAME at K = 20 and 50 under the Table 13 protocol (20% Byzantine under the scaling attack, 10 rounds, seeds 42\u201344, F1 averaged over the last three rounds, mean \u00b1 population s.d. over seeds, 60k-flow sample, orphan-free partition)", FILL.S),
    table(["K", "Aggregator", "Attack", "Attackers", "F1 (mean \u00b1 s.d.)", "Honest rejections (mean per seed, of honest district-rounds)", "Attacker rejections (all seeds)", "Rounds all attackers rejected (mean per seed)"], s11rows, [500, 1000, 800, 900, 1500, 2000, 1500, 1500], 15),
    note("Reviewer 3 asked for the FLAME comparison of Section 5.3 (K = 5, the regime FLAME\u2019s authors identify as weakest for clustering); this extension to K = 20 and 50 was not requested and was run by the authors before resubmission. FedAvg and LPRA rows reproduce Table 13 exactly (same seeds, partition and sample). HDBSCAN is run with FLAME\u2019s own settings (min_cluster_size = \u230aK/2\u230b + 1, min_samples = 1, single cluster allowed, cosine distance; every round logged in table13_flame_k20_50_clusterlog.json): it forms a cluster in every round and keeps about 11 of 20 and 30 of 50 districts (the \u230aK/2\u230b + 1 floor is 11 and 26), so FLAME discards about 87 of 200 and 195 of 500 honest district-rounds per seed with no attack (cost 0.033 and 0.011 F1 against FedAvg) and, under the scaling attack, excludes only 35 of 120 and 112 of 300 attacker-rounds, finishing at K = 20 below undefended FedAvg. An earlier run with scikit-learn\u2019s HDBSCAN defaults (no single cluster allowed) found no cluster in any round; it is kept as table13_flame_k20_50_sklearn_defaults.json and superseded. Only the scaling attack was run at K = 20 and 50. FLAME implementation as in compare_flame.py. Source: table13_flame_k20_50.json and table13_flame_k20_50_summary.json (table13_flame_k20_50.py)."),
  ] }] });

Packer.toBuffer(doc).then(b => { fs.writeFileSync(__dirname + "/../Supplementary_Addendum.docx", b); console.log("written"); });
