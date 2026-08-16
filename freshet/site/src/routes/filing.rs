//! Claiming a filing against a counted licence.
//!
//! This is the endpoint the desktop app calls **at the moment of transmission**,
//! and only for a licence whose allowance is counted.
//!
//! # Why this is not a contradiction of the offline design
//!
//! Everything else about licensing here is deliberately offline, on the grounds
//! that our uptime must never sit between a person and their filing deadline.
//! That reasoning does not apply at transmission: you are sending the return to
//! CRA, so the network is already a hard requirement. If it is down, the filing
//! cannot happen whatever we do. Counting here adds no dependency that was not
//! already there.
//!
//! It is also the only place a count can mean anything. The app keeps a local
//! tally, but it lives on the customer's machine and a reinstall resets it.
//! Selling "one corporate return" while trusting a number the buyer can reset
//! would be theatre.
//!
//! An **unlimited** licence never calls this. There is nothing to count, so
//! there is nothing to ask.

use axum::extract::State;
use axum::http::StatusCode;
use axum::Json;
use serde::{Deserialize, Serialize};

use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ClaimRequest {
    pub key: String,

    /// Stable identifier for the return being filed, chosen by the app.
    ///
    /// The idempotency handle. A transmission that fails after we counted it
    /// gets retried with the same reference and does not consume a second slot
    /// — losing a return off your allowance to a dropped connection would be
    /// the most infuriating possible failure.
    pub filing_ref: String,
}

#[derive(Debug, Serialize)]
pub struct ClaimResponse {
    pub used: u32,
    pub remaining: Option<u32>,
    /// True when this reference had already been counted.
    pub already_counted: bool,
}

#[derive(Debug, Serialize)]
pub struct ClaimError {
    pub error: String,
}

fn fail(code: StatusCode, message: &str) -> (StatusCode, Json<ClaimError>) {
    (code, Json(ClaimError { error: message.into() }))
}

pub async fn claim(
    State(state): State<AppState>,
    Json(req): Json<ClaimRequest>,
) -> Result<Json<ClaimResponse>, (StatusCode, Json<ClaimError>)> {
    let key = freshet_license::LicenceKey::parse(&req.key)
        .map_err(|e| fail(StatusCode::BAD_REQUEST, &e.to_string()))?;

    if req.filing_ref.trim().is_empty() {
        return Err(fail(StatusCode::BAD_REQUEST, "no filing reference"));
    }

    let record = state
        .store
        .by_key(&key.compact())
        .await
        .map_err(|e| fail(StatusCode::INTERNAL_SERVER_ERROR, &e.to_string()))?
        .ok_or_else(|| fail(StatusCode::NOT_FOUND, "no such licence key"))?;

    if record.is_revoked() {
        return Err(fail(StatusCode::GONE, "this licence was withdrawn"));
    }

    // The signed licence is the authority on the allowance, not our own row.
    // Reading it back from the token means the limit enforced here is exactly
    // the one the customer's app verified.
    //
    // Verified against *our own* public key rather than the constant compiled
    // into the desktop app. They are the same value in production, but coupling
    // the service to the app's constant would make this endpoint fail for any
    // deployment signing with a different key — including every test.
    let public = state.signing_key.verifying_key().to_bytes();
    let licence = freshet_license::verify_with(&record.token, &public)
        .map_err(|e| fail(StatusCode::INTERNAL_SERVER_ERROR, &e.to_string()))?;

    let allowance = licence.allowance;

    if !allowance.needs_authoritative_count() {
        // Unlimited. Nothing to claim, and no reason to write a row per filing
        // for a professional who may file hundreds.
        return Ok(Json(ClaimResponse {
            used: 0,
            remaining: None,
            already_counted: false,
        }));
    }

    let used_before = state
        .store
        .filings_used(&record.key)
        .await
        .map_err(|e| fail(StatusCode::INTERNAL_SERVER_ERROR, &e.to_string()))?;

    let claimed = state
        .store
        .claim_filing(&record.key, req.filing_ref.trim(), state.clock.now())
        .await
        .map_err(|e| fail(StatusCode::INTERNAL_SERVER_ERROR, &e.to_string()))?;

    let (used, already_counted) = match claimed {
        Some(used) => (used, false),
        // Already counted. Report success — the caller is retrying something
        // that did work, and telling them it failed would be wrong.
        None => (used_before, true),
    };

    // Checked after claiming so a retry of the filing that *reached* the limit
    // still succeeds rather than being refused on the way back in.
    if !already_counted && !allowance.permits(used.saturating_sub(1)) {
        return Err(fail(
            StatusCode::PAYMENT_REQUIRED,
            "this licence's returns have all been filed",
        ));
    }

    Ok(Json(ClaimResponse {
        used,
        remaining: allowance.remaining(used),
        already_counted,
    }))
}
