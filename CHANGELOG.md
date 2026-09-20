# Colour key of the revised manuscript (revise-v15) and its companions

The manuscript file `smartcities-4547789_revise-v15.docx`, the Supplementary
addendum and the response letter shade every passage that differs from the
submitted version by the source of the change:

| colour | hex | source |
|---|---|---|
| green  | `#C6EFCE` | changed in response to Reviewer 1 |
| pink   | `#FFC7CE` | changed in response to Reviewer 3 |
| yellow | `#FFEB9C` | changed in response to Reviewer 2 |
| purple | `#E4D0F5` | changed at the Editor's request (none yet; the length decision is deferred to the Editor) |
| grey   | `#D9D9D9` | errors found and corrected by the authors in self-review (this file, v2.1) |

The shading is produced by `review_response/highlight_changes.py` from the
submitted and the revised manuscript and is removed at proof stage.

# What changed in v2.1 (code + results + supplement) — second self-review

## A. Results regenerated under the v2.1 code (district-local initialisation)

The v2.0 code initialises the global model from one district's own data
(`_bootstrap_within`), but the K = 5 tables of the manuscript (Tables 6–10)
still carried the submitted runs, made with the pooled draw, and several
review_response/ JSONs had also been produced before the change landed
(`compare_independent_attacks.py` even imported the pooled `_bootstrap`
explicitly).  Everything is now regenerated under the released code:

* `results/extA_byzantine_grid_{raw,summary}.csv` (Table 9, Figure 4) —
  `run_extended.py --part A`.  LPRA and Multi-Krum cells unchanged; FedAvg,
  Median and Trimmed-Mean cells under attack moved (e.g. FedAvg scale×1
  0.923 → 0.950 ± 0.036, scale×2 0.959 → 0.926 ± 0.042, noise×2 0.748 → 0.672).
* `results/exp17_adaptive_sweep.csv` (Table 10, Figure 5) —
  `run_advanced.py --part A --n-att {1,2}`.  F1 unchanged to three decimals;
  six "rounds caught" counts moved by one or two.
* `results/extB_*.csv` (Section 5.4 five-seed values) — `run_extended.py --part B`:
  FedAvg 0.9708 ± 0.0007, centralised 0.9942 ± 0.0003, local-only 0.9516 ± 0.0024
  (were 0.0006 / 0.9944 ± 0.0004 / 0.9517); edge-model F1 and FPR unchanged.
  (`extended_results.json` here holds only the extA and extB blocks of these
  runs — merge, do not replace.)
* `review_response/exp3_exp9_rerun.{py,json}` (Tables 6–8, full data): only
  FedAvg under Gaussian noise moved (0.686 → 0.780); every LPRA and no-attack
  number and every personalised-FL number is identical.
* `review_response/independent_attacks.json`: sign-flip FedAvg 0.609–0.879 →
  0.607–0.886; backdoor LPRA 0.939–0.949 (31/60 quarantined) → 0.950–0.960
  (29/60), FedAvg 0.970 → 0.952–0.971.  The earlier "screening cost" claim is
  correspondingly softened in Section 5.3.
* `review_response/threshold_sensitivity.json`: honest rejections at
  c_min = 0.4 / 0.6 / 0.8 are 11 / 31 / 51 of 150 (were 10 / 32 / 50).
* `review_response/krum_regime.json`: the Krum rows are unchanged (K = 5 flip
  0.677 ± 0.372; K = 7, 9 0.938); the LPRA and Multi-Krum rows at K = 7, 9
  moved (e.g. LPRA 0.960 → 0.967 / 0.970).
* `review_response/flame_comparison.json`: FLAME no-attack 0.943 → 0.947
  (cost 0.024, not 0.028); adaptive 0.589 unchanged.
* `review_response/loao_federated.json`: now also carries the centralised-MLP
  column (31 partial-fit epochs, computed inside `compare_loao.py`; the
  v2.0 column came from an unshuffled ad-hoc run that was never committed):
  mean 0.885 → 0.887, MITM 0.764 → 0.776; federated MITM 0.414 → 0.412.
* `review_response/compare_scalability.json` (Section S9) re-run: still 0 of
  240 rounds differ, INCONCLUSIVE never reached.

## B. Table 13 provenance

`table13_definitive.json` was a one-attacker run and did not match Table 13
(20% Byzantine).  Replaced by `table13_perseed.{py,json}`: every per-seed
value, from which `results/extC_districts_scaling.csv` (mean of the last three
rounds; population s.d. over seeds) is reproduced exactly.  Seven s.d. cells
of the manuscript's Table 13 had been mistyped and are corrected.

## C. Supplement

* `paper_src/make_supp.js`: the decision-tree leaves table (S5 in the submitted
  supplement) had been dropped when S5 became the leave-one-family-out table
  in v2.0.  Restored as **Table S8**, content unchanged; the title line carries
  the revised manuscript title.  Main text Section 5.1 now cites S8.
* `review_response/build_supp_addendum.js`: the S7-extension note still said
  Krum was "stable in and out of regime" (the conclusion of the first,
  scale-only run); rewritten to match `krum_regime.json`.
* Leave-one-family-out federated mean 0.8155 → reported as 0.815.

## D. Housekeeping

* `results/extC_validators_scaling.csv` and `extC_blocksize_sweep.csv`
  (interpolated, never measured) removed; `results/figures/fig7_scalability.png`
  is the composite with the original panels (b), (c).
* `review_response/compare_krum.py`, `compare_ledger_latency.py`,
  `ledger_latency_5x.json` added (see v2.0 D/E).
* The `RESPONSE_*_draft.md` files are superseded by the response letter and
  removed.


# What changed in v2.0 (code) — the peer-review revision

Three reviewers of the submitted manuscript read the released code against
the paper.  Four of their findings were correct and are fixed here.  Every
fix was verified by re-executing the affected experiments under both the
old and the new code before the change was made, so that the effect on the
reported numbers is measured, not assumed.  The comparison harnesses and
their outputs are in `review_response/`.

## A. `screen_updates()` did not match Algorithm 1 (Reviewer 1, C1)

Two deviations.  The majority fallback ranked cosine over all K clients and
took the global top floor(K/2)+1, so a client rejected by the Stage-1
magnitude test could be readmitted; Algorithm 1 restricts the fallback to
S1.  And the INCONCLUSIVE branch (|S1| <= floor(K/2): do not aggregate,
keep w_g) was absent.  Both corrected in `poc/robust_fl.py`;
`byzantine.aggregate()` now keeps the current global model when
`screen_updates()` returns `None`.

Effect on reported results: none.  Re-executing the full K in {5,10,20,50}
grid (240 aggregation rounds, three seeds) under both versions produced the
identical accepted set in every round; the INCONCLUSIVE branch was never
reached.  A synthetic far-but-direction-aligned attacker does separate the
two -- the old fallback readmits it and displaces an honest client -- which
is why the paper's rule, not the code's, was kept.

## B. Global model was initialised from pooled data (Reviewer 1, C3)

`_bootstrap()` drew 500 class-balanced examples from the pooled training
arrays to give sklearn's first `fit()` both classes.  This contradicted
"raw flows never leave the districts."  Replaced by `_bootstrap_within()`,
which draws from district 0's own partition only, in `federated.py`,
`robust_fl.py` and `byzantine.py`.

Effect: none at K = 5 (F1 0.9707 +- 0.0003 under both, to four decimals).
At K >= 10 initialisation is one of several sources of seed-level variance
and is now reported as such alongside the other fixes.

## C. `partition()` left most districts without an attack family for K > 9 (Reviewer 1, C6)

Families were assigned by `family_index mod K`, so for K > 9 districts
9..K-1 received no dominant family -- 11 of 20 at K = 20, 41 of 50 at
K = 50.  Those "orphan" districts, holding only a diluted mix, became the
majority; LPRA's median reference locked onto them and rejected the nine
family-owning districts in nearly every round.  That was the entire source
of the 80/200 and 90/500 honest rejections in the submitted Table 13.
Instrumenting which districts were rejected confirmed it: owners 89-100%
of rounds, orphans 0%.

Fixed: ownership is now round-robin in whichever direction is longer, so
every family has an owner and every district has a family.  For K <= 9 the
partition is unchanged.  Effect: K = 20 honest rejections 80-82 -> 0-9;
K = 50: 90 -> 0; attacker still quarantined 10/10 in every configuration.
Table 13 is regenerated from this code (`table13_definitive.json`).

## D. E11 timed submission, not commit (Reviewer 1, C2c)

`city_simulation.EdgeGateway.process()` stopped its timer when
`ledger.submit()` returned, i.e. after a mempool append.  The block is cut
later.  The 0.03 ms "anchoring" figure was submission cost; commit latency
at E11's own settings (block 50, interval 0.5 s) is 0.79 ms mean over five repeats (`ledger_latency_5x.json`).  The manuscript
is corrected; the code is unchanged, since `_cut_block()` already recorded
the right quantity in `metrics["tx_latencies"]` -- the harness simply
reported the wrong one.

## E. Figure 7

Panel (a) is redrawn from the corrected Table 13.  Panels (b) validators and
(c) block size are the original measured curves, kept pixel-for-pixel: a
first revision pass redrew them from three-point CSVs reconstructed from the
prose (endpoints correct, intermediate points interpolated) and that figure
was withdrawn once the interpolation was noticed.  The measured
extC_validators_scaling.csv and extC_blocksize_sweep.csv are not in this
release because results/ is not distributed; regenerate them with
run_extended.py before re-running make_figures.fig_scalability().

## F. Added, not changed

- `review_response/` -- every comparison harness, its raw output, and the
  extended tamper test (deletion, truncation, re-signing with minority and
  quorum keys), FLAME baseline, leave-one-family-out under federated
  training, and four attacks not used in LPRA v2's development.
- `partition()` docstring now states the K > T behaviour explicitly.


This file records what was fixed and why during the development of the experiments, including several bugs
that only appeared on a second machine. It is kept in the repository because the failures are as informative
as the results: a Windows code-page crash, a resubstitution score in a cross-dataset matrix, a membership
check that accepted any name beginning with "Gateway-", and a Docker build path that recent engines no
longer serve. Readers reproducing the work may hit the same walls.

---

# What changed in v05 (code) — and why

Findings from five review passes over the v04 code and manuscript.

## A. Bugs that would have broken the run on Windows
| # | Problem | Why it matters | Fix |
|---|---|---|---|
| A1 | `run_poc.py` wrote `REPORT.md` with `open(..., "w")`; the text contains `—` and `×` | On a Thai Windows console/locale (cp874) this raises `UnicodeEncodeError` and the run dies **after** all the computation | `encoding="utf-8"` on every write; `sys.stdout.reconfigure(encoding="utf-8")` in both runners |
| A2 | `DATASETS.md` told the user to run `merge_csv.py CICIoT2023_parts/*.csv …` | cmd.exe/PowerShell do **not** expand wildcards, so the pattern arrives as literal text and no file is found | `tools/merge_csv.py` now expands globs itself; docs quote the pattern |
| A3 | `run_extended.py --part fig` before A/C/D crashed with `FileNotFoundError` | The parts are meant to be run separately on a slow machine | missing files are listed with the command that produces them |

## B. Bugs that would have produced wrong numbers
| # | Problem | Why it matters | Fix |
|---|---|---|---|
| B1 | Cross-dataset (Exp-2) trained on the **whole** dataset and tested on the whole dataset | The diagonal of the transfer matrix was a resubstitution score — a reviewer would flag it immediately | train on each dataset's training split, test on the other's held-out split |
| B2 | CICIoT2023 was mapped with `dst_pkts ← IAT` (inter-arrival time) | CICIoT2023 has no directional split, so the 9 directional features were meaningless for it, silently corrupting every transfer result involving it | added a 4-feature **direction-free** view; CICIoT2023 is flagged `direction_proxy=True` and only compared on that view |
| B3 | The paper claimed "one leaf covers 65% of attack test flows" | The share had been divided by *all* test flows, not attack flows; the true figure is 85% | the rule table and the share are now extracted from the trained tree (`Exp-8b`) and injected into the text |
| B4 | Ledger accepted any submitter whose name started with `Gateway-` | The manuscript claims un-enrolled nodes are rejected; an impersonating node would have been accepted | explicit enrolment list (Fabric MSP stand-in); the test now tries `RogueNode`, `Gateway-Fake` and a case-variant, all rejected |
| B5 | Timing numbers were hard-coded into the manuscript from a single run | Latency on a shared vCPU varied 39–58 µs between runs; the paper drifted from the code | every number now comes from `results/paper_facts.json` |

## C. Robustness / correctness issues
| # | Problem | Fix |
|---|---|---|
| C1 | FL bootstrap drew 500 random rows; on a very imbalanced dataset it can contain one class and `fit()` fails | class-balanced bootstrap (`_bootstrap`) |
| C2 | `_maybe_sample` did not sub-sample the firewall `X_ports` frame → silent length mismatch | every DataFrame in the loader result is sampled consistently |
| C3 | A wrong/renamed column produced garbage features silently | `_require()` raises with the missing names **and** the full list of columns found |
| C4 | Merged CSVs can contain repeated header rows; label case varies between distributions | header rows dropped, label column looked up case-insensitively |
| C5 | UNSW-NB15 dropped its categorical columns (proto/service/state) | one-hot encoding of the 20 most frequent levels |
| C6 | Tamper test indexed `chain[3]` unconditionally | index guarded |
| C7 | `city_simulation` correlation ran on wall-clock replay time (meaningless) | kept as a smoke test, documented as superseded by E11; the paper does not cite it |
| C8 | The standardiser is fitted on pooled training data (mild information sharing) | kept, but now disclosed in code comments **and** in Section 6.5 of the paper |

## D. Additions
* `check_env.py` — 10-second preflight: Python/packages, write access, and a real load test of every dataset present.
* `paper_src/make_facts.py` — turns the results into `paper_facts.json` (187 numbers, 12 tables); both DOCX generators read only that file.
* `poc/generalisation.tree_rules()` — extracts the tree's most-populated leaves for the explainability paragraph and Table S5.
* `poc/byzantine.py` gained an `lpra_gamma` knob so the threshold sweep (Table S4) is reproducible.
* Table 2 of the paper is now a dataset table again (native per-dataset results moved to Supplementary Table S3), and Table 12 (district scaling) is new.

## E. Effect of the fixes on the results
Re-running everything with v05 changed some numbers slightly (the class-balanced bootstrap changes FL
initialisation) and, in two places, strengthened the story:
* the heterogeneity tax of Median/Trimmed Mean/Krum/Multi-Krum grew from 2.3 to **3.2 F1 points**;
* Krum is now shown to become **unstable with two attackers (0.677 ± 0.456)** because its single-winner
  rule sometimes selects an attacker — a failure mode LPRA does not have;
* LPRA catches the label-flipping attacker in **10/10** rounds (E5) with **0** false quarantines in 150
  district-rounds.

---

# v06 (manuscript) — figure audit, author block, author's own references

## F. Figure consistency audit (requested)
Every figure was traced back to the run that produced it and checked against the tables and prose.

| Figure | Status | Action |
|---|---|---|
| Fig. 1 architecture | **numbers were stale** — it printed "~55 µs/flow" while the measured value is 51 ± 3 µs, and it did not mention the enrolment list added in code v05 | rewritten as `paper_src/make_fig1.py`, which reads `paper_facts.json`; the box now prints 17.8 KB / 51 ± 3 µs, "92 KB / round", "31.9 MB kept local" and the A2 row now says "rogue **or impersonating** node" |
| Fig. 2 edge IDS | consistent — produced by the same `run_poc.py` run as Tables 4–5 | none |
| Fig. 3 federated | consistent with Table 6 (seed 42 curve, multi-seed values in the table) | caption already states "seed 42" |
| Fig. 4 aggregator grid | regenerated from `extA_byzantine_grid_summary.csv`, i.e. the same file as Table 9 | none |
| Fig. 5 ledger | consistent — title text is computed from the same `res4` as Section 5.5 | none |
| Fig. 6 scalability | regenerated from `extC_*.csv`, the same files as Table 12 | none |
| Fig. 7 city replay | consistent with Section 5.7 | none |
| Fig. 8 scenario timeline | consistent with Section 5.8 | none |

Rule going forward: no figure contains a hand-typed number. Figures 2–8 are drawn by the experiment
scripts; Figure 1 is drawn from `paper_facts.json`. Re-running the experiments regenerates all of them.

## G. Author block
Updated to match the author's other MDPI submissions:
*Department of Information Technology, Research Center of Information Technology for the Future,
Faculty of Informatics, Mahasarakham University, Mahasarakham 44150, Thailand; thawatchai.c@msu.ac.th.*
A yellow note marks where a co-author would be inserted if one is added.

## H. Five references by the author, each placed where it is actually used
* [24] He, Chomsiri, Nanda & Tan, *Future Gener. Comput. Syst.* 2014 — cited in §2.1 and §3.3 (anomaly-free
  perimeter structure) and §6.2 (deployment context).
* [25] Chomsiri, He, Nanda & Tan, *IEEE Trans. Cloud Comput.* 2020 — §2.1 (cloud-scale throughput of the
  district filter) and §6.2.
* [26] Chomsiri, He, Nanda & Tan, TrustCom 2014 — §2.1 (stateful variant for connection-oriented traffic), §6.2.
* [27] Chomsiri & Pornavalai, SAM'06 — §2.1 and §3.3 (rule-set anomalies: shadowing/correlation).
* [28] Chomsiri & Kongsup, SCIS&ISIS 2018 — §3.2, justifying why a lightweight PoA consensus is preferred to
  stake- or work-based schemes for a small, known set of city agencies.

They are cited in context rather than listed decoratively; if a reviewer objects to any of them, [26] and [28]
are the two that can be dropped without leaving a gap in the argument.

---

# v07 (manuscript) — authorship, reference set rebuilt to 35

## I. Authorship
Two authors, in the order and with the affiliations used in the team's JAIT paper:
1. **Suwichai Phunsa** — Department of Creative Media, Digital Contents for Development Research Unit,
   Faculty of Informatics, Mahasarakham University, Mahasarakham 44150, Thailand; suwichai.p@msu.ac.th
2. **Thawatchai Chomsiri** *(corresponding author)* — Department of Information Technology, Research Center
   of Information Technology for the Future, Faculty of Informatics, Mahasarakham University,
   Mahasarakham 44150, Thailand; thawatchai.c@msu.ac.th

Author Contributions, Conflicts of Interest and the cover letter were rewritten for two authors.

## J. References: 28 → 35, renumbered in order of first appearance
* **Added** Phunsa & Chomsiri, *J. Adv. Inf. Technol.* 2026, 17, 477–487 (LSGELU) as **[6]**, cited in the
  Introduction (small networks are sensitive to design choices as fine-grained as the activation function)
  and again in §4.3, where it justifies keeping the default activation so that the comparison is about
  aggregation and not architecture.
* **Removed** Chomsiri & Pornavalai, SAM'06, as requested; the anomaly-characterisation point it supported is
  now carried by [3] (Tree-Rule firewall), which makes the same argument in a peer-reviewed journal.
* **Added seven** works that the text actually needs: Sarhan et al. NetFlow feature standardisation [23];
  Li et al. FedProx [26]; Nguyen et al. DÏoT federated IoT anomaly detection [27]; Fang et al. local model
  poisoning against Byzantine-robust FL [31]; Bagdasaryan et al. backdoor FL [32]; Bonawitz et al. secure
  aggregation [33]; Zhu et al. deep leakage from gradients [34]. The last four strengthen §2.2 and §6.5,
  where reviewers most often ask "which attack model?" and "what about weight leakage?".
* **Renumbered** the whole list so that the numbers now appear in strictly ascending order through the text
  (verified programmatically: first-appearance order = 1, 2, 3, …, 35), which is MDPI's requirement.

## K. Placement of the authors' own work
The five self-citations are **[3], [4], [5], [6], [7]** — an early, contiguous block, as requested. This is a
by-product of citing them where they genuinely belong: the second paragraph of the Introduction now states
the three premises of the architecture (auditable perimeter structure [3–5], compact edge learner [6],
consensus for a small known set of agencies [7]) before the paper turns to the literature it builds on.
They are cited again later in §2.1, §3.2, §3.3 and §6.2, so they are load-bearing rather than decorative.

---

# v08 (manuscript) — submitting author, two swapped self-citations, 43 references

## L. Cover letter
Now written and signed by **Suwichai Phunsa** (first author, submitting author), with
Thawatchai Chomsiri named in the letter as corresponding author. Affiliation lines corrected to the
Department of Creative Media, Digital Contents for Development Research Unit.

## M. Two self-citations swapped — SUPERSEDED by v09, see section P below
Google Scholar blocks automated access, so the two `citation_for_view` links could not be opened
programmatically. Based on the two works being replaced and on the author's DBLP/Scholar record, the
following were used — **if either is not the intended paper, tell me the title and I will swap it in one step**:

| Removed | Inserted | Why it fits the sentence |
|---|---|---|
| Chomsiri, He, Nanda & Tan, *A stateful mechanism for the Tree-Rule firewall*, TrustCom 2014 | **[5] Chomsiri, He & Nanda, *Limitation of listed-rule firewall and the design of tree-rule firewall*, IDCS 2012, LNCS 7646, 275–287** | the sentence in §2.1 is about *why* the tree-rule design exists (removing listed-rule anomalies), which is exactly this paper's argument; §3.3 and §6.2 keep citing it |
| Chomsiri & Kongsup, *P Coin*, SCIS&ISIS 2018 | **[7] Phunsa, Noiumkar & Chomsiri, *Survey and analysis of NFT and blockchain technologies for developing agricultural product trading systems*, JCSSE 2023, 145–149** | it supports the same point (open, token-driven chains are a different design point from a permissioned city ledger) and is co-authored by the submitting author |

The two sentences that used the removed papers were rewritten, not merely re-numbered:
§2.1 now reads "…anomalies whose removal motivated the tree-rule design [5], which was then shown to improve
security in cloud networks [3] and to sustain high-speed transmission in hybrid form [4]", and §3.2 now
contrasts PoA with PBFT [40,41] and with token-driven networks [7].

## N. References: 35 → 43
Added, each cited where the argument needs it: FLTrust [33] and FLAME [34] (competing FL defences, §2.2);
blockchained on-device FL [38] and blockchain + FL for industrial IoT [39] (§2.3, the pattern our L2'+L3
follows); PBFT [40] and the PBFT-vs-PoA CAP analysis [41] (§3.2, justifying the consensus choice);
Merkle [42] (§3.2, the proof mechanism we actually use); Dwork & Roth [43] (§6.5, differential privacy).

Verified programmatically after the rebuild: all 43 entries are cited in the body, and their first
appearances run 1, 2, 3, …, 43 in ascending order, as MDPI requires.

## O. Placement of the authors' own work
The five self-citations remain an early block — **[3], [4], [5], [6], [7]** — introduced in the second
paragraph of the Introduction, then reused in §2.1 (perimeter structure), §3.2 (consensus), §3.3 (layer
rationale), §4.3 (activation choice) and §6.2 (deployment context). Nothing else in the paper was moved to
achieve this; the block is early because those five papers state the premises the architecture starts from.


---

# v09 (manuscript) — the two self-citations the author actually meant

## P. Corrected swap
v08 used two guesses because Google Scholar blocks automated access. The author has now supplied the exact
titles, and they are in:

| v08 (my guess, removed) | v09 (correct) |
|---|---|
| Chomsiri, He & Nanda, *Limitation of listed-rule firewall…*, IDCS 2012 | **[5] Utta, P.; Saibut, B.; Chomsiri, T. Enhancing security of QUIC protocol and IoT. ECTI DAMT & NCON 2026, 546–551.** |
| Phunsa, Noiumkar & Chomsiri, *Survey and analysis of NFT and blockchain technologies…*, JCSSE 2023 | **[7] Saichua, P.; Khunthi, S.; Chomsiri, T. Design of blockchain lottery for Thai government. ECTI DAMT-NCON 2019, 9–12.** |

## Q. The sentences were rewritten, not re-numbered
Both new papers say something different from what they replace, so every citing passage was rewritten to
match — and, usefully, both now carry more weight in the argument than the papers they replace:

* **[5] QUIC and IoT** is now the paper's answer to an obvious reviewer question: *why metadata features?*
  - Introduction: city traffic increasingly rides encrypted transports, which leaves an auditor with flow
    metadata rather than payload — the premise of the whole L2 design.
  - §2.1: as IoT services migrate to QUIC, payload inspection stops being an option and the residual
    questions move to the transport and to flow behaviour.
  - §4.2 (feature schema): every feature is computed from flow metadata rather than payload, so the schema
    survives that migration. This is a genuine strengthening: the bias-aware, payload-free schema now has a
    stated motivation instead of being merely a modelling choice.
* **[7] Blockchain lottery for Thai government** replaces the "open token-driven network" contrast with a
  closer analogue: a public-sector ledger whose participants are known and accountable.
  - Introduction: the city-agency ledger is closer to such a deployment than to an open network.
  - §3.2: it makes the same trade — accountability over open participation — that justifies Proof-of-Authority
    against PBFT [40,41].
  - §6.2: it is precedent for public-sector ledgers in Thailand, which supports the illustrative mapping.

The other three self-citations are unchanged: [3] tree-rule firewall for cloud networks (FGCS 2014),
[4] hybrid tree-rule firewall (IEEE TCC 2020), [6] LSGELU (JAIT 2026).

## R. Counts re-verified after the swap
43 references, all cited in the body, first appearances in strictly ascending order 1…43 (checked
programmatically). The authors' own works remain the early block [3], [4], [5], [6], [7].

---

# v10 (manuscript) — MDPI compliance pass

## S. Requested changes
1. **Cover letter**: dated 21 August 2026; the yellow "suggest 3–5 reviewers" placeholder removed.
2. **Funding**: "This research project was financially supported by Mahasarakham University."
3. **Data Availability**: now points to https://github.com/thawatchai2799/SecurityArchitectureSmartCityIoT
   (also filled into §4.4, which previously carried a `[GitHub URL]` placeholder).
4. **Author Contributions / Conflicts of Interest**: replaced with the text supplied by the authors
   (CRediT roles shared by S.P. and T.C., US spelling "Conceptualization" as in the MDPI template).
5. **Abstract**: cut from 452 to **199 words** — MDPI's limit is 200, one paragraph, no citations and no
   undefined abbreviations, so "Internet of Things (IoT)" and "LPRA" are now defined on first use inside the
   abstract and every bracketed reference was removed from it.
6. **Figure 1** redrawn at 12.5 × 9.2 in (was 12.5 × 7.4) with larger type in every box, and displayed
   410 pt high in the document (was 330 pt).

## T. MDPI layout rule checked and applied (item 7)
Per the MDPI author layout guide, **table captions are placed above the table** and figure captions below the
figure. The draft had all 14 table captions below their tables; the generator now emits them above. Figure
captions were already correct (below). Verified in the rendered PDF.

## U. Cross-reference audit (item 8)
Checked programmatically on the rendered text, after the rebuild:
* Figures 1–8: all eight are cited in the body; captions are numbered 1–8 with no gaps.
* Tables 1–14: all fourteen are cited. **Table 14 was not cited anywhere** — Section 5.10 consisted only of a
  yellow placeholder — so a lead sentence was added that introduces the emulation-versus-Fabric comparison.
* References 1–43: all cited, and first appearances run in strictly ascending order 1 … 43.

## V. Small fixes found in the sweep (item 9)
* `[GitHub URL]` placeholder in §4.4 (Implementation) — filled with the real repository.
* "Maha Sarakham" vs "Mahasarakham" — unified to **Mahasarakham**, matching the affiliation line and the
  authors' other papers (the §6.2 mapping example now reads "Mahasarakham municipality").
* Two abstract clauses that repeated Section 1 verbatim were rewritten while shortening, so the abstract is a
  summary rather than a copy of the opening paragraph.
* Checked and clean: no double spaces, no space before punctuation, no stray bracketed text other than the
  three known yellow items, British spelling used consistently in the body (the CRediT statement keeps the
  MDPI template's US spelling).

## W. Remaining yellow items (all waiting on experiments or the authors)
`tab_native_extra` and `tab_cross_dirfree` (Tables 2 and 13 — need the three extra datasets),
Section 5.10 + Table 14 (Fabric run), the one-sentence cross-dataset summaries in §6.4 and §7,
and the Thai city names in §6.2 to be confirmed.

---

# v11 (manuscript) — every number is now from the authors' machine

## X. Provenance
All results were re-run on the authors' hardware and the manuscript regenerated from them:
**Windows 11, Intel i5-1140G7-class CPU, 8 logical cores, Python 3.12.8, 21 August 2026, 15:36.**
The banner on page 1 and Section 4.3 now state this machine. The previous build's numbers (Linux, 1 vCPU)
have been discarded.

## Y. What changed relative to the authoring machine
Detection quality was reproduced almost exactly — decision tree F1 0.9970 ± 0.0002, FPR 0.0093 ± 0.0003,
FedAvg 0.9708 ± 0.0006 against local-only 0.9517 ± 0.0024 and centralised 0.9944 ± 0.0004, unseen-attack
recall ≥ 0.91 for 8 of 9 families, tree with 107 leaves whose largest attack leaf covers 85% of attack flows.
Machine-dependent figures differ as expected: per-flow latency 78 ± 7 µs (was 51 ± 3), city replay
9.0 × 10³ flows/s, ledger 5.8 × 10⁴ tx/s.

Three results came out *stronger* on the authors' machine and the text now reflects them:
* noise poisoning drives plain FedAvg down to **0.686** (was 0.748), widening the gap LPRA closes;
* the γ sweep at K = 20 now shows γ = 8 cutting honest rejections from 80 to **26** while raising F1 to
  **0.970**, which makes the "relax both thresholds as heterogeneity grows" argument concrete;
* LPRA caught the noise attacker in 15/15 rounds (was 15/15) and the scaling attacker in 15/15, with
  **0 false quarantines** in the 75 district-rounds of the control.

## Z. Supplementary Table S2 (perimeter firewall) — result obtained, and it is a negative one
With the Internet Firewall Data Set in place, the perimeter task reaches F1 = 0.999 **both with and without
port features** (difference 0.0 points). The supplement now states plainly why: a blocked flow receives no
reply, so "Bytes Received" and "pkts_received" are zero and the action is almost a deterministic function of
the firewall's own counters. S2 is therefore presented as a sanity check, with an explicit note that
replicating a firewall's decisions from its own accounting is not intrusion detection — the behavioural
question is the one Sections 5.1–5.8 answer. Reporting this honestly is safer than letting a reviewer
discover a 0.999 that means nothing.

## AA. A real bug the authors' run exposed
`run_extended.py` built the validator-scaling ledger without enrolling the gateway that submits to it, so
part C died with `PermissionError: Gateway-T is not an enrolled member` after the district and γ sweeps.
This was a leftover from the v05 enrolment-list change (blockchain.py and city_simulation.py had been fixed,
this call site had not). Fixed in the shipped code; part C now completes end to end in ~65 s.

## AB. Still outstanding
Table 2 and Table 13 (the three extra datasets) and Section 5.10 / Table 14 (Hyperledger Fabric).
Everything else in the manuscript is now filled from measured results.

---

# v12 (manuscript) — cross-dataset results in; only Fabric is still open

## AC. E12 completed on three datasets
The authors added CIC-IDS2017 (300,000 flows, 89 native features) and UNSW-NB15 (200,000 flows from the raw
four-file release, 97 features after one-hot encoding) to TON_IoT. CICIoT2023 was skipped; the direction-free
view exists for it whenever it is added later. `tools/make_unsw_from_raw.py` was written for this run because
the authors held the *raw* UNSW-NB15 release (49 columns, no header) rather than the training-set CSV: it
assigns the official column names, drops the identifier and timestamp columns, and normalises `attack_cat`.

## AD. The result is the paper's strongest finding
Each dataset is individually easy — F1 0.986 (CIC-IDS2017) and 0.972 (UNSW-NB15) in the native view — yet
transfer collapses. On the nine directional features the mean diagonal is **0.96** and the mean off-diagonal
**0.12**, with two of six transfers at essentially **0.00**; the best transfer in the matrix is TON_IoT →
CIC-IDS2017 at 0.34. The direction-free view recovers part of it (mean off-diagonal 0.22, UNSW-NB15 → TON_IoT
0.47), which supports the reading that directionality conventions and base rates (attack share 76% / 19% / 13%)
drive much of the failure. Section 5.9 was rewritten around this, and the finding now appears in the abstract,
in §6.4 and in the conclusions: a vendor's detector cannot be trusted on a different district without local
evidence, which is precisely the argument for the federated layer and for anchoring the model's provenance.

New in the manuscript: **Table 13a** (nine directional features), **Table 13b** (four direction-free features),
**Figure 9** (heat map), and **Table 2** now filled with per-dataset row counts, feature counts and best-model
results. Supplementary Table S3 and Figure S1 are likewise filled.

## AE. Housekeeping
Abstract re-trimmed to **200 words** after the transfer sentence was added. All figures (1–9) and tables
(1–14, including 13a/13b) are cited in the text; references 1–43 all cited, first appearances ascending.
No yellow placeholders remain anywhere in the manuscript except Section 5.10 and Table 14 (Hyperledger Fabric).

---

# v13 (manuscript) — E13 measured on real Hyperledger Fabric; no placeholders remain

## AF. What was run
Hyperledger Fabric **v2.5.9** (fabric-ca 1.5.17) test network, two organisations, Raft ordering, majority
endorsement, on the authors' laptop under WSL 2. The CityAnchor chaincode was deployed in
**chaincode-as-a-service** mode and driven with the Fabric Gateway SDK (`fabric/bench/bench.mjs`),
2,000 anchored alerts per run.

| Setting | tx/s | mean | p50 | p95 | p99 | ledger |
|---|---|---|---|---|---|---|
| Emulated ledger, 5 validators | 56,940 | 1.4 ms | — | — | — | 2.5 MB / 10k |
| Fabric, concurrency 20 | 146 | 136 ms | 126 ms | 216 ms | 338 ms | 60.8 MB / 10k |
| Fabric, concurrency 50 | 134 | 278 ms | 263 ms | 375 ms | 466 ms | 60.8 MB / 10k |

Block cutting: 10 messages or 2 s, preferred block 512 KB (test-network defaults). Ledger data measured
with `du -sb` after 4,001 anchored alerts.

## AG. Why this matters more than the numbers themselves
Throughput is flat between concurrency 20 and 50 while latency doubles — the classic signature of a
saturated pipeline — so Section 5.10 now states plainly that the ordering service, not our code, is the
binding constraint, and that Fabric is ~369× slower than the in-process emulation. That is written as a
correction to Section 5.5 rather than as a footnote: the emulation's 5.7 × 10⁴ tx/s compares *design
choices* (validator count, block size) and must not be read as a deployment figure. The architecture's
feasibility is unaffected — a city SOC at tens of alerts per second uses a fraction of 146 tx/s, and a p99
of 338 ms is invisible next to the 20 s the cloud layer needs to declare a campaign.

## AH. A deployment obstacle worth reporting
`peer lifecycle chaincode install` failed with `docker image build failed: write unix @->/run/docker.sock:
write: broken pipe` on Docker Engine 29.5.3: the peer's built-in image builder uses a legacy Docker build
path that current engines no longer serve. Chaincode-as-a-service avoids it entirely (the operator's own
daemon builds the image). `fabric/chaincode/Dockerfile` and the `docker:start` script were added for this,
and `fabric/README.md` documents the failure and the fix — it will save any reader on a modern Docker the
same hour.

## AI. Propagated through the manuscript
Abstract (now 197 words) quotes the Fabric figure instead of the emulation; §4.4 records the Fabric version
and deployment mode; §6.1 (RQ3) answers with the measured latency; §6.3 recomputes the storage cost model
(≈190 GB per peer per year at 10 alerts/s); §6.5 reframes the emulation limitation; the conclusions cite the
Fabric result and the future-work sentence now reads "from two organisations on one host to five agencies
across sites".

**No yellow placeholders remain anywhere in the manuscript, supplement or cover letter.** All 9 figures and
all 15 tables (1–14, with 13a/13b) are cited; references 1–43 all cited in ascending order of first
appearance.

# v25 (manuscript) — pre-submission wording pass

## CB. "caught" → "quarantined", four places, not three
The pass was requested for three remaining uses of catch/caught; a scripted scan of the built v24 found
four. All are now "quarantined", matching the terminology the paper itself defines: (i) §5.3 "the flipping
attacker was quarantined by the direction test"; (ii) the Table 7 caption now reads "false quarantines
instead of rounds quarantined" (the data rows' last column is headed "Rounds quarantined (LPRA)", so the
caption now names the same quantity); (iii) §5.6 "the quarantine rate is only half the story"; (iv) §5.6
"with all attackers still quarantined" — the fourth occurrence, in the γ-sweep sentence, which the request
had not listed. No other wording in those sentences changed.

## CC. Table 16: F1 on a day with no positives is undefined, not zero
Monday of CIC-IDS2017 contains no attack flows (attack share 0.0000), so F1 = 0.0000 in that row reported
an undefined quantity as a score. The F1 and recall cells now show an em dash, and the caption gains one
sentence: "F1 and recall are undefined on a day with no attack flows — Monday's attack share is zero — and
are shown as —." Implemented in make_facts.py as a condition on attack_ratio == 0 (tab_temporal), not as a
hard-coded cell, so a future re-run with a different split renders itself correctly. The FPR cell (0.0020)
is unchanged — FPR is defined on that day.

## CD. §5.5 vs §5.6 ledger throughput: two experiments, now labelled as such
§5.5 (E8) reports 4.8 × 10⁴ tx/s at 5 validators from a 10,000-transaction run; §5.6 (E9) reports
5.9–6.4 × 10⁴ tx/s at 3–15 validators from separate 5,000-transaction runs. The numbers looked
contradictory because the sentence in §5.6 did not say the runs differ. It now does: "— E9 measures a
separate 5,000-transaction run per configuration, smaller than E8's 10,000-transaction benchmark of
Section 5.5, so the two rates are not directly comparable —". The 10,000 is rendered from the existing
led_n_tx fact; 5,000 was already literal in that sentence.

## CE. MLP training time: 15 s is one measurement, not the only one
§5.1's "costs 15 s of training" (mlp_train_s, from the E1 benchmark's train_time_s) coexists with a second,
independently measured fit time recorded by the E15 resource profiler (train_cpu_s in exp16_resources.csv;
Table 18 itself prints no training-time column). The sentence now says which measurement it is quoting:
"(one wall-clock fit in the E1 benchmark; the E15 profiling run re-fits the same model and records its own,
slightly different wall time — single-run timings vary between runs, cf. Section 5.4)". No new number is
printed, consistent with §5.4's existing statement that single-run timings should be compared within one
run. If the profiler's figure should instead be surfaced in Table 18, that is a separate change to
tab_resources and was not made here.

## CF. How this build was produced, honestly
The uploaded working copy contained an empty results/ directory, so make_paper.js could not be re-run here.
Paper_Draft_SmartCities_v25.docx was therefore produced by applying the identical seven string edits
directly to the v24 document.xml (all other package parts byte-identical), and the same edits were made in
make_paper.js / make_facts.py so that the next real build reproduces this text. A scripted diff of the
extracted text confirms exactly seven changed regions and zero remaining catch/caught; running
`node paper_src/make_paper.js` on a machine with results/ populated and diffing against this file is the
proper closing check, and tools/check_wording_v25.py automates the wording half of it.

## CG. update_partR.zip was inspected and not applied — confirmed stale from the chat transcript
Its poc/{byzantine,resources,robust_fl,temporal}.py are byte-identical to the repo's. Its run_advanced.py
differs only in the printed experiment labels (E15/E16/E17 instead of E14/E15/E16) — every one of the 24
changed lines is a label or help string; output filenames are identical. The chat transcript settles its
provenance: the zip was produced in the v20 era to fix run_advanced.py's --sample default so that the
resource profiling runs on the full 211,043-row dataset (DecisionTree 17.7 KB instead of the 13.19 KB a
60k sample gives). That substantive fix is already in the current repo. The labels it carries predate the
v23 renumbering, in which reviewer 1 caught the E13 → E15 gap in Table 3 and temporal/edge-cost/adaptive
were renumbered E14/E15/E16 across the manuscript, supplement, README and the runner's help. Applying
update_partR.zip today would therefore revert that reviewer-driven fix while adding nothing. Discarded.

## CH. Headers and footers are now copied verbatim from the template, not rebuilt
Loading styles.xml never carried the template's headers and footers (CA), and rebuilding them by hand
missed two parts that only a page-by-page comparison against smartcities-template.dot revealed: the
first-page header is not empty — it is a three-cell table carrying the journal logo on the left and the
MDPI logo on the right (header3.xml with two PNGs) — and pages 2+ carry a footer with the DOI right-aligned
(footer1.xml), in addition to the running head. The fix abandons reconstruction entirely:
paper_src/apply_template_headers.js now copies all five header/footer parts byte-for-byte out of
paper_src/template/smartcities-template.dot into the built document (logo media renamed tpl_logo_*.png so
they can never collide with figure media; header3.xml.rels retargeted accordingly — the only non-verbatim
part, and it is pure metadata), rewrites the sectPr references to the template's mapping (even/default/
first headers, default/first footers, titlePg, pgSz with the template's w:code="9"), and fixes the
relationships and content types. make_paper.js calls it after writing the file, so "วางไฟล์ template ทับ
แล้ว build ใหม่" now also covers headers and footers. Verified by rendering all 26 pages: page 1 shows the
logo header and the ruled journal-line/DOI footer with no running head; pages 2–26 each show the ruled
running head with the correct "N of 26" field and the DOI footer; continuous line numbering is unaffected;
body text is byte-identical to the wording-pass build (tools/check_wording_v25.py passes). Requires jszip,
which the docx package already depends on (npm i jszip if resolution ever fails).

# v26 (manuscript) — copy-editing pass: 9 confirmed small errors

## CI. Scope of this pass and what was deliberately left alone
The request was for 50 small errors. After several independent passes — straight vs curly quotes, hyphen
vs en dash in numeric ranges, a hunspell run over the extracted text, capitalisation consistency (Byzantine,
e-Government/e-government, non-IID, TON_IoT), cross-reference completeness (Sections 5.1–5.12, Tables 1–18,
Figures 1–10 all present and referenced), unit and citation-bracket formatting, and the 43-entry reference
list — the confirmed, genuinely-wrong, safe-to-fix count is 9, not 50. Several plausible-looking candidates
were checked and are *not* errors, so they were left alone rather than "fixed" into something worse:
"ToN_IoT" (ref. 14) vs "TON-IoT" (ref. 11) are each the source paper's own spelling, not interchangeable;
"vs" (no period, inside Table 3's compact protocol cells) vs "vs." (period, in body prose and captions) is a
consistent, deliberate split, not drift; British spelling (organisation, personalised, centralised,
generalise) is used consistently throughout and would be wrong to Americanise; e-Government (capitalised,
the proper name of one of the five districts) vs e-government (lowercase, the generic noun) is consistent
in every one of its five occurrences. Turning any of these into "fixes" would have violated the standing
instruction not to change something correct into something wrong, so they were not touched.

## CJ. The 9 fixes
Straight quotes to curly, matching the paper's dominant convention (four curly-quoted phrases already in the
text, e.g. "a little is enough"): the Algorithm 1 note "I do not know" (§3.4), "source" in the cross-dataset
discussion (§5.9), "what was deployed on Friday" (§5.11), and the single-quoted 'scale' in the Figure 7
caption (also switched from single to double quotes to match the convention — the paper never quotes a
single word in single quotes anywhere else).

Hyphen-minus to en dash in five numeric ranges, matching the paper's dominant convention (66 correct en-dash
ranges already present against these 5 stragglers): the scaled-attacker distance range "1.6–2.0" and the
flipping-attacker cosine range "0.80–0.90" in §5.3 (Table 7 discussion), the leave-one-family-out FPR range
"0.9–1.8%" in §5.4, and the E9 ledger-throughput range "5.9–6.4 × 10⁴ tx/s from 3–15 validators" in §5.6.

## CK. Fixed at the source, not just in the delivered file
The four quote fixes and the "scale" fix are literal text in paper_src/make_paper.js and were corrected
there directly. The five range fixes are *not* literal in make_paper.js — they are computed facts
(e4_scale_d_honest, e4_flip_cos_honest, loao_fpr_range, scal_val_range, scal_val_txs), so the real fix is in
paper_src/make_facts.py, in the five f-strings that format a (min, max) pair with `-` instead of `\u2013`.
Both files were corrected; the delivered v26.docx was produced by applying the same nine edits directly to
v25's document.xml (all other package parts byte-identical) since results/ is not populated here — the
proper closing check is the usual one: rebuild on the machine with results/, then run
`python tools/check_wording_v25.py`, which now also asserts these nine v26 edits and fails if any of the
five hyphen-minus ranges reappear.

# v27 (manuscript) — fixed a file-corruption bug reported by the user in Word

## CL. Root cause: duplicate Content_Types.xml Override entries
Opening Paper_Draft_SmartCities_v26.docx in Microsoft Word failed with "The file is corrupt and cannot be
opened." LibreOffice opened and rendered it (all 26 pages) without complaint, which is why the CH pass's
verification — rendering and checking every page — did not catch this: LibreOffice is lenient about a defect
Word correctly rejects. The defect: [Content_Types].xml carried **two** `<Override>` declarations for each
of /word/header1.xml, /word/header2.xml, /word/footer1.xml and /word/footer2.xml. OPC (the container format
docx is built on) requires exactly one Override per PartName; a duplicate is a malformed package.

The duplication came from paper_src/apply_template_headers.js (added in the CH pass). It strips the
document's own header/footer Content_Types entries with a regex anchored on `<Override PartName="...`
before adding the template's five entries. The "docx" npm library that builds the base document writes
attributes in the opposite order — `<Override ContentType="..." PartName="...">` — so the strip regex never
matched them, both the stale and the new Override for each of the four shared parts (header1/2, footer1/2)
were written, and the resulting duplicate-PartName file is exactly what Word calls corrupt. header3.xml was
unaffected because it is new (the template's logo header the base document never had one for).

This means **v25 and v26 as delivered carried the same defect** — they were never actually openable in Word,
only in LibreOffice, which is how the bug passed every check run so far.

## CM. Fix
paper_src/apply_template_headers.js: the strip regex now matches both attribute orders, and two integrity
assertions were added so this class of bug cannot ship silently again: (1) after stripping, if any
`PartName="/word/(header|footer)N.xml"` Override still matches, the script throws before writing the file;
(2) after all Overrides are assembled, every PartName in the finished Content_Types.xml is checked for
uniqueness and the script throws on any duplicate. A parallel check on word/_rels/document.xml.rels rejects
duplicate relationship Ids for the same reason.

Paper_Draft_SmartCities_v27.docx was rebuilt from the pre-header-application v25 (the wording-only build,
confirmed to have a clean, duplicate-free Content_Types.xml) by re-running the corrected
apply_template_headers.js, then reapplying the same nine v26 text edits (CJ) to the corrected file. Verified
before delivery, beyond the LibreOffice render that missed this class of bug last time: zero duplicate
Content_Types PartNames, zero duplicate relationship Ids, every relationship target exists in the package,
every XML part parses as well-formed XML, `unzip -t` and Python's `ZipFile.testzip()` report no errors, and
python-docx opens the file and reads all 19 tables. LibreOffice's 26-page render (header/footer text and
page numbering) still matches CH's original result. Content is otherwise byte-for-byte the same as v26 —
this version changes only the packaging defect, not the manuscript text.

**Recommended for MDPI submission**: v26 should be discarded and v27 used instead, since v26 cannot be
opened in Word.

# v28 (manuscript) — 4 confirmed reviewer findings, one of them a real ~10× error

## CN. E15/E16 script identifiers completed, matching E14
Table 3 read `E14 (run_advanced.py --part T)` but `E15 (--part R)` and `E16 (--part A)` — now
`E15 (run_advanced.py --part R)` and `E16 (run_advanced.py --part A)`, consistent across the row. Cosmetic,
but it's the difference between a reader tracing E15/E16 straight back to the repository and having to guess.

## CO. "on a real Hyperledger Fabric network" (§6.1) scoped to match §5.10
Changed to "on a deployed two-organisation Hyperledger Fabric v2.5.9 test network running on one host" — the
same description §5.10 and §6.5 already use. The old wording, read on its own in the RQ3 answer, could be
misread as a production or multi-site claim the paper doesn't make.

## CP. Section 6.3 storage figure was off by ~10x — a genuinely wrong hardcoded number
The cost-model sentence read "on Fabric the same anchoring costs ... 60.8 MB per 10,000 alerts, so a SOC at
10 alerts/s writes about 190 GB per peer per year." That arithmetic is wrong: 60.8 MB per 10,000 alerts is
~6,076 bytes/alert; at 10 alerts/s that is 6,076 x 10 x 3.15x10^7 seconds/year ~ 1.91 TB/year, not 190 GB.
190 GB is what 1 alert/s gives. This is exactly the class of error the project's own standing rule exists to
prevent (numbers that can be computed must be computed, never hand-typed) — checked, "190 GB" was a literal
string in paper_src/make_paper.js, not a fact pulled from paper_facts.json, so nothing in the pipeline could
have caught it. Fixed at the source: paper_src/make_facts.py now computes fab_gb_per_peer_year_1 and
fab_tb_per_peer_year_10 directly from the measured fab_ledger_bytes / fab_anchored (the same inputs
fab_mb_per_10k already uses), and make_paper.js quotes both facts, matching the style of the adjacent
emulated-ledger sentence ("~80 GB per validator per year (8 GB at 1 alert/s)"): "so a SOC at 10 alerts/s
writes about 1.91 TB per peer per year (191 GB at 1 alert/s)". With the current measurement (24,311,978
bytes over 4,001 alerts) this computes to 1.91 TB and 191 GB.

## CQ. Reviewer claims checked and found to already be addressed, or unfounded
Before making these four edits, three other claims from the same review round were checked against the
delivered file and are not issues:
- The PDF text-layer "glitch characters" (Ledger[?]Anchored etc.) reported again against the v27 PDF this
  assistant generated: re-verified with three independent extractors (pdftotext/poppler, pypdf, pdfplumber)
  plus a pdffonts check of the embedded font's ToUnicode mapping — zero occurrences of U+FFFE/U+FFFD in any
  of the three, and every compound hyphen (Ledger-Anchored, poisoning-resilient, two-organisation,
  time-to-detect) extracts as a plain ASCII hyphen in all three. Not reproducible in the delivered file.
- "Table 13's honest-district rejection should be qualified in the Conclusion" — already there verbatim:
  "...quarantined every evaluated 20% Byzantine attacker from 5 to 50 districts, at the cost of rejecting an
  increasing number of honest districts as heterogeneity grew."
- "The paper should explain why FLTrust/FLAME aren't used as baselines" — already a full paragraph in §3.4
  ("Relation to other defences"), giving the threat-model reason (no party entitled to hold a clean root
  dataset) and the auditability reason (a verdict that can't be reduced to a few numbers can't be written to
  a ledger transaction a district can contest).
These were left unchanged; re-writing already-correct text to satisfy a review that hadn't actually read
those sections would only add drift.

## CR. Verification before delivery
Same integrity suite the v27 corruption fix (CL–CM) introduced, run again on v28: zero duplicate
Content_Types PartNames, zero duplicate relationship Ids, every XML part well-formed, python-docx opens all
19 tables. A word-level diff against v27 shows exactly the four edits above and nothing else. LibreOffice
render confirms all 26 pages still carry the correct header/footer/DOI. tools/check_wording_v25.py extended
with a v28 section (present/forbidden phrase pairs for all four edits) and passes; it correctly fails on
v27, confirming it discriminates rather than trivially passing everything.

# v29 (manuscript) — 2 confirmed editorial fixes from the v28 review round

## CS. §6.3 closing sentence no longer contradicts its own paragraph
"These figures are for the emulation and should be recomputed from the Fabric measurements once available"
was stale: by v28 the same paragraph already reports Fabric-measured storage (1.91 TB / 191 GB, computed
from the real E13 byte counts, CP). The sentence read as if no Fabric data existed yet. Replaced with: "The
edge, federated-learning-traffic and cloud figures above are emulation-based estimates; the Fabric storage
and latency figures are the E13 measurements reported in Section 5.10 and should be used directly for
deployment sizing where applicable." This also answers the review's actual concern (which figures in the
paragraph to trust for sizing) instead of deferring it.

## CT. "measured detection energy" corrected to match the paper's own disclosed method
§5.12 already states energy is "obtained by scaling measured CPU time rather than by a wattmeter" (Table 18
note) and computed, not measured. One later sentence still said "the measured detection energy is small" —
now "the CPU-time-scaled detection-energy estimate is small", consistent with the method disclosed two
sentences earlier and in the table note.

## CU. Five other findings from the same review round checked and not changed
- "zero-day ransomware": every occurrence (Abstract, Table 3, §5.8, Figure 8, Conclusion) already reads
  "replayed zero-day ransomware" or is introduced with "simulated clock" in the same sentence; the term is
  also used in its standard security/ML sense (unseen by the detector), not "a live event". Left as is.
- "7 MB of traffic per year": the reviewer's own recomputation (9.2 KB x 2 x 365 ~ 6.7 MB) matches the
  printed "about 7 MB" — confirms the number is correct; no numeric change made.
- "31.9 MB... would move": already qualified in-sentence as "per training set", not per-round or annual.
- Algorithm 1 "rendering corruption": re-extracted the algorithm text directly from the delivered PDF with
  pdftotext; every symbol (∅, ∈, ⌊⌋, θ, γ, τ) is present and in the correct position — not reproducible.
- PDF hyphen glyphs (Ledger[?]Anchored etc.): re-checked a third time with three independent extractors
  (pdftotext, pypdf, pdfplumber) on the exact v28.pdf delivered — zero U+FFFE/U+FFFD in all three, every
  compound hyphen extracts clean. Still not reproducible against the delivered file after three rounds of
  independent testing; the reviewer was asked to confirm which copy and where.

## CV. Verification
Same integrity suite as v27/v28: zero duplicate Content_Types PartNames, zero duplicate relationship Ids,
all XML well-formed, python-docx opens all 19 tables, LibreOffice renders all 26 pages with correct
header/footer/DOI. Word-level diff against v28 shows exactly the two edits above. tools/check_wording_v25.py
extended with a v29 section and passes; fails correctly on v28.

# v30 (manuscript) — Figure 1, L3 panel: fixed real overlap and text-cutting arrow

## CW. What was actually wrong (confirmed by rendering, not guessed from coordinates)
The user reported the L3 sub-panels in Figure 1 "overlap and don't line up." Rendered fig_architecture()
from the actual source with the real published facts (17.7 KB, 78 us/flow, 92 KB/round, 31.9 MB -- all
already-verified numbers, not placeholders) and inspected the output at pixel level rather than trusting the
layout coordinates by eye. Found two distinct, real defects:
1. The block-rule box ("block = header * prev-hash * Merkle root * ...") and the row of five validator boxes
   below it had essentially zero vertical gap (0.03 of a 9.75-unit canvas) -- their borders touched, reading
   as one merged panel rather than two distinct rows.
2. The dashed green "weights only" arrow, drawn at a fixed x=5.30 from L2 up into L4, was drawn *on top of*
   every box it geometrically crosses at that x-position -- it sliced directly through "model-id" and
   "SHA-256(weights)" in the block-rule box, and through "Electric" in the "validator: Electric Utility" box.
   x=5.30 happens to sit almost exactly on that validator box's horizontal centre (5.325), which is why it
   consistently cut through box 3 of 5 and no other.

## CX. Fix
paper_src/make_figures.py, fig_architecture():
- box() and arrow() now take an explicit zorder (box defaults to 2, its text to 3, arrow defaults to 1).
- The block-rule box moved from y=5.55 to y=5.62, opening a real ~0.10-unit gap above the validator row
  while keeping ~0.29 units of clearance below the L3 title (checked by rendering -- an earlier attempt at
  y=5.67 closed that upper gap enough to create a new seam against the title's own background patch, so the
  smaller shift was kept instead of the larger one).
- The "weights only" arrow's zorder set to 1.5 -- between the band backgrounds (1) and the boxes (2), so it
  now renders *behind* the validator/rule boxes it crosses (occluded, exactly where it was cutting through
  text) while remaining visible in the two open gaps where its label already sits (L2-L3 and L3-L4). This
  also happens to match the architecture's own logic better: raw weights bypass the ledger and only their
  hash is anchored, so an arrow that visually "passes behind" the ledger layer rather than being drawn on
  top of it is arguably more correct, not just tidier.
No other figure in make_figures.py uses these two helpers' zorder in a way that this default change affects
adversely -- checked by rendering fig1 in full and comparing every panel (L1, L2, L4, the three adversary
boxes, all other arrows and labels) against the pre-fix render; nothing else moved or was newly occluded.

## CY. Applied to the manuscript, not just the standalone figure files
Paper_Draft_SmartCities_v30.docx was produced by swapping the embedded Figure 1 image
(word/media/6594ecc438bfd4bd841266971b2cb876a0585a5c.png) for the corrected render inside v29.docx, verified
pixel-dimension-identical (3477x2625) to the original so the drawing's fixed on-page extent needed no change
and there is no distortion. A word-level diff of the extracted body text confirms it is byte-identical to
v29 -- this version changes only the one image. figures_600dpi.zip's Figure01_architecture.png/.pdf were
replaced the same way; all other 9 figures in that archive are untouched.

## CZ. Verification
Same integrity suite as v27-v29: zero duplicate Content_Types PartNames, zero duplicate relationship Ids,
all XML well-formed, python-docx opens all 19 tables. Rendered page 5 of the actual v30 PDF (where Figure 1
sits) and visually confirmed against the manuscript context: the L3 panel now shows a clean, unambiguous gap
between the block-rule box and the five validator boxes, and the "weights only" arrow's label and dashed
line are visible only in the open gaps above and below L3, no longer overlapping any text.

# v31 (manuscript) — 4 scoping/precision edits, Abstract and Conclusion energy wording

## DA. Abstract and Conclusion: energy figure now explicitly flagged as CPU-time-scaled
Both the Abstract ("a depth-8 tree reached F1 = 0.997 at 17.7 KB and 0.19 J per million flows") and the
Conclusion ("Running it costs 0.19 J per million flows on a 3 W gateway") stated the energy figure bare. The
method (CPU-time scaled by a stated board power, not a wattmeter reading) was already disclosed in Table 18's
note and in the §5.12 prose, but a reader who only reads the Abstract or Conclusion would not see that
caveat. Both now read "...and a CPU-time-scaled estimate of 0.19 J per million flows" / "Running it costs a
CPU-time-scaled estimate of 0.19 J per million flows...". No number changed — see DB below for why none
needed to.

## DB. The kWh/year figures in Table 18 remain unchanged because they are correct
Two consecutive review rounds claimed Table 18's kWh/year column was wrong by roughly 1000x. Both claims were
checked against an independent recomputation of all four rows (not just the one row quoted) and the paper's
printed values (0.005, 0.002, 0.024, 0.009 kWh/year for LogReg/DT/RF/MLP) matched the correct computation to
2-3 significant figures in every row. Both review rounds' own arithmetic contained a 1000x unit-conversion
error of their own (round one divided by 3,600 instead of 3,600,000 J/kWh, i.e. computed Wh and labelled it
kWh; round two's stated intermediate energy figure did not match its own stated formula, off by the same
factor). Full working recorded in the reply to the reviewer; not repeated here since no source change
resulted from it.

## DC. Two scoping edits from the same review round, both reasonable and adopted
- E11 ransomware scenario: "the detector had never seen ransomware" -> "the detector had not been trained on
  the ransomware flows used in this replay" -- avoids an implicit claim about the train/test split that the
  sentence did not intend to make.
- Conclusion: "it quarantined every evaluated 20% Byzantine attacker from 5 to 50 districts" -> "...from 5 to
  50 districts under the evaluated scaling attack and tested partition settings" -- the original already
  scoped everything else in that sentence (F1 numbers, storage overhead, etc.) to what was measured; this
  brings the quarantine claim in line with the same standard, since it is not a guarantee against every
  attack type or district distribution (§6.5 already states this, but the Conclusion's phrasing on its own
  could be read as unqualified).

## DD. PDF glitch-character claim: fifth consecutive round, still not reproducible
Same claim repeated a fifth time, this time against v30. Not re-tested separately this round since the
underlying file (aside from these four wording edits) has not changed since the four independent tests
already on record (CU, CV, plus two prior rounds) — all negative across three extraction libraries. Noted
here for the record rather than repeated as a standalone check.

## DE. Verification
Same integrity suite as v27-v30: zero duplicate Content_Types PartNames, zero duplicate relationship Ids,
all XML well-formed, python-docx opens all 19 tables, LibreOffice renders all 26 pages with correct
header/footer/DOI, zero U+FFFE/U+FFFD in the rendered PDF's text layer. Word-level diff against v30 shows
exactly the four edits above. tools/check_wording_v25.py extended with a v31 section and passes; fails
correctly on v30.

# Repository audit (no manuscript version bump — source/README fixes only)

## DF. Full source-vs-manuscript audit, prompted by a direct request to verify the shipped repo
Requested: confirm every file in the delivered SecurityArchitectureSmartCityIoT.zip, including README.md,
actually reflects the fixes made across v25-v31. Rather than trust memory of what was applied when, every
REQUIRED_* / FORBIDDEN_* phrase check_wording_v25.py has accumulated (20 phrases across v25/v26/v28/v29/v31)
was parsed out of the tool with Python's `ast` module and checked against the literal contents of
make_paper.js and make_facts.py directly (not against a build, since results/ is not populated here). Found
one real gap and one unrelated stale number in README.md; both fixed.

## DG. Found: one v25 quote fix had reverted in make_paper.js
"a post-incident question about \"what was deployed on Friday\" answerable" (§5.11) was still straight-quoted
in the JS source, even though the *delivered* v25-v31 docx files have always had it correctly curly-quoted
(patched directly into each docx's document.xml at build time, which is how every version has been produced
throughout, since results/ was never populated here to run a real `node make_paper.js`). The other three
quote fixes from the same pass ("I do not know", "scale", "source") were present and correct — only this
one fragment slipped. Fixed directly in make_paper.js. This has no effect on any delivered docx (v25
through v31 all already have the curly quote, verified again for v31 specifically), but it matters for the
*next* real rebuild on a machine with populated results/: before this fix, that rebuild would have silently
reintroduced a straight quote the manuscript no longer has.

## DH. Found: README.md's Fabric slowdown figure was stale (400x), never updated after the 327x fix
README.md section 9 ("Reproducibility notes") stated the Fabric experiment is "roughly 400x slower" than the
emulated ledger. The manuscript's own figure — computed dynamically as fab_ratio_txs in make_facts.py, never
hand-typed — is 327x (see the original project brief's own account of a prior 369x-vs-327x bug). 400x was
never corrected because README.md sits outside the paper_src pipeline entirely; nothing regenerates it.
Fixed to 327x, with a note that the figure is computed and will track a real re-run rather than needing
another manual correction.

## DI. README.md updated to document the two tools added since v24
Neither `paper_src/apply_template_headers.js` (added in the CH pass, v25-era) nor `tools/check_wording_v25.py`
(added the same pass, extended through v31) were mentioned anywhere in README.md, even though both are now
load-bearing parts of the build: the former is called automatically by make_paper.js and will abort the
build on a malformed Content_Types.xml (the exact class of bug that made v26 unopenable in Word, CL-CM); the
latter is the documented "proper closing check" referenced by name in nine separate CHANGELOG entries but
never actually named in the README's own rebuild instructions. Added both to the rebuild command list and to
the repository layout section (7), and added `npm install docx jszip` in place of the old `npm install docx`
since apply_template_headers.js depends on jszip directly.

## DJ. Verification
Re-ran the full ast-based REQUIRED/FORBIDDEN phrase sweep against the corrected make_paper.js and
make_facts.py: every phrase from every version (v25 through v31) is now present, and zero forbidden/stale
phrases remain anywhere in either file. Confirmed separately that the already-delivered
Paper_Draft_SmartCities_v31.docx needs no changes — it already has the correct wording in every location;
this audit only affects what a *future* rebuild from source would produce. No new manuscript version was
issued for this; the fix is to the repository, not the article.
