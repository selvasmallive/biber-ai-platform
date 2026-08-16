//! Signing and offline verification.
//!
//! A licence is a JSON payload and an Ed25519 signature over it, joined by a
//! dot and base64url-encoded so it survives an email intact. Verification needs
//! only the public key compiled into the binary — no network, no clock skew, no
//! dependency on our servers during the eight weeks of the year when everyone
//! is filing at once.

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine as _;
use ed25519_dalek::{Signature, Signer, Verifier, VerifyingKey};

/// Re-exported so the activation service signs with exactly this crate's
/// notion of a key. An issuer that constructed its own would be free to drift.
pub use ed25519_dalek::SigningKey;

use crate::{Licence, LicenceError};

/// The public key licences are verified against in a shipped build.
///
/// Generated 2026-08-16. The private half exists only in Secret Manager and
/// nowhere in this repository, which is why nothing here can mint a retail
/// licence.
///
/// **Changing this invalidates every licence ever issued**, because the public
/// half is compiled into each installed copy. It is not a value to rotate
/// casually — treat it as fixed for the life of the product.
pub const PRODUCTION_PUBLIC_KEY: [u8; 32] = [
    0xb9, 0xfc, 0xe8, 0x1f, 0x45, 0xcc, 0xe5, 0x84,
    0x9a, 0x7d, 0x14, 0x52, 0x12, 0x56, 0x49, 0x89,
    0x41, 0x20, 0x6a, 0x80, 0x7d, 0x80, 0xc4, 0x1e,
    0xfd, 0x42, 0x1b, 0xad, 0xaf, 0x1c, 0x5f, 0xc3,
];

fn is_placeholder(key: &[u8; 32]) -> bool {
    key.iter().all(|b| *b == 0)
}

/// Serialize the payload exactly as it will be signed.
///
/// Signing and verification must agree byte for byte, so both go through this
/// one function rather than each serializing for themselves.
fn canonical(licence: &Licence) -> Result<Vec<u8>, LicenceError> {
    serde_json::to_vec(licence).map_err(|e| LicenceError::Malformed(e.to_string()))
}

/// Produce a signed licence token. Used by the activation server and by the
/// built-in development licences; never by the app itself.
pub fn sign(licence: &Licence, signing_key: &SigningKey) -> Result<String, LicenceError> {
    let body = canonical(licence)?;
    let sig = signing_key.sign(&body);

    Ok(format!(
        "{}.{}",
        URL_SAFE_NO_PAD.encode(&body),
        URL_SAFE_NO_PAD.encode(sig.to_bytes())
    ))
}

/// Verify a token against a specific public key.
pub fn verify_with(token: &str, public_key: &[u8; 32]) -> Result<Licence, LicenceError> {
    if is_placeholder(public_key) {
        return Err(LicenceError::NoSigningKeyConfigured);
    }

    let (body_b64, sig_b64) = token
        .trim()
        .split_once('.')
        .ok_or_else(|| LicenceError::Malformed("a licence has two dot-separated parts".into()))?;

    let body = URL_SAFE_NO_PAD
        .decode(body_b64)
        .map_err(|_| LicenceError::Malformed("the licence body is not valid base64".into()))?;
    let sig_bytes = URL_SAFE_NO_PAD
        .decode(sig_b64)
        .map_err(|_| LicenceError::Malformed("the signature is not valid base64".into()))?;

    let sig_bytes: [u8; 64] = sig_bytes
        .try_into()
        .map_err(|_| LicenceError::Malformed("the signature is the wrong length".into()))?;

    let verifying = VerifyingKey::from_bytes(public_key)
        .map_err(|e| LicenceError::Malformed(format!("bad public key: {e}")))?;

    verifying
        .verify(&body, &Signature::from_bytes(&sig_bytes))
        .map_err(|_| LicenceError::BadSignature)?;

    // Parse only after the signature holds, so malformed input from an
    // unverified source never reaches the deserializer.
    serde_json::from_slice(&body).map_err(|e| LicenceError::Malformed(e.to_string()))
}

/// Verify against the keys this build trusts.
///
/// In a development build that also includes the development key, so the
/// built-in test and certification licences work. A release build trusts the
/// production key alone.
pub fn verify(token: &str) -> Result<Licence, LicenceError> {
    let production = verify_with(token, &PRODUCTION_PUBLIC_KEY);

    #[cfg(feature = "dev-licences")]
    if production.is_err() {
        return verify_with(token, &crate::dev::public_key());
    }

    production
}
