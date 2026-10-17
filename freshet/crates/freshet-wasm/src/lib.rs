//! Freshet in a browser.
//!
//! # Why this exists, and what it protects
//!
//! The desktop product's central claim is that a tax return never leaves the
//! machine it was prepared on. A hosted product cannot make that claim the same
//! way — but it can make most of it, and this crate is the reason.
//!
//! The engine compiles to WebAssembly, so **the calculation runs in the
//! browser**. A corporation entering its financial statements is computing on
//! its own device, exactly as on the desktop; the server sees a return only
//! when there is something to transmit or store, and what it stores can be
//! ciphertext the browser produced.
//!
//! That is a materially different posture from the usual web tax product, where
//! every keystroke is posted to a server that does the arithmetic. It is worth
//! saying plainly what it does *not* buy:
//!
//! - **Licensing cannot be verified offline here.** The desktop build checks a
//!   signature against a key compiled into the binary, which a browser tab
//!   cannot be trusted to do — anyone can edit the JavaScript. Entitlement for
//!   the web product has to be decided server-side, at transmission.
//! - **The user still trusts the served code.** A desktop binary is signed and
//!   changes only when someone installs an update; a page is whatever the
//!   server sent this morning. That is inherent to the channel.
//! - **Storage is a separate decision** from computation, and the honest one is
//!   ciphertext the browser encrypted.
//!
//! # What is deliberately not here
//!
//! No licensing, no vault, no network. `freshet-store` depends on the OS
//! keychain and does not belong in a browser; `freshet-license` verifies
//! offline, which is exactly what a browser cannot do meaningfully. Leaving
//! them out is the point rather than an omission — this crate computes, and
//! nothing else.

use freshet_engine::{compute, compute_across, Date, FactSet, Period};
use serde::Serialize;
use wasm_bindgen::prelude::*;

/// One computed line, as the page renders it.
#[derive(Serialize)]
pub struct Line {
    pub id: String,
    pub label: String,
    pub value: String,
    pub note: Option<String>,
}

#[derive(Serialize)]
pub struct Diagnostic {
    pub id: String,
    pub severity: String,
    pub message: String,
    pub help: Option<String>,
}

#[derive(Serialize)]
pub struct Computed {
    pub lines: Vec<Line>,
    pub diagnostics: Vec<Diagnostic>,
    /// Parameters not yet checked against a published source. Non-empty means
    /// the return must not be filed, whatever else is true of it.
    pub warnings: Vec<String>,
    pub has_errors: bool,
    /// The figures behind this return are verified and it has no errors.
    ///
    /// **Not** permission to file, and the page must not read it as such.
    /// Nothing is certified, so `certified_to_file` is false for every return
    /// this build can produce — and the server decides at transmission in any
    /// case, because a page cannot be trusted to gate itself.
    pub data_sound: bool,
    pub certified_to_file: bool,
    pub may_file: bool,
}

fn facts_from(json: &str) -> Result<FactSet, String> {
    let raw: std::collections::BTreeMap<String, String> =
        serde_json::from_str(json).map_err(|e| format!("facts are not readable: {e}"))?;

    let mut facts = FactSet::new();
    for (key, value) in raw {
        let cleaned: String = value
            .chars()
            .filter(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
            .collect();

        if let Ok(parsed) = cleaned.parse() {
            facts.set(key, parsed);
        }
    }

    Ok(facts)
}

fn present(a: &freshet_engine::Assessment, certified: bool) -> Computed {
    Computed {
        lines: a
            .audit
            .iter()
            .map(|e| Line {
                id: e.id.clone(),
                label: e.label.clone(),
                value: e.value.round_dp(2).to_string(),
                note: e.note.clone(),
            })
            .collect(),
        diagnostics: a
            .diagnostics
            .iter()
            .map(|d| Diagnostic {
                id: d.id.clone(),
                severity: format!("{:?}", d.severity).to_lowercase(),
                message: d.message.clone(),
                help: d.help.clone(),
            })
            .collect(),
        warnings: a.warnings.clone(),
        has_errors: a.has_errors(),
        data_sound: a.is_filable(),
        certified_to_file: certified,
        may_file: a.is_filable() && certified,
    }
}

fn to_json<T: Serialize>(value: &T) -> Result<String, String> {
    serde_json::to_string(value).map_err(|e| e.to_string())
}

// The functions below carry the logic and return plain strings, so they can be
// tested on the host. `JsValue` exists only on wasm32 — an earlier version
// returned it directly and the tests aborted the process rather than failing,
// which is a poor way to find out. The `#[wasm_bindgen]` wrappers are the only
// place the browser boundary appears.

fn t1(tax_year: u16, province: &str, facts_json: &str) -> Result<String, String> {
    let forms = freshet_taxdata::t1_forms(tax_year, province).map_err(|e| e.to_string())?;
    let packs = freshet_taxdata::packs(tax_year, province).map_err(|e| e.to_string())?;
    let facts = facts_from(facts_json)?;

    let a = compute(&forms, &packs, &facts).map_err(|e| e.to_string())?;
    let certified =
        freshet_taxdata::is_certified(freshet_taxdata::Filing::T1 { year: tax_year }, province);
    to_json(&present(&a, certified))
}

/// Compute a personal return.
#[wasm_bindgen]
pub fn compute_t1(tax_year: u16, province: &str, facts_json: &str) -> Result<String, JsValue> {
    t1(tax_year, province, facts_json).map_err(|e| JsValue::from_str(&e))
}

fn parse_date(raw: &str) -> Result<Date, String> {
    let parts: Vec<&str> = raw.trim().split('-').collect();
    if parts.len() != 3 {
        return Err(format!("{raw} is not a date in YYYY-MM-DD form"));
    }

    let n = |s: &str| s.parse::<i64>().map_err(|_| format!("{raw} is not a date"));

    Date::new(n(parts[0])? as i32, n(parts[1])? as u32, n(parts[2])? as u32)
        .map_err(|e| e.to_string())
}

/// Compute a corporate return for a fiscal period.
///
/// The period, not a tax year: a corporation does not have one. A period
/// crossing a calendar boundary is computed from both years so a rate change
/// between them is apportioned by days, and the caller does not have to know
/// which path applies.
#[wasm_bindgen]
pub fn compute_t2(
    period_start: &str,
    period_end: &str,
    province: &str,
    facts_json: &str,
) -> Result<String, JsValue> {
    t2(period_start, period_end, province, facts_json).map_err(|e| JsValue::from_str(&e))
}

fn t2(
    period_start: &str,
    period_end: &str,
    province: &str,
    facts_json: &str,
) -> Result<String, String> {
    let period = Period::new(parse_date(period_start)?, parse_date(period_end)?)
        .map_err(|e| e.to_string())?;

    let forms = freshet_taxdata::t2_forms(province).map_err(|e| e.to_string())?;
    let facts = facts_from(facts_json)?;

    // One path, whatever the period. `t2_period_packs` cuts it wherever the
    // parameters change — at a calendar year, or at Ontario's 1 July 2026 rate
    // change — and returns a single segment when nothing changes at all.
    let packs = freshet_taxdata::t2_period_packs(period, province).map_err(|e| e.to_string())?;
    let a = compute_across(&forms, &packs, &facts).map_err(|e| e.to_string())?;

    // A fiscal period is filed under the year it ends in.
    // The year *end*, not a tax year. A T2 certification covers a window
    // of corporate year ends, which is what CRA actually grants.
    let certified = freshet_taxdata::is_certified(
        freshet_taxdata::Filing::T2 {
            year_end: period.end,
        },
        province,
    );
    to_json(&present(&a, certified))
}

/// What this build can compute, so the page does not have to be told twice.
#[wasm_bindgen]
pub fn capabilities() -> Result<String, JsValue> {
    describe().map_err(|e| JsValue::from_str(&e))
}

fn describe() -> Result<String, String> {
    #[derive(Serialize)]
    struct Capabilities {
        years: Vec<u16>,
        provinces: Vec<&'static str>,
        t2_provinces: Vec<&'static str>,
        certification_target_year: u16,
        /// Always empty here, and worth returning so the page cannot forget:
        /// nothing is certified, so nothing may be transmitted.
        certified_years: Vec<u16>,
    }

    to_json(&Capabilities {
        years: freshet_taxdata::SUPPORTED_YEARS.to_vec(),
        provinces: freshet_taxdata::supported_provinces(),
        t2_provinces: freshet_taxdata::T2_PROVINCES.to_vec(),
        certification_target_year: freshet_taxdata::CERTIFICATION_TARGET_YEAR,
        certified_years: freshet_taxdata::certified_years(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_personal_return_computes_and_reports_its_lines() {
        let out = t1(2025, "on", r#"{"t4.employment_income":"85000"}"#).unwrap();

        assert!(out.contains("fed.15000"));
        assert!(out.contains("85000"));
    }

    #[test]
    fn a_corporate_return_computes_for_a_fiscal_period() {
        let out = t2(
            "2025-07-01",
            "2026-06-30",
            "on",
            r#"{"gifi.8000":"500000"}"#,
        )
        .unwrap();

        // Straddles a calendar boundary, so the rates were apportioned.
        assert!(out.contains("t2.rates_apportioned"));
    }

    /// Amounts arrive from a browser input as whatever the user typed.
    #[test]
    fn amounts_are_read_the_way_a_person_types_them() {
        let out = t1(2025, "on", r#"{"t4.employment_income":"$85,000.00"}"#).unwrap();
        assert!(out.contains("85000"));
    }

    /// The gate travels with the calculation. A browser build that computed a
    /// return and forgot it could not be filed would be worse than useless.
    ///
    /// Anchored to a structure-first province rather than to a corporate
    /// return. This assertion has been moved twice already as the T2 data was
    /// verified underneath it — first off 2025, then off 2026 — and a test
    /// that has to be rehomed every time the product improves is testing the
    /// data rather than the gate. Alberta's personal parameters are
    /// deliberately placeholders and will be for a while.
    #[test]
    fn the_web_build_still_refuses_to_call_a_return_filable() {
        let out = t1(2026, "ab", r#"{"t4.employment_income":"85000"}"#).unwrap();

        assert!(out.contains("\"may_file\":false"), "got: {out}");
        assert!(out.contains("unverified"));
    }

    /// And the browser is not the place that decides it may be transmitted.
    ///
    /// A fully verified year computes clean here, which is exactly why the
    /// page must not read `filable` as permission to file: nothing is
    /// certified, and only the server knows that.
    #[test]
    fn a_clean_year_still_carries_no_certification() {
        let out = t2("2025-01-01", "2025-12-31", "on", "{}").unwrap();
        assert!(out.contains("\"data_sound\":true"), "got: {out}");

        assert!(describe().unwrap().contains("\"certified_years\":[]"));
    }

    #[test]
    fn a_period_that_cannot_be_a_fiscal_year_is_refused() {
        assert!(t2("2025-01-01", "2027-01-01", "on", "{}").is_err());
        assert!(t2("2025-02-29", "2025-12-31", "on", "{}").is_err());
    }

    #[test]
    fn the_page_is_told_nothing_is_certified() {
        let out = describe().unwrap();
        assert!(out.contains("\"certified_years\":[]"));
    }
}
