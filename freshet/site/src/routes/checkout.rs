//! Turning a payment into a licence.
//!
//! The webhook is the only thing that may issue a retail licence, and it is
//! reachable by anyone on the internet. Three defences, in order, before a
//! single byte of the body is trusted:
//!
//! 1. **Signature.** HMAC-SHA256 over `timestamp.body`, compared in constant
//!    time. Without it, anyone can POST themselves a licence.
//! 2. **Freshness.** A signature is valid forever unless the timestamp is
//!    checked, so a captured request could be replayed indefinitely.
//! 3. **Idempotency.** Processors retry on purpose. Issuing two licences for
//!    one purchase is a support problem in both directions.

use axum::body::Bytes;
use axum::extract::State;
use axum::http::{HeaderMap, StatusCode};
use freshet_license::LicenceKind;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use subtle::ConstantTimeEq;

use crate::issue::{issue, Offer};
use crate::mail::licence_email;
use crate::AppState;

/// How stale a signature may be. Stripe's own guidance is five minutes.
const MAX_AGE_SECS: i64 = 300;

#[derive(Debug, PartialEq, Eq)]
pub enum VerifyFailure {
    NoHeader,
    Malformed,
    TooOld,
    BadSignature,
}

/// Check a Stripe-style `t=…,v1=…` signature header.
///
/// Pure and separately tested, because this is the function standing between an
/// anonymous POST and a free licence — it should be readable without a server
/// running and provable without a payment processor.
pub fn verify_signature(
    header: Option<&str>,
    body: &[u8],
    secret: &str,
    now_unix: i64,
) -> Result<(), VerifyFailure> {
    let header = header.ok_or(VerifyFailure::NoHeader)?;

    let mut timestamp = None;
    let mut signatures: Vec<&str> = Vec::new();

    for part in header.split(',') {
        match part.trim().split_once('=') {
            Some(("t", v)) => timestamp = v.parse::<i64>().ok(),
            // Multiple v1 entries appear during a secret rotation; any one
            // matching is enough, which is what makes rotation possible.
            Some(("v1", v)) => signatures.push(v),
            _ => {}
        }
    }

    let timestamp = timestamp.ok_or(VerifyFailure::Malformed)?;
    if signatures.is_empty() {
        return Err(VerifyFailure::Malformed);
    }

    if (now_unix - timestamp).abs() > MAX_AGE_SECS {
        return Err(VerifyFailure::TooOld);
    }

    let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes())
        .map_err(|_| VerifyFailure::Malformed)?;
    mac.update(timestamp.to_string().as_bytes());
    mac.update(b".");
    mac.update(body);
    let expected = mac.finalize().into_bytes();

    let matched = signatures.iter().any(|candidate| {
        hex::decode(candidate)
            .map(|got| got.ct_eq(&expected[..]).into())
            .unwrap_or(false)
    });

    if matched {
        Ok(())
    } else {
        Err(VerifyFailure::BadSignature)
    }
}

/// What we need out of the event, and nothing more.
fn extract(body: &[u8]) -> Option<(String, String, Option<String>)> {
    let v: serde_json::Value = serde_json::from_slice(body).ok()?;

    if v.get("type")?.as_str()? != "checkout.session.completed" {
        return None;
    }

    let id = v.get("id")?.as_str()?.to_string();
    let object = v.get("data")?.get("object")?;

    // Stripe puts the address in different places depending on how the session
    // was created; both are the buyer's own address.
    let email = object
        .get("customer_details")
        .and_then(|d| d.get("email"))
        .and_then(|e| e.as_str())
        .or_else(|| object.get("customer_email").and_then(|e| e.as_str()))?
        .to_string();

    let order_ref = object.get("id").and_then(|i| i.as_str()).map(str::to_string);

    Some((id, email, order_ref))
}

pub async fn stripe_webhook(
    State(state): State<AppState>,
    headers: HeaderMap,
    body: Bytes,
) -> StatusCode {
    let Some(secret) = state.stripe_secret.as_deref() else {
        // Not configured means not accepting payments. Refusing is right;
        // quietly returning 200 would make a real misconfiguration invisible.
        tracing::error!("webhook received but STRIPE_WEBHOOK_SECRET is unset");
        return StatusCode::SERVICE_UNAVAILABLE;
    };

    let signature = headers
        .get("stripe-signature")
        .and_then(|v| v.to_str().ok());

    if let Err(why) = verify_signature(signature, &body, secret, state.clock.now()) {
        tracing::warn!(?why, "rejected a webhook");
        return StatusCode::BAD_REQUEST;
    }

    let Some((event_id, email, order_ref)) = extract(&body) else {
        // A valid event we do not act on. 200, so the processor stops retrying
        // something that will never be interesting.
        return StatusCode::OK;
    };

    match state.store.claim_event(&event_id, state.clock.now()).await {
        Ok(true) => {}
        Ok(false) => {
            tracing::info!(event_id, "already handled");
            return StatusCode::OK;
        }
        Err(e) => {
            tracing::error!("could not claim event: {e}");
            // 500 asks the processor to retry, which is what we want when we
            // genuinely do not know whether this was handled.
            return StatusCode::INTERNAL_SERVER_ERROR;
        }
    }

    let licence = match issue(
        state.store.as_ref(),
        &state.signing_key,
        &email,
        &Offer::season(state.sale_year),
        LicenceKind::Retail,
        order_ref,
        state.clock.now(),
    )
    .await
    {
        Ok(l) => l,
        Err(e) => {
            tracing::error!("could not issue a licence: {e}");
            return StatusCode::INTERNAL_SERVER_ERROR;
        }
    };

    let formatted = freshet_license::LicenceKey::parse(&licence.key)
        .map(|k| k.formatted())
        .unwrap_or_else(|_| licence.key.clone());

    if let Err(e) = state
        .mailer
        .send(&email, "Your Freshet licence", &licence_email(&licence, &formatted))
        .await
    {
        // The licence exists and is recorded, so the customer can recover it.
        // Losing the email is recoverable; re-issuing on retry would not be.
        tracing::error!("issued a licence but could not email it: {e}");
    }

    StatusCode::OK
}

#[cfg(test)]
mod tests {
    use super::*;

    const SECRET: &str = "whsec_test";

    fn sign_body(body: &[u8], timestamp: i64, secret: &str) -> String {
        let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).unwrap();
        mac.update(timestamp.to_string().as_bytes());
        mac.update(b".");
        mac.update(body);

        format!("t={timestamp},v1={}", hex::encode(mac.finalize().into_bytes()))
    }

    #[test]
    fn a_correctly_signed_request_is_accepted() {
        let body = br#"{"id":"evt_1"}"#;
        let header = sign_body(body, 1_000, SECRET);

        assert_eq!(verify_signature(Some(&header), body, SECRET, 1_000), Ok(()));
    }

    #[test]
    fn an_unsigned_request_cannot_buy_a_licence() {
        let body = br#"{"id":"evt_1"}"#;
        assert_eq!(
            verify_signature(None, body, SECRET, 1_000),
            Err(VerifyFailure::NoHeader)
        );
    }

    #[test]
    fn a_signature_from_a_different_secret_is_rejected() {
        let body = br#"{"id":"evt_1"}"#;
        let header = sign_body(body, 1_000, "whsec_someone_else");

        assert_eq!(
            verify_signature(Some(&header), body, SECRET, 1_000),
            Err(VerifyFailure::BadSignature)
        );
    }

    #[test]
    fn changing_the_body_invalidates_the_signature() {
        let header = sign_body(br#"{"amount":100}"#, 1_000, SECRET);

        assert_eq!(
            verify_signature(Some(&header), br#"{"amount":900}"#, SECRET, 1_000),
            Err(VerifyFailure::BadSignature)
        );
    }

    #[test]
    fn a_captured_request_cannot_be_replayed_tomorrow() {
        let body = br#"{"id":"evt_1"}"#;
        let header = sign_body(body, 1_000, SECRET);

        // Still perfectly signed. Age is the only thing that stops it.
        assert_eq!(
            verify_signature(Some(&header), body, SECRET, 1_000 + MAX_AGE_SECS + 1),
            Err(VerifyFailure::TooOld)
        );
    }

    #[test]
    fn a_rotated_secret_keeps_working_while_both_are_live() {
        let body = br#"{"id":"evt_1"}"#;
        let old = sign_body(body, 1_000, "whsec_old");
        let new = sign_body(body, 1_000, SECRET);

        // Stripe sends both during a rotation, joined into one header.
        let both = format!("{old},{}", new.split_once(',').unwrap().1);
        assert_eq!(verify_signature(Some(&both), body, SECRET, 1_000), Ok(()));
    }

    #[test]
    fn a_header_without_a_timestamp_is_not_treated_as_fresh() {
        let body = br#"{"id":"evt_1"}"#;
        assert_eq!(
            verify_signature(Some("v1=abcdef"), body, SECRET, 1_000),
            Err(VerifyFailure::Malformed)
        );
    }

    #[test]
    fn only_a_completed_checkout_issues_anything() {
        let ignored = br#"{"id":"evt_1","type":"payment_intent.created","data":{"object":{}}}"#;
        assert!(extract(ignored).is_none());
    }

    #[test]
    fn the_buyers_address_is_read_from_either_place_stripe_puts_it() {
        let nested = br#"{"id":"evt_1","type":"checkout.session.completed",
            "data":{"object":{"id":"cs_1","customer_details":{"email":"a@b.ca"}}}}"#;
        let flat = br#"{"id":"evt_2","type":"checkout.session.completed",
            "data":{"object":{"id":"cs_2","customer_email":"c@d.ca"}}}"#;

        assert_eq!(extract(nested).unwrap().1, "a@b.ca");
        assert_eq!(extract(flat).unwrap().1, "c@d.ca");
    }
}
