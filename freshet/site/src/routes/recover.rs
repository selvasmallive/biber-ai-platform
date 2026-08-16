//! "Send me my licence again."
//!
//! Three rules, and every one of them exists because the obvious
//! implementation is a vulnerability:
//!
//! 1. **Send to the registered address, never to the page.** Displaying a
//!    licence in response to an unauthenticated form turns this endpoint into a
//!    key-harvesting oracle for anyone who can guess customer emails.
//! 2. **Answer identically whether or not the address is on file.** Otherwise
//!    the endpoint confirms who is a customer, which is itself a disclosure.
//! 3. **Rate-limit per address, in storage.** Without it, this is an
//!    unauthenticated way to send mail to arbitrary people.

use axum::extract::State;
use axum::Json;
use serde::{Deserialize, Serialize};

use crate::mail::licence_email;
use crate::AppState;

/// One hour, three attempts. Enough for someone whose mail is slow, not enough
/// to be a mail cannon.
const WINDOW_SECS: i64 = 3_600;
const MAX_IN_WINDOW: i64 = 3;

#[derive(Debug, Deserialize)]
pub struct RecoverRequest {
    pub email: String,
}

#[derive(Debug, Serialize)]
pub struct RecoverResponse {
    pub message: String,
}

/// The single response this endpoint is allowed to give, whatever happened.
fn always() -> String {
    "If that address has a licence, it is on its way. \
     Check your spam folder if it does not arrive."
        .into()
}

pub async fn recover(
    State(state): State<AppState>,
    Json(req): Json<RecoverRequest>,
) -> Json<RecoverResponse> {
    Json(RecoverResponse {
        message: run(&state, &req.email).await,
    })
}

/// The same thing, for the plain HTML form on `/recover`.
///
/// Sharing `run` rather than duplicating it is what stops the two paths
/// drifting into different disclosure behaviour — the browser path is exactly
/// as tight-lipped as the API one because it is the same code.
pub async fn recover_form(
    State(state): State<AppState>,
    axum::extract::Form(req): axum::extract::Form<RecoverRequest>,
) -> axum::response::Html<String> {
    let message = run(&state, &req.email).await;

    axum::response::Html(format!(
        "<!doctype html><meta charset=utf-8><title>Freshet</title>
         <style>body{{font:16px/1.6 system-ui;margin:0 auto;padding:2rem 1.25rem;max-width:42rem}}</style>
         <h1>Check your email</h1><p>{message}</p><p><a href=\"/\">Back</a></p>"
    ))
}

async fn run(state: &AppState, requested: &str) -> String {
    let email = crate::store::normalise_email(requested);
    let now = state.clock.now();

    // Every failure below returns the same thing. Deliberately no `?` in this
    // function: an error path that returned a different status would leak
    // exactly what the identical wording is here to hide.
    let permitted = state
        .store
        .recovery_permitted(&email, now, WINDOW_SECS, MAX_IN_WINDOW)
        .await
        .unwrap_or(false);

    if !permitted {
        tracing::info!("recovery rate-limited");
        return always();
    }

    let Ok(licences) = state.store.for_email(&email).await else {
        tracing::error!("recovery lookup failed");
        return always();
    };

    for licence in licences.iter().filter(|l| !l.is_revoked()) {
        let formatted = freshet_license::LicenceKey::parse(&licence.key)
            .map(|k| k.formatted())
            .unwrap_or_else(|_| licence.key.clone());

        let body = licence_email(licence, &formatted);

        if let Err(e) = state
            .mailer
            .send(&email, "Your Freshet licence", &body)
            .await
        {
            tracing::error!("could not send recovery mail: {e}");
        }
    }

    always()
}
