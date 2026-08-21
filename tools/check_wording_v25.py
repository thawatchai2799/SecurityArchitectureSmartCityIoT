#!/usr/bin/env python3
"""check_wording_v25.py -- verify the v25 and v26 wording passes survived a rebuild.

Usage:  python tools/check_wording_v25.py <Paper_Draft_SmartCities_vXX.docx>

Checks, on the extracted document text:
  v25 -- 1. zero occurrences of catch/caught/catches (the term is "quarantined");
         2. the seven v25 edits are present verbatim;
         3. the Table 16 monday row shows em dashes for F1 and recall, with attack
            share 0.0000 and FPR intact.
  v26 -- 4. the four straight-quote pairs are now curly ("I do not know",
            "scale", "source", "what was deployed on Friday");
         5. the five hyphen-minus numeric ranges are now en dashes
            (1.6-2.0, 0.80-0.90, 0.9-1.8, 5.9-6.4, 3-15 validators).
Exit code 0 iff everything passes.
"""
import html
import re
import sys
import zipfile

REQUIRED = [
    "quarantined by the direction test",
    "The control row reports false quarantines instead of rounds quarantined.",
    "but the quarantine rate is only half the story",
    "with all attackers still quarantined",
    "E9 measures a separate 5,000-transaction run per configuration, "
    "smaller than E8's 10,000-transaction benchmark of Section 5.5",
    "one wall-clock fit in the E1 benchmark",
    "F1 and recall are undefined on a day with no attack flows",
]
FORBIDDEN = re.compile(r"\bcatch(es)?\b|\bcaught\b", re.IGNORECASE)
MONDAY_ROW = re.compile(r"monday\s*in-sample\s*120,000\s*0\.0000\s*\u2014\s*\u2014\s*0\.0020")

REQUIRED_V26 = [
    "\u201cI do not know\u201d",
    "\u201cscale\u201d",
    "\u201csource\u201d means once NAT",
    "\u201cwhat was deployed on Friday\u201d",
    "1.6\u20132.0 for the honest districts",
    "0.80\u20130.90) rather than by its magnitude",
    "stays at 0.9\u20131.8%",
    "5.9\u20136.4 \u00d7 10\u2074 tx/s",
    "10\u2074 tx/s from 3\u201315 validators",
]
FORBIDDEN_HYPHEN_RANGES = ["1.6-2.0", "0.80-0.90", "0.9-1.8", "5.9-6.4", "3-15 validators"]

REQUIRED_V28 = [
    "E15 (run_advanced.py --part R)",
    "E16 (run_advanced.py --part A)",
    "deployed two-organisation Hyperledger Fabric v2.5.9 test network running on one host",
    "10 alerts/s writes about 1.91 TB per peer per year (191 GB at 1 alert/s)",
]
FORBIDDEN_V28 = ["E15 (--part R)", "E16 (--part A)", "on a real Hyperledger Fabric network",
                 "writes about 190 GB per peer per year"]

REQUIRED_V29 = [
    "storage and latency figures are the E13 measurements reported in Section 5.10",
    "should be used directly for deployment sizing where applicable",
    "CPU-time-scaled detection-energy estimate is small",
]
FORBIDDEN_V29 = ["should be recomputed from the Fabric measurements once available",
                 "the measured detection energy is small"]

REQUIRED_V31 = [
    "KB and a CPU-time-scaled estimate of",
    "had not been trained on the ransomware flows used in this replay",
    "from 5 to 50 districts under the evaluated scaling attack and tested partition settings",
    "Running it costs a CPU-time-scaled estimate of",
]
FORBIDDEN_V31 = ["had never seen ransomware",
                 "districts, at the cost of rejecting an increasing number of honest districts"]


def main(path: str) -> int:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    text = html.unescape(re.sub(r"<[^>]+>", "", xml))
    ok = True

    for m in FORBIDDEN.finditer(text):
        ok = False
        ctx = text[max(0, m.start() - 60):m.end() + 60].replace("\n", " ")
        print(f"FORBIDDEN word remains: ...{ctx}...")

    for phrase in REQUIRED:
        if phrase not in text:
            ok = False
            print(f"MISSING edit: {phrase!r}")

    if not MONDAY_ROW.search(text.replace("\n", "")):
        ok = False
        print("Table 16 monday row is not 'share 0.0000 / F1 \u2014 / recall \u2014 / FPR 0.0020'")

    for phrase in REQUIRED_V26:
        if phrase not in text:
            ok = False
            print(f"MISSING v26 edit: {phrase!r}")

    for bad in FORBIDDEN_HYPHEN_RANGES:
        if bad in text:
            ok = False
            print(f"v26 REGRESSION: hyphen-minus range still present: {bad!r}")

    for phrase in REQUIRED_V28:
        if phrase not in text:
            ok = False
            print(f"MISSING v28 edit: {phrase!r}")

    for bad in FORBIDDEN_V28:
        if bad in text:
            ok = False
            print(f"v28 REGRESSION: stale phrase still present: {bad!r}")

    for phrase in REQUIRED_V29:
        if phrase not in text:
            ok = False
            print(f"MISSING v29 edit: {phrase!r}")

    for bad in FORBIDDEN_V29:
        if bad in text:
            ok = False
            print(f"v29 REGRESSION: stale phrase still present: {bad!r}")

    for phrase in REQUIRED_V31:
        if phrase not in text:
            ok = False
            print(f"MISSING v31 edit: {phrase!r}")

    for bad in FORBIDDEN_V31:
        if bad in text:
            ok = False
            print(f"v31 REGRESSION: stale phrase still present: {bad!r}")

    print("PASS: v25+v26+v28+v29+v31 wording intact" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
