//! The optional activation endpoint.
//!
//! Optional is the important word. A customer who pastes the licence from their
//! email never comes here, and nothing about their ability to file depends on
//! this service being up. This exists for the person who has the key but not
//! the licence — a forwarded receipt, a lost attachment — and for counting
//! devices.
//!
//! Note what the request does not carry: no return data, no taxpayer details,
//! no telemetry. A key, a product, and an opaque device identifier. That is a
//! claim the product makes publicly, so it is worth defending in the type.

use axum::extract::State;
use axum::http::StatusCode;
use axum::Json;
use serde::{Deserialize, Serialize};

use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct ActivateRequest {
    pub key: String,
    pub product: String,
    /// An opaque, app-generated identifier for this installation. Not a serial
    /// number, not a MAC address, not anything that identifies a person — its
    /// only job is to stop a reinstall counting as a second device.
    #[serde(default)]
    pub device: String,
}

#[derive(Debug, Serialize)]
pub struct ActivateResponse {
    pub licence: String,
    pub devices: u32,
}

#[derive(Debug, Serialize)]
pub struct ApiError {
    pub error: String,
}

fn fail(code: StatusCode, message: &str) -> (StatusCode, Json<ApiError>) {
    (code, Json(ApiError { error: message.into() }))
}

pub async fn activate(
    State(state): State<AppState>,
    Json(req): Json<ActivateRequest>,
) -> Result<Json<ActivateResponse>, (StatusCode, Json<ApiError>)> {
    // Parse before looking anything up: a typo is caught by arithmetic, and
    // an unparseable key should not become a database query.
    let key = freshet_license::LicenceKey::parse(&req.key)
        .map_err(|e| fail(StatusCode::BAD_REQUEST, &e.to_string()))?;

    let record = state
        .store
        .by_key(&key.compact())
        .await
        .map_err(|e| fail(StatusCode::INTERNAL_SERVER_ERROR, &e.to_string()))?
        .ok_or_else(|| fail(StatusCode::NOT_FOUND, "no such licence key"))?;

    if record.product != req.product {
        return Err(fail(
            StatusCode::BAD_REQUEST,
            "that key is for a different product",
        ));
    }

    if record.is_revoked() {
        return Err(fail(StatusCode::GONE, "this licence was withdrawn"));
    }

    // A blank device identifier would make every activation look like the same
    // machine, quietly turning the device count into a constant 1.
    let device = req.device.trim();
    if device.is_empty() {
        return Err(fail(StatusCode::BAD_REQUEST, "no device identifier"));
    }

    let devices = state
        .store
        .record_activation(&record.key, device, state.clock.now())
        .await
        .map_err(|e| fail(StatusCode::INTERNAL_SERVER_ERROR, &e.to_string()))?;

    Ok(Json(ActivateResponse {
        licence: record.token,
        devices,
    }))
}
