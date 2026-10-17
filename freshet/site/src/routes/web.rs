//! Filing a return that was prepared in a browser.
//!
//! # The problem this endpoint exists to solve
//!
//! The web channel computes in the page. That is what lets a hosted product
//! keep most of the desktop's privacy claim: while a corporation is entering
//! its financial statements, nothing leaves the machine.
//!
//! It also means the figures arriving here were produced by code the user
//! controls. A browser tab can be edited. Anyone who wanted to file a return
//! showing no tax payable could do it from the developer console, and the
//! server would have no way to know — if the server believed what it was told.
//!
//! So it does not. This endpoint takes the **facts**, runs the same engine over
//! them, and compares its own result against what the browser reported. The
//! browser's numbers are a claim to be checked, not data to be used.
//!
//! # Why compare rather than simply overwrite
//!
//! Recomputing and quietly filing the server's answer would be simpler, and
//! wrong. If the two disagree, one of them has a bug, and the user is about to
//! file a return that does not match what they reviewed on screen. Overwriting
//! hides that; refusing surfaces it. A disagreement should be rare enough that
//! stopping is affordable and serious enough that stopping is right.
//!
//! # The order of the refusals
//!
//! Most fundamental first, so a user hears the real reason:
//!
//! 1. The period is not one a corporation can have.
//! 2. The two calculations disagree.
//! 3. A parameter behind the calculation is unverified.
//! 4. This build is not certified for that year and province.
//! 5. The licence has no filing left.
//!
//! Only the last one costs the customer anything, and it is last on purpose:
//! taking a filing off someone's allowance and *then* telling them the return
//! could not be sent would be the worst version of this.

use std::collections::BTreeMap;

use axum::extract::State;
use axum::Json;
use freshet_engine::{compute_across, Date, FactSet, Period};
use serde::{Deserialize, Serialize};

use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct FileRequest {
    pub period_start: String,
    pub period_end: String,
    pub province: String,
    /// What the user entered. The only thing here taken at face value, because
    /// it is the only thing that is genuinely theirs to assert.
    pub facts: BTreeMap<String, String>,
    /// What their browser made of it.
    #[serde(default)]
    pub computed: BTreeMap<String, String>,
    /// Present when the customer has bought a counted licence.
    #[serde(default)]
    pub key: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct Disagreement {
    pub line: String,
    pub browser: String,
    pub server: String,
}

#[derive(Debug, Serialize)]
pub struct Verdict {
    pub allowed: bool,
    pub reason: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub disagreement: Vec<Disagreement>,
}

impl Verdict {
    fn no(reason: impl Into<String>) -> Self {
        Self {
            allowed: false,
            reason: reason.into(),
            disagreement: Vec::new(),
        }
    }
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

/// Read an amount the way a person typed it, exactly as the browser does.
///
/// This has to agree with the web build's parsing. If it did not, every user
/// who typed a dollar sign would be told the two calculations disagreed.
fn parse_money(raw: &str) -> Option<rust_decimal::Decimal> {
    let cleaned: String = raw
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();
    cleaned.parse().ok()
}

fn assess(req: &FileRequest) -> Result<(freshet_engine::Assessment, Period), String> {
    let period = Period::new(parse_date(&req.period_start)?, parse_date(&req.period_end)?)
        .map_err(|e| e.to_string())?;

    let forms = freshet_taxdata::t2_forms(&req.province).map_err(|e| e.to_string())?;

    let mut facts = FactSet::new();
    for (key, raw) in &req.facts {
        if let Some(value) = parse_money(raw) {
            facts.set(key.clone(), value);
        }
    }

    // The same single path the browser takes. If the two picked their
    // parameters differently they would disagree on every return that crossed
    // a rate change, and the comparison below would report it as tampering.
    let packs =
        freshet_taxdata::t2_period_packs(period, &req.province).map_err(|e| e.to_string())?;
    let assessment = compute_across(&forms, &packs, &facts).map_err(|e| e.to_string())?;

    Ok((assessment, period))
}

/// Lines where the browser and the server do not agree.
///
/// Only lines the browser actually reported are compared. A client that sends
/// nothing is not thereby in agreement — the caller refuses an empty report
/// rather than reading it as a clean bill.
fn compare(
    a: &freshet_engine::Assessment,
    claimed: &BTreeMap<String, String>,
) -> Vec<Disagreement> {
    let mut out = Vec::new();

    for entry in &a.audit {
        let Some(theirs) = claimed.get(&entry.id) else {
            continue;
        };

        let ours = entry.value.round_dp(2);
        let agrees = parse_money(theirs).map(|t| t == ours).unwrap_or(false);

        if !agrees {
            out.push(Disagreement {
                line: entry.id.clone(),
                browser: theirs.clone(),
                server: ours.to_string(),
            });
        }
    }

    out
}

/// Every refusal that can be decided from the calculation itself.
///
/// Split out from [`file`] so it can be tested directly. That is not tidiness:
/// today every T2 parameter pack still carries unverified figures, so the
/// unverified check below always fires first and the certification check
/// underneath it is unreachable through the endpoint. Code that cannot be
/// reached is code that quietly stops being right — this project has already
/// been bitten once by a seam built early and left unexercised. Testing the
/// function directly keeps the certification branch honest until the data
/// catches up and the endpoint starts reaching it on its own.
fn refuse(
    assessment: &freshet_engine::Assessment,
    period: Period,
    province: &str,
) -> Option<Verdict> {
    if !assessment.warnings.is_empty() {
        return Some(Verdict::no(format!(
            "This return relies on {} figure(s) that have not been checked \
             against a published source, so it cannot be filed.",
            assessment.warnings.len()
        )));
    }

    if assessment.has_errors() {
        return Some(Verdict::no(
            "This return has errors that must be corrected before it can be filed.",
        ));
    }

    // A fiscal period is filed under the year it ends in.
    let year = period.end.year as u16;
    // This endpoint files corporate returns only.
    if !freshet_taxdata::is_certified(
        freshet_taxdata::Filing::T2 {
            year_end: period.end,
        },
        province,
    ) {
        return Some(Verdict::no(if freshet_taxdata::in_certification_scope(province) {
            format!(
                "Freshet is not yet certified by the CRA to transmit a {} {} \
                 return. It has been calculated and can be printed, but it \
                 cannot be sent from here.",
                year,
                province.to_uppercase()
            )
        } else {
            out_of_scope(province)
        }));
    }

    None
}

/// Said the same way wherever a province is out of scope, because "we do not
/// file this yet" and "we do not file this" are different promises and a
/// customer choosing what to buy is entitled to know which one they have.
fn out_of_scope(province: &str) -> String {
    format!(
        "Freshet does not file {} corporate returns. Only Ontario is in the \
         current certification.",
        province.to_uppercase()
    )
}

pub async fn file(State(state): State<AppState>, Json(req): Json<FileRequest>) -> Json<Verdict> {
    // Ahead of the calculation, because the engine's own answer for an
    // unsupported province is a developer's sentence — "no T2 data for bc;
    // this build supports [\"on\"]" — and it was reaching customers verbatim.
    // What a person needs to know here is which provinces we file, not what
    // our data directory contains.
    if !freshet_taxdata::T2_PROVINCES.contains(&req.province.as_str()) {
        return Json(Verdict::no(out_of_scope(&req.province)));
    }

    let (assessment, period) = match assess(&req) {
        Ok(pair) => pair,
        Err(e) => return Json(Verdict::no(e)),
    };

    if req.computed.is_empty() {
        return Json(Verdict::no(
            "Freshet could not check this return against what your browser \
             calculated, so it will not file it.",
        ));
    }

    let disagreement = compare(&assessment, &req.computed);
    if !disagreement.is_empty() {
        return Json(Verdict {
            allowed: false,
            reason: "The calculation on this server does not match the one in your browser."
                .into(),
            disagreement,
        });
    }

    if let Some(refusal) = refuse(&assessment, period, &req.province) {
        return Json(refusal);
    }

    // Last, and only now that the return would genuinely go.
    match req.key.as_deref() {
        Some(key) => {
            if let Err(reason) = claim_one(&state, key, &req, period).await {
                return Json(Verdict::no(reason));
            }
        }
        None => return Json(Verdict::no("A licence is needed to file this return.")),
    }

    Json(Verdict {
        allowed: true,
        reason: "This return is ready to transmit.".into(),
        disagreement: Vec::new(),
    })
}

/// Count the filing against the licence, on the same path the desktop uses.
///
/// The reference is derived from the return rather than generated, so a retry
/// after a dropped connection lands on the same row and does not take a second
/// filing off the allowance.
async fn claim_one(
    state: &AppState,
    key: &str,
    req: &FileRequest,
    period: Period,
) -> Result<(), String> {
    let parsed = freshet_license::LicenceKey::parse(key)
        .map_err(|_| "That licence key was not recognised.".to_string())?;

    let record = state
        .store
        .by_key(&parsed.compact())
        .await
        .map_err(|_| "Freshet could not check that licence just now.".to_string())?
        .ok_or_else(|| "That licence key was not recognised.".to_string())?;

    if record.is_revoked() {
        return Err("That licence has been withdrawn.".into());
    }

    let public = state.signing_key.verifying_key().to_bytes();
    let licence = freshet_license::verify_with(&record.token, &public)
        .map_err(|_| "That licence could not be verified.".to_string())?;

    if !licence.allowance.needs_authoritative_count() {
        return Ok(());
    }

    let reference = format!(
        "t2:{}:{}:{}",
        req.province,
        period.start,
        period.end
    );

    let used_before = state
        .store
        .filings_used(&record.key)
        .await
        .map_err(|_| "Freshet could not check that licence just now.".to_string())?;

    let claimed = state
        .store
        .claim_filing(&record.key, &reference, state.clock.now())
        .await
        .map_err(|_| "Freshet could not record this filing.".to_string())?;

    let (used, already) = match claimed {
        Some(used) => (used, false),
        None => (used_before, true),
    };

    if !already && !licence.allowance.permits(used.saturating_sub(1)) {
        return Err("This licence's returns have all been filed.".into());
    }

    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;

    fn clean(province: &str) -> freshet_engine::Assessment {
        freshet_engine::Assessment {
            tax_year: 2026,
            province: province.into(),
            lines: Default::default(),
            audit: Vec::new(),
            // The state the product is working towards: every figure checked.
            warnings: Vec::new(),
            diagnostics: Vec::new(),
        }
    }

    fn calendar(year: i32) -> Period {
        Period::new(
            Date::new(year, 1, 1).unwrap(),
            Date::new(year, 12, 31).unwrap(),
        )
        .unwrap()
    }

    /// The check that is unreachable through the endpoint today, and which has
    /// to keep working for the day it is not.
    ///
    /// Computing a year is not permission to transmit it. Ontario 2026 is
    /// calculated correctly and is still not certified.
    #[test]
    fn a_verified_return_is_still_refused_until_the_year_is_certified() {
        let refusal = refuse(&clean("on"), calendar(2026), "on")
            .expect("an uncertified year must be refused");

        assert!(!refusal.allowed);
        assert!(
            refusal.reason.contains("not yet certified"),
            "got: {}",
            refusal.reason
        );
    }

    /// "Not yet" and "not at all" are different answers, and a customer
    /// deciding what to buy needs the right one.
    #[test]
    fn a_province_outside_the_scope_is_not_told_to_wait_for_it() {
        let refusal = refuse(&clean("bc"), calendar(2026), "bc").unwrap();

        assert!(refusal.reason.contains("does not file BC"));
        assert!(!refusal.reason.contains("not yet"));
    }

    /// The unverified check comes first, because it is the more fundamental
    /// objection: a certified build computing from an unchecked rate is worse
    /// than an uncertified one, not better.
    #[test]
    fn unverified_figures_are_reported_before_certification_is_considered() {
        let mut a = clean("on");
        a.warnings.push("fed.small_business_rate is unverified".into());

        let refusal = refuse(&a, calendar(2026), "on").unwrap();

        assert!(refusal.reason.contains("not been checked"));
    }
}
