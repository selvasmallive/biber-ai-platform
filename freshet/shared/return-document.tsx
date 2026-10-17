//! The printed return.
//!
//! Shared between the desktop app and the browser build, for the same reason
//! the interview is: the questions and the document are the two things that
//! must not differ between channels. A customer who prepares on the desktop
//! and prints from the web should get the same paper.
//!
//! # What this is not
//!
//! It is **not** a CRA form facsimile, and it does not pretend to be one. It
//! is a complete statement of what was entered and what Freshet computed from
//! it, laid out to be read and checked by a person. Facsimiles of the T1
//! General and the T2 come later, from CRA's own form specifications, and
//! putting an approximation of one on paper in the meantime would be worse
//! than this — it would look official.
//!
//! # Why it says so loudly
//!
//! Three places in the product already tell customers they can print: the
//! licence-expiry notice ("your returns open, recalculate, print and export"),
//! the out-of-scope province notice, and the Alberta case in the filing gate.
//! Those promises were made before anything could print. They are kept here.
//!
//! But a printed tax return that does not say what it is becomes, on someone's
//! desk six months later, indistinguishable from a filed one. Every page
//! carries its status, and the status is computed rather than written in, so
//! it cannot drift from what the filing gate actually decided.

export interface DocumentLine {
  id: string;
  label: string;
  value: string;
  note?: string | null;
}

export interface DocumentDiagnostic {
  id: string;
  severity: string;
  message: string;
  help?: string | null;
}

export interface ReturnDocument {
  /// "T1" or "T2". Decides the headings, not the arithmetic.
  kind: "T1" | "T2";
  /// What the user called it. Never an identity field.
  label: string;
  province: string;
  /// A tax year for a T1; the fiscal period for a T2.
  period: string;
  lines: DocumentLine[];
  diagnostics: DocumentDiagnostic[];
  /// Parameters not yet checked against a published source.
  warnings: string[];
  /// What the filing gate decided, passed in rather than re-derived.
  canFile: boolean;
  /// Why not, when it cannot. Shown verbatim.
  blockedBy: string[];
  preparedAt: Date;
}

/// Lines worth pulling out of the long list, in the order a reader expects.
///
/// The full list is still printed below; this is the summary a person checks
/// first. Ids that are absent are skipped rather than printed as nil, because
/// a line that does not apply to a return should not appear on its paper.
const HEADLINE: Record<"T1" | "T2", [string, string][]> = {
  T2: [
    ["gifi.9999", "Net income per the financial statements"],
    ["t2.300", "Net income for income tax purposes"],
    ["t2.360", "Taxable income"],
    ["t2.430", "Small business deduction"],
    ["t2.700", "Federal Part I tax"],
    ["prov.tax", "Provincial tax"],
    ["summary.total_tax", "Total tax payable"],
    ["summary.balance", "Balance owing"],
  ],
  T1: [
    ["fed.15000", "Total income"],
    ["fed.23600", "Net income"],
    ["fed.26000", "Taxable income"],
    ["fed.42000", "Net federal tax"],
    ["prov.tax", "Provincial tax"],
    ["summary.total_tax", "Total tax"],
    ["summary.balance", "Balance"],
  ],
};

const money = (raw: string): string => {
  const n = Number(raw);
  if (Number.isNaN(n)) return raw;
  return n.toLocaleString("en-CA", { style: "currency", currency: "CAD" });
};

/// The stylesheet the printed page uses.
///
/// Kept as a string and injected rather than living in either app's CSS, so
/// the paper is identical whichever channel produced it. `@page` margins are
/// set here because a browser's defaults vary by platform and a tax return
/// that reflows differently on macOS and Windows is a support call.
export const PRINT_STYLES = `
@media print {
  /* Visibility rather than display, and a descendant selector rather than a
     child one. The document is rendered inside the React root, so
     \`body > *:not(.return-document)\` hid the root — and the document with it.
     That printed a blank page, which is the one bug a print feature must not
     have, because it is invisible until a customer wastes paper on it.

     \`visibility: hidden\` on everything, then \`visible\` back on the document
     and its contents, works at any nesting depth: visibility inherits, so
     turning it back on inside a hidden subtree is enough. */
  body * { visibility: hidden; }
  .return-document,
  .return-document * { visibility: visible; }

  .return-document {
    display: block !important;
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
  }

  @page { margin: 18mm 16mm; }
}

.return-document {
  display: none;
  color: #000;
  background: #fff;
  font: 11pt/1.4 "Times New Roman", Georgia, serif;
}

.return-document h1 { font-size: 16pt; margin: 0 0 2pt; }
.return-document h2 {
  font-size: 11pt;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid #000;
  padding-bottom: 2pt;
  margin: 14pt 0 6pt;
}
.return-document .meta { font-size: 9.5pt; margin: 0 0 10pt; }
.return-document .meta span { margin-right: 14pt; }

.return-document .status {
  border: 1.5pt solid #000;
  padding: 7pt 9pt;
  margin: 0 0 12pt;
}
.return-document .status strong { display: block; font-size: 11.5pt; }
.return-document .status ul { margin: 5pt 0 0; padding-left: 16pt; }
.return-document .status p { margin: 5pt 0 0; font-size: 9.5pt; }

.return-document table { width: 100%; border-collapse: collapse; }
.return-document td { padding: 1.6pt 0; vertical-align: baseline; }
.return-document td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  padding-left: 10pt;
}
.return-document td.code {
  width: 11%;
  font-size: 9pt;
  color: #333;
  white-space: nowrap;
}
.return-document .headline td { font-size: 11.5pt; padding: 3pt 0; }
.return-document .headline tr:last-child td { font-weight: bold; border-top: 1px solid #000; }

.return-document .check { margin: 0 0 7pt; font-size: 10pt; }
.return-document .check strong { display: block; }
.return-document .check span { display: block; font-size: 9.5pt; color: #333; }

.return-document .foot {
  margin-top: 16pt;
  padding-top: 5pt;
  border-top: 1px solid #000;
  font-size: 9pt;
}

/* A page break mid-figure is how a reader loses their place. */
.return-document tr, .return-document .check, .return-document .status {
  break-inside: avoid;
}
.return-document h2 { break-after: avoid; }
`;

export function ReturnDocumentView({ doc }: { doc: ReturnDocument }) {
  const find = (id: string) => doc.lines.find((l) => l.id === id);

  const headline = HEADLINE[doc.kind]
    .map(([id, label]) => [label, find(id)] as const)
    .filter((pair): pair is readonly [string, DocumentLine] => Boolean(pair[1]));

  const prepared = doc.preparedAt.toLocaleString("en-CA", {
    dateStyle: "long",
    timeStyle: "short",
  });

  return (
    <div className="return-document">
      <h1>{doc.label}</h1>
      <p className="meta">
        <span>{doc.kind === "T2" ? "Corporate return" : "Personal return"}</span>
        <span>{doc.period}</span>
        <span>{doc.province.toUpperCase()}</span>
        <span>Prepared {prepared}</span>
      </p>

      {/* Computed from the gate rather than written in, so the paper cannot
          claim something the software would refuse to do. */}
      <div className="status">
        {doc.canFile ? (
          <>
            <strong>This return has not been filed.</strong>
            <p>
              Freshet can transmit it, but nothing has been sent. A return is
              filed only once the CRA has acknowledged it.
            </p>
          </>
        ) : (
          <>
            <strong>This return cannot be filed, and has not been.</strong>
            {doc.blockedBy.length > 0 && (
              <ul>
                {doc.blockedBy.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
            <p>
              The figures below are correct for what was entered. This document
              is a working copy for review — it is not a CRA form and it is not
              a filed return.
            </p>
          </>
        )}
      </div>

      {headline.length > 0 && (
        <>
          <h2>Summary</h2>
          <table className="headline">
            <tbody>
              {headline.map(([label, line]) => (
                <tr key={line.id}>
                  <td>{label}</td>
                  <td className="num">{money(line.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {doc.warnings.length > 0 && (
        <>
          <h2>Figures not yet verified</h2>
          <p style={{ fontSize: "9.5pt", margin: "0 0 6pt" }}>
            {doc.warnings.length} parameter
            {doc.warnings.length === 1 ? " has" : "s have"} not been checked
            against a published CRA or provincial source. The arithmetic is
            correct for the figures used; the figures themselves are not
            confirmed.
          </p>
          <table>
            <tbody>
              {doc.warnings.map((w) => (
                <tr key={w}>
                  <td style={{ fontSize: "9.5pt" }}>{w}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {doc.diagnostics.length > 0 && (
        <>
          <h2>Checks</h2>
          {doc.diagnostics.map((d) => (
            <div className="check" key={d.id}>
              <strong>{d.message}</strong>
              {d.help && <span>{d.help}</span>}
            </div>
          ))}
        </>
      )}

      <h2>Every line</h2>
      <table>
        <tbody>
          {doc.lines.map((l) => (
            <tr key={l.id}>
              <td className="code">{l.id.replace(/^[a-z0-9_]+\./i, "")}</td>
              <td>{l.label}</td>
              <td className="num">{money(l.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="foot">
        Prepared with Freshet. This is a working copy, not a CRA form and not a
        filed return. Keep it with your records; a corporation must retain its
        books and records for six years from the end of the tax year they
        relate to.
      </p>
    </div>
  );
}

/// Put the document on paper.
///
/// `window.print()` rather than generating a PDF. The browser and the webview
/// both already have a print dialogue that can save to PDF, honours the user's
/// paper size, and does not require shipping a rendering engine. A PDF writer
/// would be a second layout implementation to keep in step with this one.
export function printDocument(): void {
  window.print();
}
