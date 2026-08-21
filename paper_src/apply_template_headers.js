// apply_template_headers.js -- copy the journal template's header and footer
// parts into a built manuscript, verbatim.
//
// Why this exists: the template's headers and footers are not styles, so
// loading styles.xml does not carry them (CHANGELOG CA), and rebuilding them
// by hand missed pieces twice: the first-page logo table (header3) and the
// DOI footer on later pages (footer1). Copying the parts byte-for-byte from
// paper_src/template/smartcities-template.dot is the only approach that
// cannot drift from the journal: if MDPI ships a new template, drop the file
// in and rebuild.
//
// Template part roles (titlePg on, evenAndOddHeaders off, so "even" is inert
// but carried anyway to match the template exactly):
//   header1.xml  even    (empty)
//   header2.xml  default running head: "Smart Cities 2026, 9, x FOR PEER
//                        REVIEW" + PAGE of NUMPAGES, rule below
//   header3.xml  first   logo table (journal logo left, MDPI logo right)
//   footer1.xml  default DOI, right-aligned
//   footer2.xml  first   rule above + journal line left, DOI right
//
// Usage: require("./apply_template_headers").apply(docxPath, dotPath)
//        or: node paper_src/apply_template_headers.js <built.docx>
// Requires jszip (a dependency of the docx package already in use).

const fs = require("fs");
const path = require("path");

let JSZip;
try { JSZip = require("jszip"); }
catch (e) { throw new Error("jszip not found -- run: npm i jszip (it ships with the docx package)"); }

const HDR_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml";
const FTR_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml";
const REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

// media are renamed on copy so they can never collide with the manuscript's
// own figures; header3.xml.rels is rewritten to the new names (the only part
// not carried byte-verbatim -- it is pure metadata).
const MEDIA = { "media/image3.png": "media/tpl_logo_journal.png",
                "media/image4.png": "media/tpl_logo_mdpi.png" };

async function apply(docxPath, dotPath) {
  const dot = await JSZip.loadAsync(fs.readFileSync(dotPath));
  const doc = await JSZip.loadAsync(fs.readFileSync(docxPath));

  const rd = (zip, name) => zip.file(name).async("nodebuffer");
  const rds = (zip, name) => zip.file(name).async("string");

  // 1. drop every header/footer part the builder made, with its rels
  const dropRe = /^word\/(_rels\/)?(header|footer)\d+\.xml(\.rels)?$/;
  Object.keys(doc.files).filter(n => dropRe.test(n)).forEach(n => doc.remove(n));

  // 2. copy the five parts verbatim, plus renamed media and patched rels
  for (const part of ["header1.xml", "header2.xml", "header3.xml", "footer1.xml", "footer2.xml"])
    doc.file("word/" + part, await rd(dot, "word/" + part));
  for (const [src, dst] of Object.entries(MEDIA))
    doc.file("word/" + dst, await rd(dot, "word/" + src));
  let h3rels = await rds(dot, "word/_rels/header3.xml.rels");
  for (const [src, dst] of Object.entries(MEDIA)) h3rels = h3rels.split(src).join(dst);
  doc.file("word/_rels/header3.xml.rels", h3rels);

  // 3. document.xml.rels: drop old header/footer relationships, add five new
  let rels = await rds(doc, "word/_rels/document.xml.rels");
  rels = rels.replace(/<Relationship [^>]*Target="(header|footer)\d+\.xml"[^>]*\/>/g, "");
  const add = [["rIdTplH1", "header", "header1.xml"], ["rIdTplH2", "header", "header2.xml"],
               ["rIdTplH3", "header", "header3.xml"], ["rIdTplF1", "footer", "footer1.xml"],
               ["rIdTplF2", "footer", "footer2.xml"]]
    .map(([id, kind, tgt]) => `<Relationship Id="${id}" Type="${REL_NS}/${kind}" Target="${tgt}"/>`)
    .join("");
  rels = rels.replace("</Relationships>", add + "</Relationships>");
  const relIds = [...rels.matchAll(/Id="([^"]+)"/g)].map(m => m[1]);
  if (new Set(relIds).size !== relIds.length)
    throw new Error("duplicate relationship Id in word/_rels/document.xml.rels");
  doc.file("word/_rels/document.xml.rels", rels);

  // 4. document.xml: replace the references in sectPr with the template's
  //    mapping, and adopt the template's pgSz (A4, w:code="9")
  let dx = await rds(doc, "word/document.xml");
  dx = dx.replace(/<w:(headerReference|footerReference)[^>]*\/>/g, "");
  const refs = '<w:headerReference w:type="even" r:id="rIdTplH1"/>' +
               '<w:headerReference w:type="default" r:id="rIdTplH2"/>' +
               '<w:headerReference w:type="first" r:id="rIdTplH3"/>' +
               '<w:footerReference w:type="default" r:id="rIdTplF1"/>' +
               '<w:footerReference w:type="first" r:id="rIdTplF2"/>';
  if (!/<w:sectPr[^>]*>/.test(dx)) throw new Error("no sectPr found in document.xml");
  dx = dx.replace(/(<w:sectPr[^>]*>)/, "$1" + refs);
  dx = dx.replace(/<w:pgSz [^/]*\/>/, '<w:pgSz w:w="11906" w:h="16838" w:code="9"/>');
  if (!dx.includes("<w:titlePg")) dx = dx.replace("<w:pgSz", "<w:titlePg/><w:pgSz");
  doc.file("word/document.xml", dx);

  // 5. content types: drop old header/footer overrides, add the five parts,
  //    make sure png has a Default
  // NB: the "docx" package writes ContentType before PartName (the reverse
  // of the order used elsewhere in this file), so the strip regex must not
  // assume attribute order -- an order-locked regex here previously left
  // both the old and new Override for header1/2 and footer1/2 in place,
  // which is a duplicate-PartName Content_Types.xml that LibreOffice opens
  // but Word correctly refuses as corrupt. Match either attribute order.
  let ct = await rds(doc, "[Content_Types].xml");
  ct = ct.replace(
    /<Override(?:(?: PartName="\/word\/(?:header|footer)\d+\.xml")(?: ContentType="[^"]*")?|(?: ContentType="[^"]*")(?: PartName="\/word\/(?:header|footer)\d+\.xml"))\s*\/>/g,
    "");
  // belt-and-braces: assert no header/footer Override survived either order,
  // so a future regressions fails loudly instead of shipping a corrupt file
  if (/PartName="\/word\/(header|footer)\d+\.xml"/.test(ct))
    throw new Error("old header/footer Content_Types Override(s) were not fully stripped");
  const ovr = ["header1", "header2", "header3"].map(p =>
      `<Override PartName="/word/${p}.xml" ContentType="${HDR_CT}"/>`).join("") +
    ["footer1", "footer2"].map(p =>
      `<Override PartName="/word/${p}.xml" ContentType="${FTR_CT}"/>`).join("");
  ct = ct.replace("</Types>", ovr + "</Types>");
  if (!/Extension="png"/.test(ct))
    ct = ct.replace("</Types>", '<Default Extension="png" ContentType="image/png"/></Types>');
  // final integrity check: every PartName must be unique (OPC requires this;
  // Word treats a duplicate as a corrupt package and refuses to open it)
  const partNames = [...ct.matchAll(/PartName="([^"]+)"/g)].map(m => m[1]);
  const seen = new Set();
  for (const p of partNames) {
    if (seen.has(p)) throw new Error("duplicate Content_Types Override for " + p);
    seen.add(p);
  }
  doc.file("[Content_Types].xml", ct);

  fs.writeFileSync(docxPath, await doc.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  return docxPath;
}

module.exports = { apply };

if (require.main === module) {
  const out = process.argv[2];
  if (!out) { console.error("usage: node apply_template_headers.js <built.docx>"); process.exit(1); }
  apply(out, path.join(__dirname, "template", "smartcities-template.dot"))
    .then(p => console.log("template headers/footers applied:", p))
    .catch(e => { console.error(e.message); process.exit(1); });
}
