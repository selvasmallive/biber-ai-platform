//! End-to-end tests through the real router.
//!
//! The unit tests prove individual functions behave. These prove the things
//! that are only true once the routes are wired up — that an unauthenticated
//! caller cannot get a licence out of the recovery endpoint, that admin is
//! genuinely absent until configured, and that the licence a customer receives
//! is the one their app will accept.

use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use axum::body::Body;
use axum::http::{Request, StatusCode};
use freshet_license::sign::SigningKey;
use freshet_license::LicenceKind;
use freshet_site::issue::{issue, Offer};
use freshet_site::mail::{MailError, Mailer};
use freshet_site::store::memory::MemoryStore;
use freshet_site::store::Store;
use freshet_site::{router, AppState, Clock};
use tower::ServiceExt;

const NOW: i64 = 1_800_000_000;

struct FixedClock;

impl Clock for FixedClock {
    fn now(&self) -> i64 {
        NOW
    }
}

/// Captures mail instead of sending it, so a test can assert on what a
/// customer would actually have received.
#[derive(Default)]
struct Outbox(Mutex<Vec<(String, String)>>);

#[async_trait]
impl Mailer for Outbox {
    async fn send(&self, to: &str, _subject: &str, body: &str) -> Result<(), MailError> {
        self.0.lock().unwrap().push((to.into(), body.into()));
        Ok(())
    }
}

struct Harness {
    state: AppState,
    store: Arc<MemoryStore>,
    outbox: Arc<Outbox>,
    signing: SigningKey,
}

fn harness(admin_emails: Vec<String>) -> Harness {
    let store = Arc::new(MemoryStore::new());
    let outbox = Arc::new(Outbox::default());
    let signing = SigningKey::from_bytes(&[3u8; 32]);

    let state = AppState {
        store: store.clone(),
        mailer: outbox.clone(),
        clock: Arc::new(FixedClock),
        signing_key: Arc::new(signing.clone()),
        stripe_secret: None,
        admin_emails,
        sale_year: 2026,
    };

    Harness { state, store, outbox, signing }
}

async fn post(state: &AppState, path: &str, json: &str) -> (StatusCode, String) {
    let response = router(state.clone())
        .oneshot(
            Request::builder()
                .method("POST")
                .uri(path)
                .header("content-type", "application/json")
                .body(Body::from(json.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    let status = response.status();
    let bytes = axum::body::to_bytes(response.into_body(), 64 * 1024)
        .await
        .unwrap();

    (status, String::from_utf8_lossy(&bytes).into_owned())
}

async fn get(state: &AppState, path: &str, as_admin: Option<&str>) -> StatusCode {
    let mut builder = Request::builder().method("GET").uri(path);

    if let Some(email) = as_admin {
        builder = builder.header("x-goog-authenticated-user-email", email);
    }

    router(state.clone())
        .oneshot(builder.body(Body::empty()).unwrap())
        .await
        .unwrap()
        .status()
}

async fn sell_to(h: &Harness, email: &str) -> freshet_site::store::IssuedLicence {
    issue(
        h.store.as_ref(),
        &h.signing,
        email,
        &Offer::season(2026),
        LicenceKind::Retail,
        Some("order_1".into()),
        NOW,
    )
    .await
    .unwrap()
}

// -- recovery ------------------------------------------------------------

#[tokio::test]
async fn recovery_never_puts_a_licence_in_the_response_body() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "buyer@example.ca").await;

    let (status, body) = post(&h.state, "/api/recover", r#"{"email":"buyer@example.ca"}"#).await;

    assert_eq!(status, StatusCode::OK);
    assert!(
        !body.contains(&sold.token),
        "the recovery response leaked the licence: {body}"
    );
    assert!(!body.contains(&sold.key), "the recovery response leaked the key");

    // It went to the registered address instead.
    let sent = h.outbox.0.lock().unwrap();
    assert_eq!(sent.len(), 1);
    assert_eq!(sent[0].0, "buyer@example.ca");
    assert!(sent[0].1.contains(&sold.token));
}

#[tokio::test]
async fn recovery_answers_identically_for_a_stranger_and_a_customer() {
    let h = harness(vec![]);
    sell_to(&h, "buyer@example.ca").await;

    let (known_status, known) =
        post(&h.state, "/api/recover", r#"{"email":"buyer@example.ca"}"#).await;
    let (unknown_status, unknown) =
        post(&h.state, "/api/recover", r#"{"email":"nobody@example.ca"}"#).await;

    // Any difference here — status, wording, timing hints — tells an attacker
    // who is a customer.
    assert_eq!(known_status, unknown_status);
    assert_eq!(known, unknown);
}

#[tokio::test]
async fn recovery_is_not_an_unauthenticated_way_to_send_someone_mail() {
    let h = harness(vec![]);
    sell_to(&h, "buyer@example.ca").await;

    for _ in 0..10 {
        post(&h.state, "/api/recover", r#"{"email":"buyer@example.ca"}"#).await;
    }

    let sent = h.outbox.0.lock().unwrap().len();
    assert!(sent <= 3, "sent {sent} emails from 10 requests");
}

#[tokio::test]
async fn a_revoked_licence_is_not_resent() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "buyer@example.ca").await;
    h.store.revoke(&sold.key, NOW).await.unwrap();

    post(&h.state, "/api/recover", r#"{"email":"buyer@example.ca"}"#).await;

    assert!(h.outbox.0.lock().unwrap().is_empty());
}

// -- activation ----------------------------------------------------------

#[tokio::test]
async fn activation_returns_a_licence_the_app_will_accept() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "buyer@example.ca").await;

    let key = freshet_license::LicenceKey::parse(&sold.key).unwrap();
    let body = format!(
        r#"{{"key":"{}","product":"freshet-t1","device":"device-1"}}"#,
        key.formatted()
    );

    let (status, response) = post(&h.state, "/api/activate", &body).await;
    assert_eq!(status, StatusCode::OK);

    let json: serde_json::Value = serde_json::from_str(&response).unwrap();
    let token = json["licence"].as_str().unwrap();

    // The point of the whole exercise: what comes back verifies offline
    // against the public half of the key that signed it.
    let public = h.signing.verifying_key().to_bytes();
    let licence = freshet_license::verify_with(token, &public).unwrap();
    assert_eq!(licence.licensee, "buyer@example.ca");
    assert_eq!(json["devices"], 1);
}

#[tokio::test]
async fn activating_twice_from_one_machine_is_not_two_devices() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "buyer@example.ca").await;
    let key = freshet_license::LicenceKey::parse(&sold.key).unwrap().formatted();

    let same = format!(r#"{{"key":"{key}","product":"freshet-t1","device":"device-1"}}"#);
    let other = format!(r#"{{"key":"{key}","product":"freshet-t1","device":"device-2"}}"#);

    post(&h.state, "/api/activate", &same).await;
    let (_, again) = post(&h.state, "/api/activate", &same).await;
    let (_, second) = post(&h.state, "/api/activate", &other).await;

    let count = |b: &str| serde_json::from_str::<serde_json::Value>(b).unwrap()["devices"].clone();
    assert_eq!(count(&again), 1);
    assert_eq!(count(&second), 2);
}

#[tokio::test]
async fn an_invented_key_gets_nothing() {
    let h = harness(vec![]);

    let invented = freshet_license::LicenceKey::from_payload("ZZZZZZZZZZZZZZZZ").unwrap();
    let body = format!(
        r#"{{"key":"{}","product":"freshet-t1","device":"d"}}"#,
        invented.formatted()
    );

    // Well-formed, correct checksum, and worthless — the signature is what
    // matters and only the issuer can produce one.
    let (status, _) = post(&h.state, "/api/activate", &body).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn a_revoked_licence_will_not_activate_on_a_new_machine() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "buyer@example.ca").await;
    h.store.revoke(&sold.key, NOW).await.unwrap();

    let key = freshet_license::LicenceKey::parse(&sold.key).unwrap().formatted();
    let body = format!(r#"{{"key":"{key}","product":"freshet-t1","device":"d"}}"#);

    let (status, _) = post(&h.state, "/api/activate", &body).await;
    assert_eq!(status, StatusCode::GONE);
}

#[tokio::test]
async fn a_t1_key_does_not_activate_a_future_t2_product() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "buyer@example.ca").await;
    let key = freshet_license::LicenceKey::parse(&sold.key).unwrap().formatted();

    let body = format!(r#"{{"key":"{key}","product":"freshet-t2","device":"d"}}"#);
    let (status, _) = post(&h.state, "/api/activate", &body).await;

    assert_eq!(status, StatusCode::BAD_REQUEST);
}

// -- payment -------------------------------------------------------------

#[tokio::test]
async fn no_licence_is_issued_when_payments_are_not_configured() {
    let h = harness(vec![]);

    let (status, _) = post(
        &h.state,
        "/api/webhook/stripe",
        r#"{"id":"evt_1","type":"checkout.session.completed",
            "data":{"object":{"id":"cs_1","customer_details":{"email":"free@example.ca"}}}}"#,
    )
    .await;

    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert!(h.store.for_email("free@example.ca").await.unwrap().is_empty());
}

#[tokio::test]
async fn an_unsigned_webhook_cannot_mint_itself_a_licence() {
    let mut h = harness(vec![]);
    h.state.stripe_secret = Some("whsec_test".into());

    let (status, _) = post(
        &h.state,
        "/api/webhook/stripe",
        r#"{"id":"evt_1","type":"checkout.session.completed",
            "data":{"object":{"id":"cs_1","customer_details":{"email":"thief@example.ca"}}}}"#,
    )
    .await;

    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(h.store.for_email("thief@example.ca").await.unwrap().is_empty());
}

// -- admin ---------------------------------------------------------------

#[tokio::test]
async fn admin_does_not_exist_until_it_is_configured() {
    let h = harness(vec![]);

    // Not 403 — a 403 would confirm there is an admin area to attack.
    assert_eq!(
        get(&h.state, "/admin/licences?q=buyer", Some("anyone@example.ca")).await,
        StatusCode::NOT_FOUND
    );
}

#[tokio::test]
async fn an_unlisted_caller_cannot_reach_admin() {
    let h = harness(vec!["selva@freshettax.ca".into()]);

    assert_eq!(
        get(&h.state, "/admin/licences?q=buyer", None).await,
        StatusCode::NOT_FOUND
    );
    assert_eq!(
        get(&h.state, "/admin/licences?q=buyer", Some("someone@else.ca")).await,
        StatusCode::NOT_FOUND
    );
}

#[tokio::test]
async fn a_listed_admin_gets_in_and_the_lookup_is_recorded() {
    let h = harness(vec!["selva@freshettax.ca".into()]);
    sell_to(&h, "buyer@example.ca").await;

    let status = get(
        &h.state,
        "/admin/licences?q=buyer",
        Some("accounts.google.com:selva@freshettax.ca"),
    )
    .await;

    assert_eq!(status, StatusCode::OK);

    let trail = h.store.audit_trail();
    assert_eq!(trail.len(), 1, "looking up a customer was not audited");
    assert_eq!(trail[0].0, "selva@freshettax.ca");
    assert_eq!(trail[0].1, "search");
}

// -- public pages --------------------------------------------------------

#[tokio::test]
async fn the_homepage_says_the_product_cannot_file_yet() {
    let h = harness(vec![]);

    let response = router(h.state.clone())
        .oneshot(Request::builder().uri("/").body(Body::empty()).unwrap())
        .await
        .unwrap();

    let bytes = axum::body::to_bytes(response.into_body(), 256 * 1024).await.unwrap();
    let html = String::from_utf8_lossy(&bytes);

    // Selling software that cannot yet file without saying so would be the
    // single most damaging thing this site could do.
    assert!(html.contains("not yet certified by CRA"), "{html}");
}

// -- counting filings ----------------------------------------------------

async fn sell_tier(
    h: &Harness,
    email: &str,
    offer: Offer,
) -> freshet_site::store::IssuedLicence {
    issue(
        h.store.as_ref(),
        &h.signing,
        email,
        &offer,
        LicenceKind::Retail,
        None,
        NOW,
    )
    .await
    .unwrap()
}

fn claim_body(key: &str, filing_ref: &str) -> String {
    let formatted = freshet_license::LicenceKey::parse(key).unwrap().formatted();
    format!(r#"{{"key":"{formatted}","filing_ref":"{filing_ref}"}}"#)
}

#[tokio::test]
async fn a_single_return_licence_is_spent_after_one_filing() {
    let h = harness(vec![]);
    let sold = sell_tier(&h, "owner@example.ca", Offer::corporate_single(0, i64::MAX)).await;

    let (first, body) = post(&h.state, "/api/filings/claim", &claim_body(&sold.key, "ret-1")).await;
    assert_eq!(first, StatusCode::OK);

    let json: serde_json::Value = serde_json::from_str(&body).unwrap();
    assert_eq!(json["used"], 1);
    assert_eq!(json["remaining"], 0);

    // A second, different return has nothing left to spend.
    let (second, _) = post(&h.state, "/api/filings/claim", &claim_body(&sold.key, "ret-2")).await;
    assert_eq!(second, StatusCode::PAYMENT_REQUIRED);
}

/// The failure that would infuriate someone most: losing a return off their
/// allowance because the connection dropped after we counted it.
#[tokio::test]
async fn retrying_the_same_filing_does_not_burn_a_second_slot() {
    let h = harness(vec![]);
    let sold = sell_tier(&h, "owner@example.ca", Offer::corporate_single(0, i64::MAX)).await;

    let body = claim_body(&sold.key, "ret-1");

    let (first, _) = post(&h.state, "/api/filings/claim", &body).await;
    let (retry, retry_body) = post(&h.state, "/api/filings/claim", &body).await;

    assert_eq!(first, StatusCode::OK);
    assert_eq!(retry, StatusCode::OK, "a retry must not look like a failure");

    let json: serde_json::Value = serde_json::from_str(&retry_body).unwrap();
    assert_eq!(json["used"], 1, "the retry consumed a second slot");
    assert_eq!(json["already_counted"], true);
}

#[tokio::test]
async fn a_professional_licence_is_not_counted_at_all() {
    let h = harness(vec![]);
    let sold = sell_tier(
        &h,
        "firm@example.ca",
        Offer::corporate_professional(0, i64::MAX),
    )
    .await;

    for n in 0..50 {
        let (status, body) =
            post(&h.state, "/api/filings/claim", &claim_body(&sold.key, &format!("ret-{n}"))).await;

        assert_eq!(status, StatusCode::OK);
        let json: serde_json::Value = serde_json::from_str(&body).unwrap();
        assert!(json["remaining"].is_null(), "a professional was given a number");
    }

    // And nothing was written per filing, which matters for a firm doing
    // hundreds of returns a season.
    assert_eq!(h.store.filings_used(&sold.key).await.unwrap(), 0);
}

#[tokio::test]
async fn a_household_licence_counts_down_to_its_limit() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "family@example.ca").await;

    for n in 0..5 {
        let (status, body) =
            post(&h.state, "/api/filings/claim", &claim_body(&sold.key, &format!("ret-{n}"))).await;

        assert_eq!(status, StatusCode::OK, "return {n} was refused");
        let json: serde_json::Value = serde_json::from_str(&body).unwrap();
        assert_eq!(json["remaining"], 4 - n);
    }

    let (sixth, _) =
        post(&h.state, "/api/filings/claim", &claim_body(&sold.key, "ret-6")).await;
    assert_eq!(sixth, StatusCode::PAYMENT_REQUIRED);
}

#[tokio::test]
async fn a_revoked_licence_cannot_claim_a_filing() {
    let h = harness(vec![]);
    let sold = sell_to(&h, "family@example.ca").await;
    h.store.revoke(&sold.key, NOW).await.unwrap();

    let (status, _) = post(&h.state, "/api/filings/claim", &claim_body(&sold.key, "ret-1")).await;
    assert_eq!(status, StatusCode::GONE);
}

#[tokio::test]
async fn an_invented_key_cannot_claim_a_filing() {
    let h = harness(vec![]);
    let invented = freshet_license::LicenceKey::from_payload("ZZZZZZZZZZZZZZZZ").unwrap();

    let body = format!(
        r#"{{"key":"{}","filing_ref":"ret-1"}}"#,
        invented.formatted()
    );

    let (status, _) = post(&h.state, "/api/filings/claim", &body).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}
