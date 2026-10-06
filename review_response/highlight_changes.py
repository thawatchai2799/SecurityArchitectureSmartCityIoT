"""Shade every passage of revise-v32 that differs from the submitted manuscript, by source of the change.
Round 2: paragraph defaults are anchored to paragraph text (first 40 characters of the revise-v30 paragraph the
index referred to) instead of to indices, so inserted paragraphs no longer shift the map."""
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy, difflib, re, sys

G, P, Y, V, GR = 'C6EFCE', 'FFC7CE', 'FFEB9C', 'E4D0F5', 'D9D9D9'   # R1 green, R3 pink, R2 yellow, Editor purple, self grey

# ---- paragraph defaults (index in the list of non-empty paragraphs of v14)
DEF30 = { 1: P, 6: Y, 10: G, 12: P, 13: G, 15: G, 23: G, 25: G, 27: G, 30: P, 34: P, 38: G, 39: Y, 40: GR, 41: G,
       42: P, 50: G, 53: G, 54: Y, 60: GR, 61: P, 64: G, 68: V, 71: G, 72: G, 75: GR, 76: GR, 77: GR,
       78: G, 79: G, 80: GR, 84: GR, 89: P, 92: G, 93: G, 94: G, 95: GR, 96: G, 101: G, 104: GR, 105: G,
       106: G, 110: G, 119: G, 129: G, 136: GR, 138: G, 142: P, 143: P, 144: G, 145: G, 148: G,
       195: G, 196: G, 197: G, 198: G}
# ---- sentence-level overrides, applied in order; first match wins
# span-only overrides: only the matched text is recoloured; the rest of the sentence keeps its sentence colour
SPAN = [
    # Academic Editor (purple): values that moved when the experiments were re-run under the corrected code,
    # and the algorithm-implementation equivalence clause of Section 4.4
    (r'and the released screen_updates\(\) implements Algorithm 1 step for step[^;]*\(Supplementary Section S9\)|'
     r'0\.780 \(Gaussian-noise weights\)|0\.780|34\.1 against 1\.7–2\.0|cosine 0\.09 against 0\.79–0\.89|0\.950 ± 0\.036 \(scale\) and 0\.780 ± 0\.161 \(noise\)|'
     r'0\.920 \(flip\), 0\.926 \(scale\) and 0\.672 \(noise\)|0\.939–0\.941|about 0\.939 \(0\.939–0\.945\)|0\.9393|0\.607–0\.886|29/60|0\.950–0\.960 against FedAvg’s 0\.952–0\.971|'
     r'0\.00–0\.41% of test flows under LPRA and 0\.00–0\.47% under FedAvg|11/150 at 0\.4, 31/150 at 0\.6, 51/150 at 0\.8|0\.024 F1 with no attack \(0\.947 against 0\.971\)|'
     r'0\.887 when trained centrally|0\.365 centralised and 0\.363 federated|six of nine|0\.776 to 0\.412|0\.9708 ± 0\.0007 versus centralised 0\.9942 ± 0\.0003 and local-only 0\.9516 ± 0\.0024', V),
    # self-found corrections (grey): mistyped or missing statements, not re-run values
    (r'\(60k-flow sample; recall 0\.81 on the full data of Table 11\)|Supplementary Table S8|Table S8 the twelve[^;]*|tied with Trimmed Mean under noise|population s\.d\. over seeds|an estimated 0\.19|threshold sweep is reported separately \(Table S4\)|0\.01–0\.16|and against the colluding pair never both colluders in the same round', GR),
    # author-driven wording refinements prompted by informal pre-submission review (grey), revise-v26
    (r'the ledger’s guarantee ends at a validator-quorum collusion|Hyperledger Fabric test network|LPRA loses no F1 when no attack is present at five districts|loses no F1 when there is no attack at five districts', GR),   # revise-v30
    (r'scaling, label-flip, Gaussian-noise and stealth poisoning attacks|its aggregation guarantee assumes an honest majority of districts, and the ledger’s guarantee ends at a validator-quorum collusion|Two distinct majority assumptions therefore apply: LPRA \(L4\) assumes an honest majority of districts, whereas the ledger \(L3\) holds only while fewer than ⌈2N/3⌉ validators collude \(Section 5\.5\)|and the backdoor trial was inconclusive, so no backdoor resistance is claimed; LPRA assumes an honest majority of districts, the ledger’s guarantees end at a colluding validator quorum', GR),   # revise-v30
    (r'a majority cluster is only three districts|it is a majority-cluster decision that excludes legitimately different honest districts whether or not an attacker is present|at 20 and 50 districts FLAME’s majority cluster still discards about two fifths of the honest district-rounds, at a no-attack cost of 0\.033 and 0\.011 F1 against LPRA’s 0\.007 and zero|at five districts \(at 20 it costs 0\.007 F1, Section 5\.6\)|no F1 when no attack is present|no F1 when there is no attack|at five districts \(0\.007 F1 at 20 districts, Section 5\.6; |between the delta of client i and|; a comparison of design, not of measured performance', GR),   # revise-v30
    (r'at five districts, lost no F1 without an attack|, unlike them and(?= FLAME;)|although in Sections 5\.3 and 5\.6 that assignment never rejected an attacker at any district count tested|the comparison at K = 20 and 50 under the corrected partition is reported in Section 5\.6 and Table S11|extend the large-K FLAME comparison of Section 5\.6 beyond the scaling attack|and at five districts lost no F1 when no attack was present, unlike Median, Trimmed Mean, Krum, Multi-Krum and FLAME; at 20 and 50 districts FLAME’s no-attack cost shrinks to 0\.001–0\.002 F1 \(below LPRA’s own at 20\), but its clustering still rejected no attacker|removed them at 50 districts and cut them to at most 6 of 160 at 20 districts|within one between-seed standard deviation \(LPRA’s own\) of FedAvg’s|quarantined the scaled, flipped, noisy and sign-flipped attackers it was given in every round but one, held F1 within 0\.001 against the adaptive attacker at every strength and direction tested, quarantined the scaled attackers at every size from 5 to 50 districts and, at five districts,|\(Supplementary Table S3\) show|the submitted version’s Supplementary Table S4 sweep|removes the effect entirely at K = 50 and, at K = 20, reduces it to at most 6 of 160 honest district-rounds|manuscript’s numbers|S9, S10 and S11, are in review_response/|Table S11 FLAME at K = 20 and 50 under the Table 13 protocol; |The three-way trade-off is systematic, not incidental[^;]*(?:;[^;]*){0,20}?None of the three offers a formal confidentiality guarantee for the exchanged weights\.', GR),
    # round 2: sub-span colours inside sentences whose sentence-level colour belongs to another source
    (r'admits about ⌊K/2⌋ \+ 1 districts by construction of its clustering parameters and so|and under every attacker placement tried|and the attacker-placement study|FLAME, once its clustering is run as specified, excludes the same attackers but sits 0\.03 F1 below under the single-attacker attacks and level under the adaptive pair', G),
    (r'tested once its first version, which that same sweep had broken at f/K = 0\.4, was repaired|the best robust rule|Beyond one half|it was given at five districts in every round but one|degrades at 0\.44–0\.45 and inverts above one half \(Section 5\.6\)', P),
]
OVR = [
    # Academic Editor, sentence-level (purple)
    (r'regenerated under it|Undefended FedAvg under attack is also the least repeatable', V),
    # self-found corrections, sentence-level (grey)
    (r'60k-flow sample of the federated|the run uses the 60k-flow sample|scaled, flipped, noisy|is the path this paper offers', GR),
    # Reviewer 2 (yellow)
    (r'Generative AI|Claude Opus|GPT-5|MDPI’s policy', Y),
    # round 2: Reviewer 1 (green) before the older pink rules, for the FLAME re-implementation and the latency/initialisation corrections
    (r'0\.904|Algorithm 1 specifies|by construction of its clustering parameters|clustering the updates|flame_impl|Table S15|λ = 0\.01|first n_att district|manifest that maps|submission latency itself|Three things about the commit latency|turns Byzantine from the first|an insider compromised after enrolment|training split|104 of the 500|MANIFEST|script families|three kinds|least repeatable|block that contains it|saturated-mempool|twenty times faster|submission call|under every attacker placement|run as its Algorithm 1', G),
    # round 2: Reviewer 3 (pink)
    (r'patient adversary|validation-based|commitment-based|Byzantine fraction|f/K|inverts above|degrades at|decode_blockfile|Table S14|certificates|block file|extrapolat|i5-11300H|not deployment figures|Dong et al\.|vehicular|Table S13|Table S12|heterogeneity tax at five districts|ledger-writable decision', P),
    # Reviewer 3 (pink)
    (r'[Tt]rustworthy|Measured Limits|FLAME|E18|clustering|confidentialit|gradient-inversion|transport level|BPFL \[46\] provides|'
     r'validator-majority|⌈2N/3⌉|quorum|stealth|honest envelope|tamper|[Tt]runcat|E19|Table S10|height anchor|orchestrator that is malicious|'
     r'caveats belong|15–20 features|regularit|guarantee ends|guarantee’s|where each layer|most consequential|Fabric deployment from two', P),
    # Reviewer 1 (green)
    (r'FedChallenger|DT-BFL|BRFL|Section 2\.3|screen_updates|INCONCLUSIVE|equivalence|single district|district’s own|one district|pooled|'
     r'initialis|partition|orphan|owner|Table 13|honest rejections|Krum|non-selection|selection rule|resilience condition|n > 2f|sign-flip|E17|'
     r'developmental|c_min|joint|Table S4|leave-one-family|federated (MLP|model)|transfers? (worse|to an unseen)|delivery mechanism|'
     r'federation|E14|chronological|commit|submission time|0\.8 ms|provenance|silent|correctness|recomput|commitments|\[4[4-7]\]|'
     r'Table S5|Section S9|Table S7|review_response|v2\.1\.0|attributable|backdoor|specialis', G),
]
SENT = re.compile(r'[^.;]*[.;]?\s*')

def sentences(text):
    out = []; i = 0
    for m in re.finditer(r'.*?(?:[.;](?=\s|$)|$)', text, re.S):
        if m.end() == m.start(): break
        out.append((m.start(), m.end())); i = m.end()
        if i >= len(text): break
    return out

EXEMPT30 = {13, 25, 27, 38, 80, 95}   # contribution 2, Sections 2.3, 2.4, 3.4 main paragraph, FLAME paragraph, FLAME-at-large-K paragraph (S11): one source each

# ---- round 2: resolve the revise-v30 index maps to text anchors, then add/override for revise-v31
_v30 = [p.text for p in Document(S + 'out/smartcities-4547789_revise-v30_clean.docx').paragraphs if p.text.strip()]
DEF_PREFIX = {_v30[i][:40]: c for i, c in DEF30.items()}
EXEMPT_PREFIX = {_v30[i][:40] for i in EXEMPT30}
NEW_DEF = {                                            # revise-v31 paragraphs, by 40-character prefix
    'Stealth attack: construction, why it was': P,     # Reviewer 3, point 2
    'Which districts are Byzantine. Table 13 ': G,     # Reviewer 1, C3
    'Byzantine fraction at fixed K. Section 6': P,     # Reviewer 3, point 3
    '48. Dong, S.; Su, H.; Xia, Y.; Zhu, F.; ': P,     # Reviewer 3, point 1
    'FLAME [34] is added as a baseline (E18),': G,     # Reviewer 1, C2 (whole paragraph rewritten)
    'FLAME at larger district counts. Section': G,     # Reviewer 1, C2 (whole paragraph rewritten)
    'Table 15. Emulated ledger (Section 5.5) ': P,     # Reviewer 3, point 4
    'Table 15 reports 2,000 anchored alerts a': P,     # Reviewer 3, point 4
    'Table 8. Personalised FL: one local epoc': G,     # Reviewer 1, C4
    'Surveys of IoT in smart cities identify ': P,     # Reviewer 3, point 1 (T-ITS reference)
    'In E10, 20,000 held-out flows were repla': G,     # Reviewer 1, C1
    # revise-v32: Highlights section added at the Section Managing Editor's request (purple)
    'Highlights': V, 'What are the main findings?': V, 'What are the implications of the main fi': V,
    'On TON_IoT a depth-8 decision tree detec': V, 'LPRA, a screening rule whose accept/quar': V,
    'A city can run intrusion detection on a ': V, 'Ledger anchoring certifies provenance, n': V,
    'Class imbalance (MITM) affects multi-cla': G,   # Section 6.6 regeneration sentence (Reviewer 1, C5; revise-v31)
}
NEW_EXEMPT = {'Highlights', 'What are the main findings?', 'What are the implications of the main fi', 'On TON_IoT a depth-8 decision tree detec', 'LPRA, a screening rule whose accept/quar', 'A city can run intrusion detection on a ', 'Ledger anchoring certifies provenance, n',
              'Stealth attack: construction, why it was', 'Which districts are Byzantine. Table 13 ', 'Byzantine fraction at fixed K. Section 6',
              'FLAME [34] is added as a baseline (E18),', 'FLAME at larger district counts. Section'}
SPAN_SKIP = {'Highlights', 'What are the main findings?', 'What are the implications of the main fi', 'On TON_IoT a depth-8 decision tree detec',
             'LPRA, a screening rule whose accept/quar', 'A city can run intrusion detection on a ', 'Ledger anchoring certifies provenance, n'}
def resolve(vp):
    DEF = {}; EXEMPT = set()
    for j, p in enumerate(vp):
        k = p.text[:40]
        if k in DEF_PREFIX: DEF[j] = DEF_PREFIX[k]
        if k in NEW_DEF: DEF[j] = NEW_DEF[k]
        if k in EXEMPT_PREFIX or k in NEW_EXEMPT: EXEMPT.add(j)
    return DEF, EXEMPT

def colour_for(sentence, default, exempt=False):
    if exempt: return default
    for rx, col in OVR:
        if re.search(rx, sentence): return col
    return default

def shade_run(run, fill):
    rPr = run._r.get_or_add_rPr()
    for old in rPr.findall(qn('w:shd')): rPr.remove(old)
    shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill)
    rPr.append(shd)

def apply_ranges(par, ranges):
    """ranges: list of (start,end,fill) in paragraph-text coordinates; splits runs as needed."""
    if not ranges: return
    bounds = sorted({b for s, e, _ in ranges for b in (s, e)})
    # split runs at bounds
    pos = 0
    for r in list(par.runs):
        text = r.text; start, end = pos, pos + len(text); pos = end
        cuts = [b for b in bounds if start < b < end]
        if not cuts: continue
        pieces = []; last = 0
        for b in cuts: pieces.append(text[last:b - start]); last = b - start
        pieces.append(text[last:])
        r.text = pieces[0]; prev = r._r
        for piece in pieces[1:]:
            new = copy.deepcopy(r._r)
            for t in new.findall(qn('w:t')): new.remove(t)
            t = OxmlElement('w:t'); t.text = piece; t.set(qn('xml:space'), 'preserve'); new.append(t)
            prev.addnext(new); prev = new
    # shade
    pos = 0
    for r in par.runs:
        s, e = pos, pos + len(r.text); pos = e
        if e == s: continue
        for rs, re_, fill in ranges:
            if s >= rs and e <= re_: shade_run(r, fill); break

def changed_ranges(old, new):
    """word-level diff -> char ranges in new that are inserted/replaced"""
    a = re.findall(r'\S+|\s+', old); b = re.findall(r'\S+|\s+', new)
    pos = [0]
    for tok in b: pos.append(pos[-1] + len(tok))
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ('insert', 'replace') and j2 > j1: out.append((pos[j1], pos[j2]))
    return out

def colour_paragraph(par, old_text, default, exempt=False):
    new = par.text
    ch = changed_ranges(old_text, new) if old_text is not None else [(0, len(new))]
    if not ch: return
    ranges = []
    for ss, se in sentences(new):
        if any(cs < se and ce > ss for cs, ce in ch):
            col = colour_for(new[ss:se], default, exempt)
            # shade only the changed sub-spans inside this sentence
            for cs, ce in ch:
                lo, hi = max(cs, ss), min(ce, se)
                if lo < hi:
                    # extend to whole words already (tokens); keep
                    ranges.append((lo, hi, col))
    # span-only overrides carve sub-ranges out of the sentence-level ranges
    for rx, col in (SPAN if new[:40] not in SPAN_SKIP else []):   # v32: whole-paragraph insertions keep one colour
        for m in re.finditer(rx, new):
            # recolour only the parts of the match that actually changed
            for cs, ce in ch:
                lo, hi = max(m.start(), cs), min(m.end(), ce)
                if lo >= hi: continue
                nr = []
                for a, b, f in ranges:
                    if b <= lo or a >= hi: nr.append((a, b, f)); continue
                    if a < lo: nr.append((a, lo, f))
                    if b > hi: nr.append((hi, b, f))
                nr.append((lo, hi, col)); ranges = nr
    apply_ranges(par, ranges)

def main(src, dst):
    o = Document(sys.argv[3] if len(sys.argv) > 3 else 'smartcities-4547789.docx'); d = Document(src)
    op = [p for p in o.paragraphs if p.text.strip()]; vp = [p for p in d.paragraphs if p.text.strip()]
    DEF, EXEMPT = resolve(vp)
    sm = difflib.SequenceMatcher(None, [p.text for p in op], [p.text for p in vp], autojunk=False)
    n = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        olds = [p.text for p in op[i1:i2]]
        for k, j in enumerate(range(j1, j2)):
            default = DEF.get(j)
            if default is None: print('NO DEFAULT for paragraph', j, vp[j].text[:60]); default = GR
            old = None
            if tag == 'replace':
                if (j2 - j1) == (i2 - i1): old = olds[k]
                else:   # unequal block: pair with the most similar old paragraph, else treat as wholly new
                    best = max(olds, key=lambda o_: difflib.SequenceMatcher(None, o_, vp[j].text, autojunk=False).ratio())
                    if difflib.SequenceMatcher(None, best, vp[j].text, autojunk=False).ratio() > 0.5: old = best
            colour_paragraph(vp[j], old, default, exempt=(j in EXEMPT)); n += 1
    # ---- tables: new[i] <-> old[i-1] for i>=2 ; new[1] (Algorithm) all yellow
    T = d.tables; OT = o.tables
    tab_default = {0: P, 3: G, 7: V, 9: V, 10: V, 13: G}
    for ti, t in enumerate(T):
        if ti == 1:
            for r in t.rows:
                for c in r.cells:
                    for p in c.paragraphs:
                        for run in p.runs: shade_run(run, Y)
            continue
        ot = OT[ti - 1] if ti >= 1 else OT[0]
        for ri, row in enumerate(t.rows):
            for ci, cell in enumerate(row.cells):
                oldtxt = ot.rows[ri].cells[ci].text if ri < len(ot.rows) and ci < len(ot.rows[ri].cells) else None
                if oldtxt == cell.text: continue
                default = tab_default.get(ti, GR)
                # per-cell overrides
                txt = cell.text
                row0 = row.cells[0].text.strip()
                if ti == 3 and (row0.startswith('E18') or row0.startswith('E19')): default = P
                if ti == 3 and (row0.startswith('E18') or row0.startswith('E20')): default = G      # round 2, Reviewer 1 C2 / C3
                if ti == 3 and (row0.startswith('E21') or row0.startswith('E22')): default = P      # round 2, Reviewer 3 points 3 / 4
                if ti in (7, 8): default = G                                                         # round 2, Reviewer 1 C4 (Tables 7, 8 regenerated)
                if ti == 3 and 'threshold sweep' in txt: default = GR
                if ti == 3 and ('E17' in txt or 'independent validation' in txt or 'four attacks' in txt): default = G
                if ti == 0: default = P
                if ti == 0 and 'every round but one' in txt: default = GR     # Table 1 A2-iii evidence cell, authors' correction
                if ti == 0 and ('E21' in txt or 'honest majority assumed' in txt): default = P   # round 2, Reviewer 3 point 3
                if ti == 13 and ci in (6, 7): default = G          # Table 13 quarantine / honest columns (R1 C6)
                for p in cell.paragraphs:
                    for run in p.runs: shade_run(run, default)
                if ti == 3 and 'Table S11' in txt and 'flame_impl' not in txt:                   # E18 row: the K = 20/50 extension is the authors' own (grey run inside an R3 cell)
                    for p in cell.paragraphs:
                        for run in p.runs:
                            if 'K = 20 and 50 under the E9 protocol' in run.text: shade_run(run, GR)
    # revise-v30: the four markdown leftovers (*mean*, *median*, *are*) became italic runs; the token changed, so it is
    # shaded, and the change is the authors' own
    for p in vp:
        for r in p.runs:
            if r.italic and r.text.strip() in ('mean', 'median', 'are'): shade_run(r, GR)
    d.save(dst); print('paragraphs coloured:', n)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
