//! Minting a licence.
//!
//! This is the only place in the world that can produce something the desktop
//! app will accept, because it is the only place the private key exists. It
//! signs through `freshet_license::sign`, the same function the built-in
//! development licences go through and the exact inverse of what the app
//! verifies with — so a licence that fails in the app is a bug here, not a
//! disagreement between two implementations of the same idea.

use freshet_license::sign::SigningKey;
use freshet_license::{sign, Allowance, Coverage, Licence, LicenceKey, LicenceKind, PAYLOAD_VERSION};
use rand::RngCore;

use crate::store::{IssuedLicence, Store, StoreError};

/// Crockford base32, matching the key alphabet exactly.
const ALPHABET: &[u8] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const PAYLOAD_LEN: usize = 16;

/// What a customer bought.
#[derive(Debug, Clone)]
pub struct Offer {
    pub product: String,
    pub coverage: Coverage,
    pub allowance: Allowance,
    /// Seconds from issue until the licence stops working.
    ///
    /// This is the honest lever against sharing, and it is why the offline
    /// design gives up little: a leaked licence dies at the end of its season,
    /// and tax software is reissued yearly regardless. Enforcement needs no
    /// network because expiry travels inside the signed payload.
    pub lifetime_secs: Option<i64>,
}

/// A generous window. Filing for a year closes well before this, and the
/// remainder covers late returns and amendments without anyone having to think
/// about it.
const SEASON_SECS: i64 = 400 * 24 * 60 * 60;

impl Offer {
    /// The standard T1 household licence.
    ///
    /// Five returns because a household is the unit that justifies charging at
    /// all when a free web filer exists: one purchase covers a spouse, adult
    /// children and a parent.
    pub fn season(tax_year: u16) -> Self {
        Offer {
            product: "freshet-t1".into(),
            coverage: Coverage::TaxYears(vec![tax_year]),
            allowance: Allowance::Returns(5),
            lifetime_secs: Some(SEASON_SECS),
        }
    }

    /// A single corporate return.
    ///
    /// T2 buyers split in two, and this is the owner with exactly one company.
    /// Coverage is a fiscal period range because a corporation with a June
    /// year-end is filing something no calendar year names.
    pub fn corporate_single(from_unix: i64, to_unix: i64) -> Self {
        Offer {
            product: "freshet-t2".into(),
            coverage: Coverage::PeriodsEnding { from_unix, to_unix },
            allowance: Allowance::Returns(1),
            lifetime_secs: Some(SEASON_SECS),
        }
    }

    /// The professional tier: any number of corporate returns in the range.
    pub fn corporate_professional(from_unix: i64, to_unix: i64) -> Self {
        Offer {
            product: "freshet-t2".into(),
            coverage: Coverage::PeriodsEnding { from_unix, to_unix },
            allowance: Allowance::Unlimited,
            lifetime_secs: Some(SEASON_SECS),
        }
    }
}

/// Sixteen characters of OS entropy: eighty bits.
///
/// Masking the low five bits is unbiased *because* the alphabet is exactly 32
/// long — five bits, thirty-two symbols, no remainder to skew. That is a
/// property of this alphabet, not of the technique, so the assertion below
/// fails loudly if anyone ever changes its length.
fn random_payload() -> String {
    const _: () = assert!(
        ALPHABET.len() == 32,
        "masking five bits is only unbiased for a 32-symbol alphabet"
    );

    let mut bytes = [0u8; PAYLOAD_LEN];
    rand::rngs::OsRng.fill_bytes(&mut bytes);

    bytes
        .iter()
        .map(|b| ALPHABET[(b & 0x1f) as usize] as char)
        .collect()
}

#[derive(Debug, thiserror::Error)]
pub enum IssueError {
    #[error("could not mint a licence: {0}")]
    Licence(String),

    #[error("could not record the licence: {0}")]
    Store(String),

    #[error("gave up finding an unused licence key")]
    NoFreeKey,
}

impl From<freshet_license::LicenceError> for IssueError {
    fn from(e: freshet_license::LicenceError) -> Self {
        IssueError::Licence(e.to_string())
    }
}

impl From<StoreError> for IssueError {
    fn from(e: StoreError) -> Self {
        IssueError::Store(e.to_string())
    }
}

/// Issue a licence, store it, and return it ready to email.
///
/// Key collision is handled by retrying rather than by trusting the entropy:
/// 16 base32 characters is 80 bits and a collision will never happen, but
/// "will never happen" is how you get a customer receiving someone else's
/// licence, and the storage layer's uniqueness constraint is the only thing
/// that actually knows.
pub async fn issue(
    store: &dyn Store,
    signing_key: &SigningKey,
    email: &str,
    offer: &Offer,
    kind: LicenceKind,
    order_ref: Option<String>,
    now_unix: i64,
) -> Result<IssuedLicence, IssueError> {
    for _ in 0..8 {
        let key = LicenceKey::from_payload(&random_payload())?;
        let expires_unix = offer.lifetime_secs.map(|s| now_unix + s);

        let licence = Licence {
            version: PAYLOAD_VERSION,
            key: key.compact(),
            product: offer.product.clone(),
            licensee: email.to_string(),
            kind,
            coverage: offer.coverage.clone(),
            allowance: offer.allowance,
            issued_unix: now_unix,
            expires_unix,
        };

        let token = sign(&licence, signing_key)?;

        let record = IssuedLicence {
            key: key.compact(),
            email: email.to_string(),
            token,
            product: offer.product.clone(),
            issued_unix: now_unix,
            expires_unix,
            revoked_unix: None,
            order_ref: order_ref.clone(),
        };

        match store.insert(&record).await {
            Ok(()) => return Ok(record),
            Err(StoreError::DuplicateKey) => continue,
            Err(e) => return Err(e.into()),
        }
    }

    Err(IssueError::NoFreeKey)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::memory::MemoryStore;

    fn signer() -> SigningKey {
        SigningKey::from_bytes(&[7u8; 32])
    }

    #[test]
    fn a_minted_key_is_always_readable_by_the_app() {
        for _ in 0..500 {
            let raw = random_payload();
            let key = LicenceKey::from_payload(&raw).expect("minted an unparseable key");

            // Round-trips through the form a customer sees in an email.
            assert_eq!(LicenceKey::parse(&key.formatted()).unwrap(), key);
        }
    }

    #[test]
    fn minted_keys_do_not_repeat() {
        use std::collections::HashSet;

        let seen: HashSet<String> = (0..2_000).map(|_| random_payload()).collect();
        assert_eq!(seen.len(), 2_000, "the key generator is not random enough");
    }

    #[tokio::test]
    async fn an_issued_licence_verifies_against_the_matching_public_key() {
        let store = MemoryStore::new();
        let key = signer();

        let issued = issue(
            &store,
            &key,
            "buyer@example.ca",
            &Offer::season(2026),
            LicenceKind::Retail,
            Some("order_1".into()),
            1_000_000,
        )
        .await
        .unwrap();

        let public = key.verifying_key().to_bytes();
        let licence = freshet_license::verify_with(&issued.token, &public).unwrap();

        assert_eq!(licence.licensee, "buyer@example.ca");
        assert_eq!(licence.coverage, Coverage::TaxYears(vec![2026]));
        assert_eq!(licence.kind, LicenceKind::Retail);
    }

    #[tokio::test]
    async fn a_licence_signed_here_is_worthless_under_a_different_key() {
        let store = MemoryStore::new();

        let issued = issue(
            &store,
            &signer(),
            "buyer@example.ca",
            &Offer::season(2026),
            LicenceKind::Retail,
            None,
            1_000_000,
        )
        .await
        .unwrap();

        let impostor = SigningKey::from_bytes(&[9u8; 32]).verifying_key().to_bytes();
        assert!(freshet_license::verify_with(&issued.token, &impostor).is_err());
    }

    #[tokio::test]
    async fn a_season_licence_expires_and_says_so_inside_the_signature() {
        let store = MemoryStore::new();
        let key = signer();
        let now = 1_000_000;

        let issued = issue(
            &store,
            &key,
            "buyer@example.ca",
            &Offer::season(2026),
            LicenceKind::Retail,
            None,
            now,
        )
        .await
        .unwrap();

        let public = key.verifying_key().to_bytes();
        let licence = freshet_license::verify_with(&issued.token, &public).unwrap();
        let expiry = licence.expires_unix.expect("a season licence must expire");

        // Enforced offline, by the app, from the signed payload — the server is
        // not consulted and cannot be.
        assert!(licence.check("freshet-t1", &freshet_license::Filing::TaxYear(2026), 0, expiry - 1).granted());

        // Not a cliff edge. A licence that lapsed yesterday still files, so a
        // customer part-way through a late return is not stranded by a date.
        let grace = freshet_license::standing::GRACE_SECS;
        assert!(licence.check("freshet-t1", &freshet_license::Filing::TaxYear(2026), 0, expiry + 1).granted());
        assert!(licence.check("freshet-t1", &freshet_license::Filing::TaxYear(2026), 0, expiry + grace - 1).granted());

        // It does end, though — which is what makes expiry the honest answer
        // to licence sharing rather than a gesture.
        assert!(!licence.check("freshet-t1", &freshet_license::Filing::TaxYear(2026), 0, expiry + grace).granted());
    }

    /// A season licence must outlive its own filing season by a wide margin.
    ///
    /// Someone buying in January to file for the prior year, then amending in
    /// the autumn, is doing something completely normal.
    #[tokio::test]
    async fn a_season_licence_comfortably_outlasts_its_filing_season() {
        let store = MemoryStore::new();
        let key = signer();
        let now = 1_000_000;

        let issued = issue(
            &store, &key, "buyer@example.ca", &Offer::season(2026),
            LicenceKind::Retail, None, now,
        )
        .await
        .unwrap();

        let days = (issued.expires_unix.unwrap() - now) / (24 * 60 * 60);
        assert!(days >= 365, "a season licence lasting {days} days is too short");
    }

    #[tokio::test]
    async fn every_issued_licence_is_recorded_so_it_can_be_resent() {
        let store = MemoryStore::new();

        let issued = issue(
            &store,
            &signer(),
            "  Buyer@Example.CA ",
            &Offer::season(2026),
            LicenceKind::Retail,
            None,
            1_000_000,
        )
        .await
        .unwrap();

        let found = store.for_email("buyer@example.ca").await.unwrap();
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].token, issued.token);
    }
}
