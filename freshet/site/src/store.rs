//! What the service remembers.
//!
//! Deliberately little. The desktop product holds no personal data at all, and
//! the temptation is to let the website quietly become the place that does.
//! PIPEDA applies to everything kept here, so the rule is: an email address to
//! deliver to, a licence to deliver, and the timestamps needed to answer "did
//! this arrive?" — nothing else. Names, addresses and card details stay with
//! the payment processor, which is already obliged to hold them.

use async_trait::async_trait;

pub mod memory;
pub mod postgres;

#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("that licence key already exists")]
    DuplicateKey,

    #[error("storage failed: {0}")]
    Backend(String),
}

pub type Result<T> = std::result::Result<T, StoreError>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IssuedLicence {
    /// Compact form, `FRSH…`, as the canonical identifier.
    pub key: String,
    pub email: String,
    /// The signed token. Storing it means a resend is a lookup, not a re-sign —
    /// so a customer's licence is byte-identical every time they ask for it.
    pub token: String,
    pub product: String,
    pub issued_unix: i64,
    pub expires_unix: Option<i64>,
    pub revoked_unix: Option<i64>,
    /// The payment processor's reference. The only link back to a real order,
    /// and the only reason to keep anything at all.
    pub order_ref: Option<String>,
}

impl IssuedLicence {
    pub fn is_revoked(&self) -> bool {
        self.revoked_unix.is_some()
    }
}

#[async_trait]
pub trait Store: Send + Sync {
    async fn insert(&self, licence: &IssuedLicence) -> Result<()>;
    async fn by_key(&self, key: &str) -> Result<Option<IssuedLicence>>;

    /// Every licence for an address, for the "send it to me again" path.
    async fn for_email(&self, email: &str) -> Result<Vec<IssuedLicence>>;

    async fn revoke(&self, key: &str, at_unix: i64) -> Result<bool>;

    /// Record an activation and return how many distinct devices have now
    /// activated this licence. The count is the whole point of activation
    /// existing at all.
    async fn record_activation(&self, key: &str, device: &str, at_unix: i64) -> Result<u32>;

    /// Has this payment event been handled already? Processors retry, and
    /// issuing two licences for one purchase is a support problem in both
    /// directions.
    async fn claim_event(&self, event_id: &str, at_unix: i64) -> Result<bool>;

    /// Whether another recovery email may be sent to this address now.
    ///
    /// Enforced in storage rather than in process memory because Cloud Run runs
    /// many instances: an in-process counter would let an attacker get one
    /// attempt per instance, which is not a rate limit.
    async fn recovery_permitted(
        &self,
        email: &str,
        now_unix: i64,
        window_secs: i64,
        max_in_window: i64,
    ) -> Result<bool>;

    /// Claim one filing slot against a licence, returning how many are now
    /// used. `None` means this exact filing was already counted.
    ///
    /// Keyed by a caller-supplied filing reference so a retry after a dropped
    /// connection does not burn a second slot. Someone whose network died
    /// mid-transmission must not lose a return off their allowance for it.
    async fn claim_filing(
        &self,
        key: &str,
        filing_ref: &str,
        at_unix: i64,
    ) -> Result<Option<u32>>;

    /// How many filings have been counted against a licence.
    async fn filings_used(&self, key: &str) -> Result<u32>;

    async fn search(&self, needle: &str, limit: i64) -> Result<Vec<IssuedLicence>>;

    /// Who looked at what. Support staff can see customer email addresses, so
    /// the looking is itself worth a record.
    async fn audit(&self, who: &str, action: &str, subject: &str, at_unix: i64) -> Result<()>;

    /// Erase everything held for an address, for a PIPEDA deletion request.
    /// Returns how many rows went.
    async fn forget_email(&self, email: &str) -> Result<u64>;
}

/// Addresses are compared case-insensitively and trimmed, everywhere, once.
///
/// Doing this at the boundary rather than per-query is what stops
/// `Selva@…` recovering a licence that `selva@…` bought — or, worse, failing to.
pub fn normalise_email(raw: &str) -> String {
    raw.trim().to_ascii_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn addresses_are_compared_without_case_or_whitespace_tripping_people_up() {
        assert_eq!(normalise_email("  Selva@Freshettax.CA \n"), "selva@freshettax.ca");
    }
}
