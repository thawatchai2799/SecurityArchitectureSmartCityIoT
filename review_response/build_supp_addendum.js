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
// ---------------- S11: FLAME at K = 20 and 50 under the Table 13 protocol (Algorithm-1 implementation; round 2, Reviewer 1 C2)
const fl = J("table13_flame_k20_50_summary.json");
const fl001 = J("table13_flame_k20_50_summary_lam0.001.json").filter(r => r.aggregator === "flame");
const f4 = (x) => (Math.round(x * 10000) / 10000).toFixed(4);
const aggName = { fedavg: "FedAvg", flame: "FLAME (λ = 0.01)", lpra: "LPRA v2" };
const s11row = (r, name) => [r.K, name, r.attack === "none" ? "none" : "scale", r.n_att,
  `${f4(r.f1)} ± ${f4(r.f1_sd)}`,
  `${r.honest_rej} of ${(r.K - r.n_att) * 10}`,
  r.aggregator === "fedavg" ? "—" : (r.n_att ? `${r.att_rej_sum} of ${r.n_att * 30}` : "—"),
  r.aggregator === "fedavg" ? "—" : (r.n_att ? `${r.caught_mean.toFixed(0)} of 10` : "—")];
const s11rows = [];
for (const K of [20, 50]) {
  for (const r of fl.filter(r => r.K === K)) s11rows.push(s11row(r, aggName[r.aggregator]));
  for (const r of fl001.filter(r => r.K === K)) s11rows.push(s11row(r, "FLAME (λ = 0.001)"));
}
// ---------------- S12: attacker placement (round 2, Reviewer 1 C3)
const pl = J("table13_attacker_placement_summary.json");
const s12rows = [];
for (const K of [5, 10, 20, 50]) {
  const fa = pl.find(r => r.K === K && r.agg === "fedavg"), lp = pl.find(r => r.K === K && r.agg === "lpra");
  lp.placements.forEach((q, i) => {
    const fq = fa.placements[i];
    s12rows.push([K, K === 5 ? (i === 0 ? "fixed (district 0)" : `district ${i}`) : (i === 0 ? "fixed" : `random ${i}`), q.attackers.join(", "), q.families.join(", "), f4(fq.f1),
      `${f4(q.f1)} ± ${f4(q.f1_sd_seeds)}`, `${q.att_mean.toFixed(0)} of ${lp.attacker_rounds}`,
      `${q.hon_min}–${q.hon_max} of ${lp.honest_district_rounds}`, `${q.caught_mean.toFixed(0)} of 10`]);
  });
  s12rows.push([K, "over placements", "", "", `${f4(fa.f1_mean)} ± ${f4(fa.f1_sd)} [${f4(fa.f1_min)}, ${f4(fa.f1_max)}]`,
    `${f4(lp.f1_mean)} ± ${f4(lp.f1_sd)} [${f4(lp.f1_min)}, ${f4(lp.f1_max)}]`, `${lp.att_rej_mean} of ${lp.attacker_rounds}`,
    `${lp.hon_rej_min}–${lp.hon_rej_max} of ${lp.honest_district_rounds}`, `${lp.caught_mean} of 10`]);
}
// ---------------- S13: Byzantine-fraction sweep (round 2, Reviewer 3 point 3)
const fk = J("fk_boundary_sweep_summary.json");
const s13rows = [];
for (const K of [9, 11]) for (const f of [2, 3, 4, 5, 6]) for (const attack of ["scale", "flip", "noise", "adaptive"]) {
  const fa = fk.find(r => r.K === K && r.f === f && r.attack === attack && r.agg === "fedavg");
  const v2 = fk.find(r => r.K === K && r.f === f && r.attack === attack && r.agg === "lpra_v2");
  const v1 = fk.find(r => r.K === K && r.f === f && r.attack === attack && r.agg === "lpra_v1");
  s13rows.push([K, f, (f / K).toFixed(2), attack, `${f4(fa.f1_mean)} ± ${f4(fa.f1_sd)}`, `${f4(v2.f1_mean)} ± ${f4(v2.f1_sd)}`,
    v2.att_rej.replace('-', '\u2013'), v2.hon_rej.replace('-', '\u2013'), v2.caught.replace('-', '\u2013'), v1 ? `${f4(v1.f1_mean)} ± ${f4(v1.f1_sd)}; hon ${v1.hon_rej}` : "—"]);
}
// ---------------- S14: composition of the Fabric ledger bytes (round 2, Reviewer 3 point 4)
const comp = JSON.parse(fs.readFileSync(EV + "../fabric/blockfile_composition.json", "utf8"));
const compNames = [["endorser_cert", "Endorser identities (X.509 certificate + MSP id), two per transaction"], ["payload_header", "Payload header: channel header + signature header (client certificate, nonce)"],
  ["action_header", "Action header: signature header again (client certificate, nonce)"], ["rwset", "Read/write set (_lifecycle reads + cityanchor read/write of the alert key)"],
  ["response_events_ccid", "Chaincode response (repeats the stored alert) + chaincode id; no events"], ["proposal_payload", "Proposal payload: the AnchorAlert arguments"],
  ["endorser_signature", "Endorser signatures (two)"], ["envelope_signature", "Client signature over the envelope"], ["block_metadata", "Block metadata (orderer signature, validity flags), share per transaction"],
  ["proposal_hash", "Proposal hash"], ["block_header", "Block header hashes, share per transaction"]];
const s14rows = compNames.map(([k, name]) => [name, comp.per_tx_bytes[k].toFixed(0), comp.share[k].toFixed(1)]);
s14rows.push(["Protobuf framing, length prefixes, configuration transactions (share)", (comp.file_bytes_per_tx - compNames.reduce((a, [k]) => a + comp.per_tx_bytes[k], 0)).toFixed(0), (100 - compNames.reduce((a, [k]) => a + comp.share[k], 0)).toFixed(1)]);
s14rows.push(["Block file per transaction", comp.file_bytes_per_tx.toFixed(0), "100.0"]);
const du = comp.ledgersData_du_bytes_2026_10_05;
const s14b = [["Block file (chains/chains/mychannel/blockfile_000000)", du.chains_blockfile.toLocaleString(), (100 * du.chains_blockfile / du.total).toFixed(1)],
  ["Block index (chains/index)", du.chains_index.toLocaleString(), (100 * du.chains_index / du.total).toFixed(1)],
  ["State database (stateLeveldb)", du.stateLeveldb.toLocaleString(), (100 * du.stateLeveldb / du.total).toFixed(1)],
  ["History database (historyLeveldb)", du.historyLeveldb.toLocaleString(), (100 * du.historyLeveldb / du.total).toFixed(1)],
  ["Other (pvtdataStore, bookkeeper, configHistory, fileLock, ledgerProvider, directory overhead)", (du.total - du.chains_blockfile - du.chains_index - du.stateLeveldb - du.historyLeveldb).toLocaleString(), (100 * (du.total - du.chains_blockfile - du.chains_index - du.stateLeveldb - du.historyLeveldb) / du.total).toFixed(1)],
  ["ledgersData total (5 Oct 2026; 24,311,978 on 21 Aug 2026 before LevelDB compaction)", du.total.toLocaleString(), "100.0"]];
// ---------------- S15: FLAME lambda sensitivity at K = 5 (round 2, Reviewer 1 C2)
const s15rows = [];
for (const lam of ["0.001", "0.01", "0.1"]) {
  const fc = J(`flame_comparison_lam${lam}.json`);
  for (const r of fc) s15rows.push([lam, r.attack, r.n_att, `${f4(r.flame.f1)} ± ${f4(r.flame.f1_sd)}`, f4(r.fedavg.f1), f4(r.lpra.f1),
    r.n_att ? `${r.flame.att_rej} of ${30 * r.n_att}` : "—", `${r.flame.hon_rej} of ${30 * (5 - r.n_att)}`, r.flame.mean_kept.toFixed(2)]);
}
const s10rows = tam.map(r => [r.attack.replace(/^\d\s/, ""), r.keys, r.detected ? "yes" : "NO", r.msg.split("(")[0].trim().slice(0, 70)]);

const doc = new Document({ styles: { default: { document: { run: { font: F, size: 20 } } } }, sections: [{
  properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
  children: [
    new Paragraph({ children: [new TextRun({ text: "Supplementary Material — addendum for the revised manuscript (revise-v32)", font: F, size: 24, bold: true })], spacing: { after: 120 } }),
    p("This addendum replaces Table S4, adds Table S5, Section S9 and Tables S10 to S15, and extends Table S7 of the submitted Supplementary Material. The former Table S5 (decision-tree leaves) becomes Table S8, unchanged. Every number here is regenerated from the revised repository (release v2.2.0); the scripts are in review_response/ (Table S14: fabric/bench/) and each table names its source file. Tables S11 to S15 are new in or regenerated for the second revision."),
    p([t("Colour key (same as the revised manuscript and the response letter): ", { bold: true }), t("green = added or replaced for Reviewer 1", { shading: sh(FILL.G) }), t("; "), t("pink = for Reviewer 3", { shading: sh(FILL.P) }), t("; "), t("yellow = for Reviewer 2", { shading: sh(FILL.Y) }), t("; "), t("purple = for the Editors (round 1: the Academic Editor\u2019s algorithm\u2013implementation agreement and re-run; round 2: the Highlights section the Section Managing Editor asked for)", { shading: sh(FILL.V) }), t("; "), t("grey = changed by the authors on their own initiative (self-review corrections and pre-submission additions)", { shading: sh(FILL.S) }), t(". Each section heading below is shaded with the colour of the reviewer whose comment it answers (Table S11, first added unasked, was regenerated for Reviewer 1 in the second round and is green); every number in this addendum is from release v2.2.0; Tables S11 to S15 were added or regenerated in the second round and the numbers that moved against the first revision are listed in the repository CHANGELOG (v2.2.0).")]),

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
    h1("Table S11. FLAME at K = 20 and 50 under the Table 13 protocol (20% Byzantine under the scaling attack, 10 rounds, seeds 42–44, F1 averaged over the last three rounds, mean ± population s.d. over seeds, 60k-flow sample, orphan-free partition; FLAME after its Algorithm 1, λ = 0.01 and 0.001)", FILL.G),
    table(["K", "Aggregator", "Attack", "Attackers", "F1 (mean ± s.d.)", "Honest rejections (mean per seed, of honest district-rounds)", "Attacker rejections (all seeds)", "Rounds all attackers rejected (mean per seed)"], s11rows, [500, 1300, 800, 900, 1500, 1900, 1400, 1400], 15),
    note("Round 2 (Reviewer 1, C2): FLAME is implemented after Algorithm 1 of Nguyen et al. — cosine distance between the local models themselves, HDBSCAN with min_cluster_size = ⌊K/2⌋ + 1, min_samples = 1 and a single cluster allowed, clipping to the median norm over all K updates, an equal-weight mean of the admitted set and Gaussian noise σ = λ · S_t with λ = 0.01, the value FLAME used for its NIDS scenario (review_response/flame_impl.py). FedAvg and LPRA rows reproduce Table 13 exactly (same seeds, partition and sample). HDBSCAN forms a cluster in every round and admits 11–14 of 20 and 27–34 of 50 districts (every round logged in table13_flame_k20_50_clusterlog.json), so with no attack FLAME discards about two fifths of the honest district-rounds at both sizes (cost 0.025 F1 at K = 20 — 0.032 at λ = 0.001 — and 0.012 at K = 50); under the scaling attack it excludes every attacker (120 of 120, 300 of 300) and still discards 41 of 160 and 126 of 400 honest district-rounds. Two earlier runs are superseded and kept: table13_flame_k20_50_sklearn_defaults.json (scikit-learn’s HDBSCAN defaults, no cluster in any round) and table13_flame_k20_50_v2.1.0.json (cosine on the updates Wᵢ − G and λ = 0.001; it reported only 35 of 120 and 112 of 300 attacker-rounds excluded, an artefact of clustering the updates, withdrawn). Only the scaling attack was run at K = 20 and 50. Source: table13_flame_k20_50_summary.json and table13_flame_k20_50_summary_lam0.001.json (table13_flame_k20_50.py --lam)."),

    h1("Table S12. Attacker placement (E20): the Table 13 protocol with the Byzantine set varied (scaling attack, 20% Byzantine, 10 rounds, seeds 42–44, F1 averaged over the last three rounds)", FILL.G),
    table(["K", "Placement", "Byzantine districts", "Dominant families they own", "FedAvg F1", "LPRA v2 F1 (mean ± s.d. over seeds)", "LPRA attacker rejections (mean per seed)", "LPRA honest rejections (range over seeds)", "Rounds all attackers rejected"], s12rows, [450, 1000, 1300, 1900, 1000, 1500, 1100, 1100, 900], 14),
    note("Round 2 (Reviewer 1, C3): every poisoning experiment in the paper makes the first n_att districts Byzantine. Here all five single-attacker placements are run at K = 5, and the fixed set plus four random draws (numpy default_rng(1000 + p), without replacement) at K = 10, 20 and 50, each under the three training seeds; the “fixed” row of each K is the published Table 13 placement. Families follow the orphan-free partition’s ownership rule (for K ≤ 9 family i belongs to district i mod K, so a district can own two; for K > 9 district d owns family d mod 9). The quarantine decision is placement-independent (every attacker quarantined in every round under every placement; honest rejections 0 at K = 5 and 50, 0–6 of 80 at K = 10 — Table 13’s fixed placement: 0–3 — and 0–6 of 160 at K = 20, as in Table 13); F1 after quarantine depends on how much of one family’s dominant share the quarantined districts owned — the 0.938–0.939 placements are those that quarantine a district holding most of the ransomware share — and the fixed placement is the most favourable to LPRA’s F1 at K = 10 and 50, equal-highest to three decimals at K = 5 and within 0.004 of the highest at K = 20. Source: table13_attacker_placement.json and _summary.json (table13_attacker_placement.py)."),

    h1("Table S13. Byzantine-fraction sweep (E21): K = 9 and 11, f = 2–6 Byzantine districts, 10 rounds, seeds 42–44, fixed placement (districts 0…f−1), F1 averaged over the last three rounds (mean ± population s.d.)", FILL.P),
    table(["K", "f", "f/K", "Attack", "FedAvg F1", "LPRA v2 F1", "v2 attacker rej. (range / total)", "v2 honest rej. (range / total)", "v2 rounds all attackers rejected", "LPRA v1 (adaptive only): F1; honest rej."], s13rows, [400, 350, 500, 800, 1200, 1200, 1300, 1300, 1100, 1700], 14),
    note("Round 2 (Reviewer 3, point 3). Attacks: scale (×10 update), label flip, Gaussian-noise weights, and the colluding adaptive attacker of Table 10 (opposing direction, strength s = 6, all attackers sending the same vector — the worst case for a median). Three regimes: the screen holds to f/K ≈ 0.36 (every scaled, noisy and adaptive attacker quarantined in 10/10 rounds; label flipping, visible only to the direction test, is the first to slip, from f/K = 0.33); it degrades without inverting at 0.44–0.45 (adaptive attackers 30–34 of 40 and 36–40 of 50 quarantined with 6–14 honest rejections, F1 0.96; LPRA v1 collapses here as it did at K = 5, f = 2); and it inverts above one half, where the identical colluding vectors are the median (adaptive: every honest district rejected, F1 0.14; flip: F1 0.15 against FedAvg’s 0.59–0.71; scale: no attacker rejected, F1 equal to FedAvg’s). The INCONCLUSIVE branch was never reached in the 270 runs; in such a round every district would count as rejected. Source: fk_boundary_sweep.json and _summary.json (fk_boundary_sweep.py)."),

    h1("Table S14. Composition of the Fabric ledger bytes of Table 15 (E22): the E13 peer’s block file decoded transaction by transaction", FILL.P),
    table(["Component of one anchored-alert transaction", "Bytes per transaction", "% of block file"], s14rows, [5400, 1500, 1200], 16),
    table(["ledgersData on disk (peer0.org1)", "Bytes", "%"], s14b, [5400, 1500, 1200], 16),
    note("Round 2 (Reviewer 3, point 4). The block file of the E13 ledger (408 blocks; 4,004 endorser transactions = 4,001 AnchorAlert invocations + 3 chaincode-lifecycle transactions; 3 configuration transactions; 8,006 endorsements) is read by fabric/bench/decode_blockfile.py, a dependency-free parser of fabric’s block serialization and protobuf wire format whose layout and field numbers were checked against the fabric release-2.5 source. X.509 certificates alone are 3,907 bytes of the 5,480 bytes a transaction occupies (71%; 73% of the whole file): the client’s certificate appears in both the payload header and the action header and each of the two endorsements carries the endorser’s, so 16,014 certificate copies of only a handful of distinct certificates (ten in the whole file, 769–1,034 bytes each) sit in the 4,004 transactions. The AnchorAlert arguments themselves are 160 bytes; the stored JSON alert appears twice (in the write set and in the chaincode response). The 60.8 MB per 10,000 alerts of Table 15 is 24,311,978 bytes / 4,001 alerts × 10,000, a linear extrapolation; the on-disk total measured on 5 October 2026 is 1.04 MB smaller than on 21 August because LevelDB compacted the index and state databases after a restart, the block file being unchanged. Source: fabric/blockfile_composition.json (fabric/bench/decode_blockfile.py)."),

    h1("Table S15. FLAME at K = 5 for three noise levels λ (E18; three seeds, 10 rounds, F1 averaged over the last three rounds)", FILL.G),
    table(["λ", "Attack", "Attackers", "FLAME F1 (mean ± s.d.)", "FedAvg F1", "LPRA v2 F1", "FLAME attacker rejections", "FLAME honest rejections", "Mean admitted of 5"], s15rows, [600, 900, 900, 1500, 1000, 1000, 1300, 1300, 1000], 15),
    note("Round 2 (Reviewer 1, C2(b)–(c)). FLAME derives λ = (1/ε)·√(2 ln(1.25/δ)) from a per-scenario privacy budget and used λ = 0.001 for image classification and word prediction and λ = 0.01 for its network-intrusion-detection scenario; the main text uses 0.01. At λ = 0.001 and 0.01 every cell sits on the three-district plateau of 0.939 and the admitted set is three of five in 176–179 of 180 rounds; at λ = 0.1 the noise lifts F1 off that plateau by an amount that varies with the draw (between-seed s.d. 0.004–0.013), which is a sensitivity to report, not a benefit to claim. Noise is seeded from the previous global model, so every cell reproduces on its own. Source: flame_comparison_lam0.001.json, flame_comparison_lam0.01.json (= flame_comparison.json) and flame_comparison_lam0.1.json (compare_flame.py --lam)."),
  ] }] });

Packer.toBuffer(doc).then(b => { fs.writeFileSync(__dirname + "/../Supplementary_Addendum.docx", b); console.log("written"); });
