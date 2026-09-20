"""Shade every passage of the revised manuscript that differs from the submitted one, by source of
the change (green R1, pink R3, yellow R2, purple Editor, grey authors).
Usage: python highlight_changes.py revised.docx out.docx submitted.docx
The DEF/OVR maps below are the attribution used for revise-v15."""
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy, difflib, re, sys

G, P, Y, V, GR = 'C6EFCE', 'FFC7CE', 'FFEB9C', 'E4D0F5', 'D9D9D9'   # R1 green, R3 pink, R2 yellow, Editor purple, self grey

# ---- paragraph defaults (index in the list of non-empty paragraphs of v14)
DEF = {1: P, 6: Y, 10: G, 12: P, 13: G, 15: G, 23: G, 25: G, 27: G, 30: P, 34: P, 38: G, 39: Y, 41: G, 42: P,
       50: G, 53: G, 54: Y, 60: GR, 61: P, 64: G, 68: GR, 71: G, 72: G, 75: GR, 77: GR, 78: G, 79: G, 80: P,
       84: GR, 89: P, 92: G, 93: G, 94: G, 95: G, 100: G, 104: G, 105: G, 109: G, 118: G, 128: G, 135: GR,
       137: G, 141: P, 142: P, 143: G, 144: G, 147: G, 194: G, 195: G, 196: G, 197: G}
# ---- sentence-level overrides, applied in order; first match wins
OVR = [
    # self-found corrections (grey)
    (r'0\.780|34\.1 against|0\.79–0\.89|cosine 0\.09|0\.950 ± 0\.036|0\.926 \(scale\)|0\.939–0\.941|least repeatable|0\.9393|0\.607–0\.886|'
     r'0\.887 when|0\.365 centralised|six of nine|0\.776 to 0\.412|0\.0007|0\.9942|0\.9516|Table S8|60k-flow sample of the federated|'
     r'recall 0\.81 on the full|11/150|0\.024 F1|29/60|0\.950–0\.960|0\.00–0\.41|Tables 7, 9 and 10 and Figures|tied with Trimmed Mean under noise|'
     r'0\.939–0\.945|scaled, flipped, noisy|is the path this paper offers|threshold sweep is reported|population s\.d\.|an estimated 0\.19|'
     r'Table S8 the twelve', GR),
    # Reviewer 2 (yellow)
    (r'Generative AI|Claude Opus|GPT-5|MDPI’s policy', Y),
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

def colour_for(sentence, default):
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

def colour_paragraph(par, old_text, default):
    new = par.text
    ch = changed_ranges(old_text, new) if old_text is not None else [(0, len(new))]
    if not ch: return
    ranges = []
    for ss, se in sentences(new):
        if any(cs < se and ce > ss for cs, ce in ch):
            col = colour_for(new[ss:se], default)
            # shade only the changed sub-spans inside this sentence
            for cs, ce in ch:
                lo, hi = max(cs, ss), min(ce, se)
                if lo < hi:
                    # extend to whole words already (tokens); keep
                    ranges.append((lo, hi, col))
    apply_ranges(par, ranges)

def main(src, dst):
    o = Document(sys.argv[3] if len(sys.argv) > 3 else 'smartcities-4547789.docx'); d = Document(src)
    op = [p for p in o.paragraphs if p.text.strip()]; vp = [p for p in d.paragraphs if p.text.strip()]
    sm = difflib.SequenceMatcher(None, [p.text for p in op], [p.text for p in vp], autojunk=False)
    n = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        olds = [p.text for p in op[i1:i2]]
        for k, j in enumerate(range(j1, j2)):
            default = DEF.get(j)
            if default is None: print('NO DEFAULT for paragraph', j, vp[j].text[:60]); default = GR
            old = olds[k] if (tag == 'replace' and k < len(olds) and (j2 - j1) == (i2 - i1)) else (None if tag == 'insert' else (olds[0] if len(olds) == 1 else None))
            colour_paragraph(vp[j], old, default); n += 1
    # ---- tables: new[i] <-> old[i-1] for i>=2 ; new[1] (Algorithm) all yellow
    T = d.tables; OT = o.tables
    tab_default = {0: P, 3: G, 7: GR, 9: GR, 10: GR, 13: G}
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
                if ti == 3 and txt.startswith('E18'): default = P
                if ti == 3 and txt.startswith('E19'): default = P
                if ti == 3 and 'threshold sweep' in txt: default = GR
                if ti == 3 and ('E17' in txt or 'independent validation' in txt or 'four attacks' in txt): default = G
                if ti == 0: default = P
                if ti == 13 and ci in (6, 7): default = G          # Table 13 quarantine / honest columns (R1 C6)
                if ti == 9 and ('†' in txt and ci in (4, 5)) and oldtxt is not None and oldtxt.replace('0.938', '0.939') == txt: default = GR
                for p in cell.paragraphs:
                    for run in p.runs: shade_run(run, default)
    d.save(dst); print('paragraphs coloured:', n)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
