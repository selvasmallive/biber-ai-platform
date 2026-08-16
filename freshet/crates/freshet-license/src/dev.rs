//! Built-in development and certification licences.
//!
//! # This module must not reach a customer
//!
//! It contains a **private signing key**. Anything that can reach this code can
//! mint licences. That is acceptable only because the key here signs licences
//! that a release build refuses to accept: `verify` trusts the development
//! public key solely when the `dev-licences` feature is on, and the shipped
//! build does not enable it.
//!
//! So there are two independent locks, not one. Extracting this key from a
//! development build yields licences that no release binary will honour, and
//! forgetting to remove a hardcoded key cannot happen because there is no
//! hardcoded key in the release path at all.
//!
//! # Why these exist
//!
//! CRA's certification cycle means transmitting test returns repeatedly for
//! three months. Making that depend on a purchase flow, or on a website that
//! does not exist yet, would be absurd. The certification licence is also a
//! distinct [`LicenceKind`], so a return filed during testing is
//! distinguishable from a customer's afterwards.

use ed25519_dalek::SigningKey;

use crate::{sign, Allowance, Coverage, Licence, LicenceKey, LicenceKind, PAYLOAD_VERSION};

/// Fixed so development licences are byte-identical on every machine and in
/// every test run. It is not a secret and is not trying to be.
const DEV_SEED: [u8; 32] = [
    0x46, 0x72, 0x65, 0x73, 0x68, 0x65, 0x74, 0x20, 0x64, 0x65, 0x76, 0x65, 0x6c, 0x6f, 0x70,
    0x6d, 0x65, 0x6e, 0x74, 0x20, 0x6c, 0x69, 0x63, 0x65, 0x6e, 0x63, 0x65, 0x20, 0x6b, 0x65,
    0x79, 0x21,
];

/// Signed at a fixed instant so the tokens never change.
const ISSUED: i64 = 1_767_225_600;

pub fn signing_key() -> SigningKey {
    SigningKey::from_bytes(&DEV_SEED)
}

/// The public half, trusted only when this module is compiled in.
pub fn public_key() -> [u8; 32] {
    signing_key().verifying_key().to_bytes()
}

pub struct BuiltIn {
    pub key: LicenceKey,
    pub token: String,
    pub licence: Licence,
    pub purpose: &'static str,
}

fn build(payload: &str, kind: LicenceKind, licensee: &str, returns: u32, purpose: &'static str) -> BuiltIn {
    let key = LicenceKey::from_payload(payload).expect("built-in payloads are well formed");

    let licence = Licence {
        version: PAYLOAD_VERSION,
        key: key.compact(),
        product: "freshet-t1".into(),
        licensee: licensee.into(),
        kind,
        coverage: Coverage::TaxYears(freshet_supported_years()),
        allowance: Allowance::Returns(returns),
        issued_unix: ISSUED,
        expires_unix: None,
    };

    let token = sign::sign(&licence, &signing_key()).expect("built-in licences sign");

    BuiltIn {
        key,
        token,
        licence,
        purpose,
    }
}

/// Kept here rather than depending on the tax data crate, so licensing has no
/// opinion about tax and vice versa.
fn freshet_supported_years() -> Vec<u16> {
    vec![2025, 2026]
}

/// Every licence this build will accept without contacting anything.
pub fn licences() -> Vec<BuiltIn> {
    vec![
        build(
            "DEV0000000000001",
            LicenceKind::Development,
            "Development build",
            100,
            "Everyday development and manual testing.",
        ),
        build(
            "CERT000000000001",
            LicenceKind::Certification,
            "CRA certification",
            1000,
            "Transmitting CRA certification test returns, without a purchase flow in the way.",
        ),
    ]
}

/// Look up a built-in licence by key.
pub fn find(key: &LicenceKey) -> Option<BuiltIn> {
    licences().into_iter().find(|b| b.key == *key)
}
