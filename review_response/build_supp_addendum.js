const path = require("path");
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType } = require("docx");

const EV = __dirname + "/";
const J = (n) => JSON.parse(fs.readFileSync(EV + n, "utf8"));
const F = "Times New Roman";
const t = (x, o = {}) => new TextRun({ text: x, font: F, size: 20, ...o });
const p = (x, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 276 }, children: Array.isArray(x) ? x : [t(x)], ...o });
const h1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: s, font: F, size: 22, bold: true, color: "000000" })] });
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

// ---------------- S7 addition: Krum in and out of regime
const krum = J("krum_regime.json");
const byK = {};
for (const r of krum) { const k = `${r.K}|${r.agg}`; (byK[k] = byK[k] || []).push(r); }
const s7rows = Object.entries(byK).map(([k, rs]) => {
  const [K, agg] = k.split("|"); const honest = Number(K) - 2;
  const f1 = rs.reduce((a, r) => a + r.f1, 0) / rs.length;
  const hon = rs.map(r => r.hon_rej).join("/"), att = rs.map(r => r.att_rej).join("/");
  return [K, agg, Number(K) > 6 ? "yes" : "no", f3(f1), `${att} of 20`, `${hon} of ${honest * 10}`,
    agg === "lpra" ? "quarantine" : "non-selection"];
}).sort((a, b) => Number(a[0]) - Number(b[0]) || a[1].localeCompare(b[1]));

// ---------------- S9: equivalence check
const eq = J("compare_scalability.json");
const s9rows = eq.map(r => [r.K, r.seed, r.attack, f3(r.f1_rel), f3(r.f1_pap), `${r.hon_rel} / ${r.hon_pap}`,
  `${r.att_rel} / ${r.att_pap}`, r.rounds_differ, r.inconclusive_rounds]);
const totalRounds = eq.length * 10, differ = eq.reduce((a, r) => a + r.rounds_differ, 0);

// ---------------- S10: extended tamper test
const tam = J("tamper_extended.json");
const s10rows = tam.map(r => [r.attack.replace(/^\d\s/, ""), r.keys, r.detected ? "yes" : "NO", r.msg.split("(")[0].trim().slice(0, 70)]);

const doc = new Document({ styles: { default: { document: { run: { font: F, size: 20 } } } }, sections: [{
  properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
  children: [
    new Paragraph({ children: [new TextRun({ text: "Supplementary Material — addendum for the revised manuscript (revise-v09)", font: F, size: 24, bold: true })], spacing: { after: 120 } }),
    p("This addendum replaces Table S4, adds Tables S5, S9 and S10, and extends Table S7 of the submitted Supplementary Material. The former Table S5 (decision-tree leaves) becomes Table S8, unchanged. Every number here is regenerated from the revised repository (release v2.0.0); the scripts are in review_response/ and each table names its source file."),

    h1("Table S4. LPRA joint threshold sensitivity: c_min × γ, with and without attack (K = 5, 10 rounds, seeds 42–44)"),
    table(["Regime", "c_min", "γ", "F1 (mean)", "Honest rejections", "Attacker rejections"], s4rows, [1900, 900, 900, 1300, 2000, 2000]),
    note("Without an attack, c_min is inactive up to 0.2 and then excludes honest clients; γ matters only at 1.5. Under the s = 6 opposing adaptive attack with two attackers, all eighteen cells are identical: the Stage-1 magnitude test alone is sufficient and the direction test is never binding, so c_min is unconstrained by this attack. The submitted S4 swept γ alone at K = 20; those honest rejections were a partitioning artefact (main text Section 5.6) and the sweep is superseded. Source: threshold_sensitivity.json (compare_sensitivity.py)."),

    h1("Table S5. Leave-one-family-out F1 on TON_IoT: centralised tree, centralised MLP, federated MLP (E12 extension)"),
    table(["Held-out family", "Test flows", "DT-8, centralised", "MLP 32-16, centralised", "MLP 32-16, federated (LPRA v2, K = 5)"], s5rows, [1900, 1300, 1900, 2000, 2200]),
    note("Train on the other eight families plus benign; test on the held-out family plus held-out benign. The MLP is the network the federated layer uses (~30 epochs centralised, matching 15 rounds × 2 local epochs). Model class accounts for about half the gap (ransomware: 0.363 for the MLP whether centralised or federated), federation for the rest (MITM: 0.764 → 0.414). Source: loao_federated.json (compare_loao.py)."),

    h1("Table S7 (extension). Krum and Multi-Krum inside and outside the resilience condition n > 2f + 2 (f = 2, scale attack, seeds 42–44)"),
    table(["K", "Aggregator", "n > 2f+2", "F1 (mean)", "Attacker rounds rejected (per seed)", "Honest \u201crejections\u201d (per seed)", "What the count is"], s7rows, [600, 1500, 1000, 1200, 2400, 2200, 1500]),
    note("At K = 5, f = 2 the condition fails and _krum_scores() uses one nearest neighbour; Krum\u2019s F1 is nonetheless stable in and out of regime (0.938–0.941). Krum\u2019s honest \u201crejections\u201d are non-selection by a single-winner rule and rise with K for that reason alone (67%, 80%, 86% of honest district-rounds); they are not comparable to LPRA\u2019s quarantine decisions and the main-text Table 9 no longer places them in the same column. Source: krum_regime.json (compare_krum.py)."),

    h1("Section S9. Equivalence of the released and the corrected screen_updates()"),
    p(`The released screen_updates() differed from Algorithm 1 in two ways: its majority fallback ranked cosine over all K clients rather than over S\u2081, and it lacked the INCONCLUSIVE branch. Both are corrected in release v2.0.0. The table re-runs the scalability grid under both versions on the same seeds, partitions and attacks and counts the rounds in which the accepted set differed. Over ${eq.length} configurations and ${totalRounds} aggregation rounds, ${differ} rounds differed and the INCONCLUSIVE branch was never reached, so no reported number depends on the discrepancy. A synthetic far-but-direction-aligned attacker does separate the two (the released fallback readmits it and displaces an honest client); the paper\u2019s rule is the one the code now implements.`),
    table(["K", "Seed", "Attack", "F1 released", "F1 corrected", "Honest rej. rel / corr", "Attacker rej. rel / corr", "Rounds differing", "INCONCLUSIVE rounds"], s9rows, [500, 600, 800, 1100, 1100, 1500, 1600, 1200, 1300], 15),
    note("Source: compare_scalability.json (compare_scale.py); the K = 5 adaptive-attack conditions in compare_k5_adaptive.log show the same identity."),

    h1("Table S10. Extended tamper test against the emulated ledger (E19)"),
    table(["Attack", "Attacker holds", "Detected", "verify_chain() result"], s10rows, [3200, 1500, 1000, 3600]),
    note("Five validators, quorum four. Two attacks are not detected and are stated as limits in main-text Sections 5.5 and 6.5: truncation leaves an internally consistent shorter chain, and a chain re-signed with a validator quorum is accepted as intact (the honest-majority bound of Proof-of-Authority, measured). Source: tamper_extended.json (compare_tamper.py)."),
  ] }] });

Packer.toBuffer(doc).then(b => { fs.writeFileSync(__dirname + "/../Supplementary_Addendum.docx", b); console.log("written"); });
