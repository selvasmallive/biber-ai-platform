//! The activation boundary.
//!
//! Exchanging a key for a signed licence is the *only* moment the app talks to
//! our servers, and it happens once. Everything after is offline. This trait is
//! where the website plugs in, and it is deliberately the same shape as the CRA
//! transport seam elsewhere in the codebase: the thing that does not exist yet
//! fails loudly rather than silently doing nothing.

use crate::{LicenceError, LicenceKey};

pub trait Activation {
    /// Shown to the user so they know what is being contacted.
    fn label(&self) -> String;

    /// Exchange a key for a signed licence token.
    fn activate(&self, key: &LicenceKey) -> Result<String, LicenceError>;
}

/// The real activation service.
///
/// **Not implemented — the website does not exist yet.** When it does, this
/// becomes a single POST:
///
/// ```text
/// POST {base_url}/api/activate
/// { "key": "FRSH...", "product": "freshet-t1" }
///
/// 200 { "licence": "<base64 payload>.<base64 signature>" }
/// 404 { "error": "no such key" }
/// 409 { "error": "already activated on the maximum number of devices" }
/// ```
///
/// The response is signed by the private half of the production keypair, which
/// lives on the activation server and nowhere else. Nothing in this repository
/// can mint a retail licence, which is the point.
///
/// Note what is deliberately *absent*: no return data, no taxpayer details, no
/// telemetry. The request carries a key and a product name.
pub struct WebActivation {
    pub base_url: String,
}

impl Activation for WebActivation {
    fn label(&self) -> String {
        format!("Freshet activation ({})", self.base_url)
    }

    fn activate(&self, _key: &LicenceKey) -> Result<String, LicenceError> {
        Err(LicenceError::ActivationUnavailable)
    }
}

/// Activation from a licence token the user already holds — pasted from an
/// email, or restored from a backup.
///
/// This path needs no server at all, which makes it the fallback if activation
/// is ever unreachable and the reason an outage can never strand a paying
/// customer at their filing deadline.
pub struct PastedLicence {
    pub token: String,
}

impl Activation for PastedLicence {
    fn label(&self) -> String {
        "Licence pasted directly".to_string()
    }

    fn activate(&self, _key: &LicenceKey) -> Result<String, LicenceError> {
        Ok(self.token.clone())
    }
}
