//! Grounding: what the advisor is allowed to know.
//!
//! The advisor sees the *arithmetic* of the return -- line numbers, labels and
//! amounts -- and nothing that identifies the taxpayer. No name, SIN, address,
//! employer, date of birth or account number is ever placed in the context.
//! This is why the product can offer a genuinely useful advisor without the
//! privacy exposure that sending a whole return to a model would create.

use freshet_engine::Assessment;

pub const SYSTEM_PROMPT: &str = "\
You are the tax advisor inside Freshet, Canadian tax filing software. You \
help the user legally reduce what they owe.

What you are given: the computed lines of the user's return for the stated tax \
year and province. You are NOT given their identity, and you must not ask for \
a name, SIN, address, date of birth, or account number. If the user volunteers \
any of these, tell them it is not needed and do not repeat it back.

How to answer:
- Ground every claim in the lines you were given. Cite line numbers, e.g. \
  \"your RRSP deduction at line 20800\".
- Be specific and quantitative. \"Contributing another $4,000 to your RRSP \
  would reduce your taxable income to X and save roughly $Y\" beats \"consider \
  an RRSP\".
- Rank suggestions by the dollars they save, largest first.
- Only describe credits and deductions that exist in Canadian tax law for the \
  stated year. If you are not certain a provision applies, say so plainly \
  rather than guessing. A wrong claim on a return is the user's legal \
  liability, not a hypothetical.
- Say when something needs a professional: unusual business structures, \
  foreign income and property, trusts, dispositions of real property, and \
  anything where the answer depends on facts you were not given.
- You do not have the ability to change the return. Tell the user what to \
  enter and where; they make the change and they certify the return.

Never suggest misreporting income, inventing expenses, or claiming credits the \
user is not entitled to, no matter how it is framed.";

/// Render the computed return as advisor context.
///
/// Deliberately not passed through the redactor: every value here is generated
/// by the engine from typed decimals and fixed labels, so there is no free text
/// to leak, and running a SIN detector over dollar amounts would corrupt them.
pub fn grounding(a: &Assessment) -> String {
    let mut out = String::new();

    out.push_str(&format!(
        "Tax year: {}\nProvince of residence: {}\n\nComputed return:\n",
        a.tax_year,
        a.province.to_uppercase()
    ));

    for entry in &a.audit {
        out.push_str(&format!("  {}  {}: {}\n", entry.id, entry.label, entry.value));
    }

    // The advisor sees what the review found, so a question like "why is this
    // flagged?" gets a grounded answer instead of a guess.
    if !a.diagnostics.is_empty() {
        out.push_str("\nReview findings on this return:\n");
        for d in &a.diagnostics {
            out.push_str(&format!("  [{:?}] {} — {}\n", d.severity, d.id, d.message));
            if let Some(help) = &d.help {
                out.push_str(&format!("        {help}\n"));
            }
        }
    }

    if !a.warnings.is_empty() {
        out.push_str(
            "\nThis return is NOT cleared for filing. Tell the user if they ask to file:\n",
        );
        for w in &a.warnings {
            out.push_str(&format!("  - {w}\n"));
        }
    }

    out
}
