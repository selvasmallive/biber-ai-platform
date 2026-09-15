//! The Freshet licence service.
//!
//! It sells licences, delivers them, resends them when they are lost, and lets
//! support look them up. What it deliberately is **not** is a dependency of the
//! desktop app: a customer with their licence in hand can file whether or not
//! any of this is running, which is the property the whole design protects.

pub mod config;
pub mod issue;
pub mod mail;
pub mod routes;
pub mod store;

use std::sync::Arc;

use axum::routing::{get, post};
use axum::Router;
use freshet_license::sign::SigningKey;

use crate::mail::Mailer;
use crate::store::Store;

/// Time, injectable.
///
/// Signature freshness, rate-limit windows and licence expiry all depend on
/// "now", and a service whose security properties depend on the wall clock
/// should be testable without waiting for it.
pub trait Clock: Send + Sync {
    fn now(&self) -> i64;
}

pub struct SystemClock;

impl Clock for SystemClock {
    fn now(&self) -> i64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0)
    }
}

#[derive(Clone)]
pub struct AppState {
    pub store: Arc<dyn Store>,
    pub mailer: Arc<dyn Mailer>,
    pub clock: Arc<dyn Clock>,
    pub signing_key: Arc<SigningKey>,
    pub stripe_secret: Option<String>,
    pub admin_emails: Vec<String>,
    /// Which tax year a purchase today entitles the buyer to file.
    pub sale_year: u16,
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/", get(routes::pages::home))
        .route("/recover", get(routes::pages::recover_form))
        .route("/privacy", get(routes::pages::privacy))
        .route("/healthz", get(routes::pages::health))
        .route("/api/activate", post(routes::activate::activate))
        .route("/api/recover", post(routes::recover::recover))
        .route("/api/recover-form", post(routes::recover::recover_form))
        .route("/api/webhook/stripe", post(routes::checkout::stripe_webhook))
        .route("/api/filings/claim", post(routes::filing::claim))
        .route("/api/web/file", post(routes::web::file))
        .route("/admin/licences", get(routes::admin::licences))
        .route("/admin/licences/{key}/revoke", post(routes::admin::revoke))
        .route("/admin/customers/{email}/forget", post(routes::admin::forget))
        // A licence is a couple of hundred bytes and a webhook a few kilobytes.
        // Anything larger is not a request this service has any business
        // buffering.
        .layer(tower_http::limit::RequestBodyLimitLayer::new(64 * 1024))
        .layer(tower_http::trace::TraceLayer::new_for_http())
        .with_state(state)
}
