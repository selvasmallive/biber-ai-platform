//! Licensing.
//!
//! Freshet prepares a return for nothing. Filing it needs a licence, and this
//! crate is the whole of that decision.
//!
//! The shape is **one-time activation, then offline forever**. The key a
//! customer is emailed is exchanged once with the activation service for a
//! signed licence, which the app then verifies against a compiled-in public key
//! with no network at all. That matters more here than in most products for two
//! reasons: the entire pitch is that a return never leaves the machine, and the
//! eight weeks when every customer files at once are the eight weeks when an
//! outage would be least forgivable. A licence check that phones home would put
//! our uptime between a person and their filing deadline.
//!
//! Forgery is prevented by the signature, not by the key format. Anyone can
//! invent a well-formed key; only a signed licence unlocks anything.

pub mod activation;
pub mod credential;
pub mod key;
pub mod scope;
pub mod sign;
pub mod standing;

#[cfg(feature = "dev-licences")]
pub mod dev;

pub use activation::{Activation, WebActivation};
pub use credential::Credential;
pub use key::LicenceKey;
pub use scope::{Allowance, Coverage, Filing};
pub use standing::{standing, Standing};
pub use sign::{sign, verify, verify_with};

use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum LicenceError {
    #[error("{0}")]
    MalformedKey(String),

    #[error("this licence is not readable: {0}")]
    Malformed(String),

    #[error("this licence was not issued by Freshet")]
    BadSignature,

    #[error(
        "this build has no licensing key compiled into it, so no licence can be \
         accepted. Generate a signing keypair and set PRODUCTION_PUBLIC_KEY."
    )]
    NoSigningKeyConfigured,

    #[error(
        "licence activation is not available yet: the activation service has not \
         been built. A development licence can be used in the meantime."
    )]
    ActivationUnavailable,

    #[error(
        "that is a licence key, not a licence. Freshet does not contact any \
         server on its own: paste the licence from your purchase email, open the \
         licence file it came with, or tick \"verify this key online\" to let \
         Freshet exchange the key for you."
    )]
    KeyNeedsActivation,

    #[error("the activation service rejected this key: {0}")]
    Rejected(String),

    #[error("could not reach the activation service: {0}")]
    Unreachable(String),
}

/// What a licence was issued for. Kept on the licence so that a return filed
/// under a development or certification licence is distinguishable afterwards —
/// during CRA testing that distinction is the point.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LicenceKind {
    /// Sold to a customer.
    Retail,
    /// Internal development and testing. Never valid in a release build.
    Development,
    /// Issued for a CRA certification cycle. Never valid in a release build.
    Certification,
}

impl LicenceKind {
    /// Whether returns filed under this licence are real customer filings.
    pub fn is_production(self) -> bool {
        matches!(self, LicenceKind::Retail)
    }

    pub fn label(self) -> &'static str {
        match self {
            LicenceKind::Retail => "Licensed",
            LicenceKind::Development => "Development licence",
            LicenceKind::Certification => "CRA certification licence",
        }
    }
}

/// The payload format this build writes.
///
/// Every change to [`Licence`] alters the bytes that get signed and therefore
/// invalidates every licence already issued. This number is what makes the
/// *next* such change survivable: a licence stamped with a version this build
/// does not know is refused with "update Freshet", not with "invalid licence".
pub const PAYLOAD_VERSION: u8 = 1;

/// The signed payload.
///
/// Field names and order are part of the signature, because signing and
/// verification serialize through the same function. **Changing anything here
/// invalidates every licence ever issued** — safe only while none have been.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Licence {
    /// First field so it is always readable, whatever else changes.
    pub version: u8,
    /// The key this licence was issued against, in compact form.
    pub key: String,
    /// Which product. A T1 licence must not unlock a future T2 product.
    pub product: String,
    /// Shown in the app so a person can see which of their licences this is.
    pub licensee: String,
    pub kind: LicenceKind,
    /// Calendar tax years for a T1; fiscal period range for a T2.
    pub coverage: Coverage,
    /// A fixed number of returns, or unlimited for the professional tier.
    pub allowance: Allowance,
    pub issued_unix: i64,
    /// `None` never expires.
    pub expires_unix: Option<i64>,
}

/// Whether a licence permits a particular filing, and if not, why not.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Entitlement {
    Granted,
    Expired { expired_unix: i64 },
    WrongProduct { licensed_for: String },
    NotCovered { covered: Coverage },
    ReturnLimitReached { max_returns: u32 },

    /// Issued by a newer Freshet than this one.
    ///
    /// A separate outcome from "invalid" on purpose. Telling someone their
    /// valid, paid-for licence is invalid — when the real answer is that their
    /// app is old — sends them to support instead of to the update button.
    NewerThanThisBuild { version: u8 },
}

impl Entitlement {
    pub fn granted(&self) -> bool {
        matches!(self, Entitlement::Granted)
    }

    /// Why filing is blocked, in the words the app should show.
    pub fn explain(&self) -> String {
        match self {
            Entitlement::Granted => "Licensed to file.".into(),
            Entitlement::Expired { .. } => standing::describe(standing::Standing::Ended)
                .unwrap_or_else(|| "This licence has ended.".into()),
            Entitlement::WrongProduct { licensed_for } => {
                format!("This licence is for {licensed_for}, not this product.")
            }
            Entitlement::NotCovered { covered } => format!(
                "This licence covers {}. Filing outside that needs a licence for it.",
                covered.describe()
            ),
            Entitlement::ReturnLimitReached { max_returns } => format!(
                "This licence covers {max_returns} returns and they have all been filed."
            ),
            Entitlement::NewerThanThisBuild { .. } => {
                "This licence was issued for a newer version of Freshet. Update \
                 Freshet and it will work — there is nothing wrong with the licence."
                    .into()
            }
        }
    }
}

impl Licence {
    /// Decide whether this licence permits filing a given return.
    ///
    /// `already_filed` is how many returns have been transmitted under it, so
    /// the caller owns that count rather than the licence pretending to know.
    pub fn check(
        &self,
        product: &str,
        filing: &Filing,
        already_filed: u32,
        now_unix: i64,
    ) -> Entitlement {
        // Before anything else. A payload from the future may mean things by
        // these fields that this build does not, so acting on them would be
        // guessing — and guessing about entitlement is how someone gets told
        // their real licence is fake.
        if self.version > PAYLOAD_VERSION {
            return Entitlement::NewerThanThisBuild {
                version: self.version,
            };
        }

        if self.product != product {
            return Entitlement::WrongProduct {
                licensed_for: self.product.clone(),
            };
        }

        // Expiry goes through `standing`, so the grace period and the clock
        // tolerance are applied here exactly as the UI describes them. Two
        // places deciding what "expired" means is how software ends up
        // refusing to file while the screen says everything is fine.
        if !standing::standing(self.issued_unix, self.expires_unix, now_unix).permits_filing() {
            return Entitlement::Expired {
                expired_unix: self.expires_unix.unwrap_or(now_unix),
            };
        }

        if !self.coverage.covers(filing) {
            return Entitlement::NotCovered {
                covered: self.coverage.clone(),
            };
        }

        // Only a counted allowance can be exhausted; `Unlimited` never reaches
        // here, which is why matching it is unreachable rather than a case to
        // invent a number for.
        if let Allowance::Returns(max) = self.allowance {
            if !self.allowance.permits(already_filed) {
                return Entitlement::ReturnLimitReached { max_returns: max };
            }
        }

        Entitlement::Granted
    }

    /// Whether filing under this licence requires the count to be confirmed by
    /// the issuer rather than trusted from this machine.
    ///
    /// Checked at transmission, where the network is already required.
    pub fn needs_authoritative_count(&self) -> bool {
        self.allowance.needs_authoritative_count()
    }
}
