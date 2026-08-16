//! Support tooling.
//!
//! # Where the authentication actually is
//!
//! Not here. These routes trust `X-Goog-Authenticated-User-Email`, a header set
//! by Identity-Aware Proxy — and a header anyone can send if they can reach the
//! service directly. **The load balancer is the security boundary**, and the
//! deploy must set `--ingress internal-and-cloud-load-balancing` so that direct
//! Cloud Run URLs cannot be used at all. Without that, this is unauthenticated.
//!
//! That is a deliberate trade rather than laziness: the alternative is the site
//! storing admin passwords, and a licensing service that never holds a password
//! cannot leak one. The allowlist below is defence in depth, not the gate.
//!
//! Admin is **off** unless `ADMIN_EMAILS` is set, so a service that has not been
//! put behind IAP yet has no admin surface to find.

use axum::extract::{Path, Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::{Html, IntoResponse, Response};
use serde::Deserialize;

use crate::AppState;

/// IAP prefixes the address with `accounts.google.com:`.
fn caller(headers: &HeaderMap) -> Option<String> {
    let raw = headers
        .get("x-goog-authenticated-user-email")?
        .to_str()
        .ok()?;

    Some(
        raw.rsplit_once(':')
            .map(|(_, e)| e)
            .unwrap_or(raw)
            .trim()
            .to_ascii_lowercase(),
    )
}

/// Who is asking, if they are allowed to ask at all.
///
/// Returns 404 rather than 403 for an unknown caller: a 403 confirms the admin
/// area exists, and there is nothing to gain from telling someone that.
fn authorise(state: &AppState, headers: &HeaderMap) -> Result<String, Response> {
    let denied = || StatusCode::NOT_FOUND.into_response();

    if state.admin_emails.is_empty() {
        return Err(denied());
    }

    match caller(headers) {
        Some(email) if state.admin_emails.contains(&email) => Ok(email),
        _ => Err(denied()),
    }
}

fn escape(raw: &str) -> String {
    raw.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

#[derive(Debug, Deserialize)]
pub struct Search {
    #[serde(default)]
    pub q: String,
}

pub async fn licences(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(search): Query<Search>,
) -> Response {
    let who = match authorise(&state, &headers) {
        Ok(w) => w,
        Err(r) => return r,
    };

    if search.q.trim().is_empty() {
        return Html(page("Search for an address, key or order reference.", "")).into_response();
    }

    // Recorded before the results are shown: looking up a customer is itself
    // access to personal data, and the log is what makes that reviewable.
    let _ = state
        .store
        .audit(&who, "search", search.q.trim(), state.clock.now())
        .await;

    let found = match state.store.search(search.q.trim(), 50).await {
        Ok(f) => f,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    };

    let rows: String = found
        .iter()
        .map(|l| {
            let key = freshet_license::LicenceKey::parse(&l.key)
                .map(|k| k.formatted())
                .unwrap_or_else(|_| l.key.clone());

            format!(
                "<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td>
                 <td><form method=\"post\" action=\"/admin/licences/{}/revoke\">
                 <button{}>Revoke</button></form></td></tr>",
                escape(&key),
                escape(&l.email),
                escape(&l.product),
                if l.is_revoked() { "revoked" } else { "active" },
                escape(&l.key),
                if l.is_revoked() { " disabled" } else { "" },
            )
        })
        .collect();

    Html(page(
        &format!("{} result(s)", found.len()),
        &format!(
            "<table><tr><th>Key</th><th>Email</th><th>Product</th><th>State</th><th></th></tr>{rows}</table>"
        ),
    ))
    .into_response()
}

pub async fn revoke(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(key): Path<String>,
) -> Response {
    let who = match authorise(&state, &headers) {
        Ok(w) => w,
        Err(r) => return r,
    };

    let changed = state.store.revoke(&key, state.clock.now()).await;
    let _ = state
        .store
        .audit(&who, "revoke", &key, state.clock.now())
        .await;

    match changed {
        Ok(true) => Html(page(
            "Revoked.",
            "<p>Because verification is offline, a machine that already holds \
             this licence keeps working until it expires. Revocation stops \
             future activations and recovery emails — it is not a kill switch, \
             and it was never designed to be one.</p>",
        ))
        .into_response(),
        Ok(false) => Html(page("Nothing changed — already revoked, or no such key.", "")).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

/// Erase everything held for an address, for a PIPEDA deletion request.
pub async fn forget(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(email): Path<String>,
) -> Response {
    let who = match authorise(&state, &headers) {
        Ok(w) => w,
        Err(r) => return r,
    };

    let gone = state.store.forget_email(&email).await;
    let _ = state
        .store
        .audit(&who, "forget", &email, state.clock.now())
        .await;

    match gone {
        Ok(n) => Html(page(
            &format!("Deleted {n} licence record(s)."),
            "<p>Their licences will no longer activate or be recoverable. Copies \
             already installed keep working, because they verify offline.</p>",
        ))
        .into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response(),
    }
}

fn page(heading: &str, body: &str) -> String {
    format!(
        "<!doctype html><meta charset=utf-8><title>Freshet admin</title>
         <style>body{{font:15px/1.5 system-ui;margin:2rem;max-width:60rem}}
         table{{border-collapse:collapse;width:100%}}
         td,th{{border-bottom:1px solid #ddd;padding:.4rem;text-align:left}}
         code{{font-size:13px}}</style>
         <h1>Freshet admin</h1>
         <form method=get action=/admin/licences>
           <input name=q placeholder=\"email, key or order\" size=40>
           <button>Search</button>
         </form>
         <p>{}</p>{}",
        escape(heading),
        body
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn headers(email: &str) -> HeaderMap {
        let mut h = HeaderMap::new();
        h.insert(
            "x-goog-authenticated-user-email",
            email.parse().unwrap(),
        );
        h
    }

    #[test]
    fn the_iap_prefix_is_stripped_and_case_is_ignored() {
        let h = headers("accounts.google.com:Selva@Freshettax.CA");
        assert_eq!(caller(&h).unwrap(), "selva@freshettax.ca");
    }

    #[test]
    fn an_address_without_the_prefix_still_reads() {
        let h = headers("selva@freshettax.ca");
        assert_eq!(caller(&h).unwrap(), "selva@freshettax.ca");
    }

    #[test]
    fn html_from_a_customer_record_cannot_become_markup() {
        let nasty = "<script>alert(1)</script>\"";
        let out = escape(nasty);

        assert!(!out.contains('<'), "{out}");
        assert!(!out.contains('"'), "{out}");
    }
}
