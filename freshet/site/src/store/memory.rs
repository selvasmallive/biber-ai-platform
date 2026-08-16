//! An in-memory store.
//!
//! Not a toy: it is what the whole test suite runs against, so every rule the
//! service enforces — replay protection, rate limiting, revocation, activation
//! counting — is exercised here without a database anywhere near CI. The
//! Postgres implementation then has to agree with it, which is a much easier
//! thing to check than a service tested only end to end.

use std::collections::HashMap;
use std::sync::Mutex;

use async_trait::async_trait;

use super::{normalise_email, IssuedLicence, Result, Store, StoreError};

#[derive(Default)]
struct Inner {
    licences: Vec<IssuedLicence>,
    activations: HashMap<String, Vec<String>>,
    events: HashMap<String, i64>,
    recoveries: Vec<(String, i64)>,
    filings: HashMap<String, Vec<String>>,
    audits: Vec<(String, String, String, i64)>,
}

#[derive(Default)]
pub struct MemoryStore {
    inner: Mutex<Inner>,
}

impl MemoryStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn audit_trail(&self) -> Vec<(String, String, String, i64)> {
        self.inner.lock().unwrap().audits.clone()
    }
}

#[async_trait]
impl Store for MemoryStore {
    async fn insert(&self, licence: &IssuedLicence) -> Result<()> {
        let mut inner = self.inner.lock().unwrap();

        if inner.licences.iter().any(|l| l.key == licence.key) {
            return Err(StoreError::DuplicateKey);
        }

        let mut stored = licence.clone();
        stored.email = normalise_email(&stored.email);
        inner.licences.push(stored);
        Ok(())
    }

    async fn by_key(&self, key: &str) -> Result<Option<IssuedLicence>> {
        let inner = self.inner.lock().unwrap();
        Ok(inner.licences.iter().find(|l| l.key == key).cloned())
    }

    async fn for_email(&self, email: &str) -> Result<Vec<IssuedLicence>> {
        let wanted = normalise_email(email);
        let inner = self.inner.lock().unwrap();

        Ok(inner
            .licences
            .iter()
            .filter(|l| l.email == wanted)
            .cloned()
            .collect())
    }

    async fn revoke(&self, key: &str, at_unix: i64) -> Result<bool> {
        let mut inner = self.inner.lock().unwrap();

        match inner.licences.iter_mut().find(|l| l.key == key) {
            Some(l) if l.revoked_unix.is_none() => {
                l.revoked_unix = Some(at_unix);
                Ok(true)
            }
            _ => Ok(false),
        }
    }

    async fn record_activation(&self, key: &str, device: &str, _at_unix: i64) -> Result<u32> {
        let mut inner = self.inner.lock().unwrap();
        let seen = inner.activations.entry(key.to_string()).or_default();

        // Reactivating the same machine is not a second device. Anything else
        // would punish a reinstall, which is a normal thing people do.
        if !seen.iter().any(|d| d == device) {
            seen.push(device.to_string());
        }

        Ok(seen.len() as u32)
    }

    async fn claim_event(&self, event_id: &str, at_unix: i64) -> Result<bool> {
        let mut inner = self.inner.lock().unwrap();

        if inner.events.contains_key(event_id) {
            return Ok(false);
        }

        inner.events.insert(event_id.to_string(), at_unix);
        Ok(true)
    }

    async fn recovery_permitted(
        &self,
        email: &str,
        now_unix: i64,
        window_secs: i64,
        max_in_window: i64,
    ) -> Result<bool> {
        let wanted = normalise_email(email);
        let mut inner = self.inner.lock().unwrap();

        let since = now_unix - window_secs;
        inner.recoveries.retain(|(_, at)| *at > since);

        let recent = inner
            .recoveries
            .iter()
            .filter(|(e, _)| *e == wanted)
            .count() as i64;

        if recent >= max_in_window {
            return Ok(false);
        }

        inner.recoveries.push((wanted, now_unix));
        Ok(true)
    }

    async fn claim_filing(
        &self,
        key: &str,
        filing_ref: &str,
        _at_unix: i64,
    ) -> Result<Option<u32>> {
        let mut inner = self.inner.lock().unwrap();
        let seen = inner.filings.entry(key.to_string()).or_default();

        if seen.iter().any(|r| r == filing_ref) {
            return Ok(None);
        }

        seen.push(filing_ref.to_string());
        Ok(Some(seen.len() as u32))
    }

    async fn filings_used(&self, key: &str) -> Result<u32> {
        let inner = self.inner.lock().unwrap();
        Ok(inner.filings.get(key).map(|f| f.len() as u32).unwrap_or(0))
    }

    async fn search(&self, needle: &str, limit: i64) -> Result<Vec<IssuedLicence>> {
        let needle = needle.trim().to_ascii_lowercase();
        let inner = self.inner.lock().unwrap();

        Ok(inner
            .licences
            .iter()
            .filter(|l| {
                l.email.contains(&needle)
                    || l.key.to_ascii_lowercase().contains(&needle)
                    || l
                        .order_ref
                        .as_deref()
                        .is_some_and(|o| o.to_ascii_lowercase().contains(&needle))
            })
            .take(limit.max(0) as usize)
            .cloned()
            .collect())
    }

    async fn audit(&self, who: &str, action: &str, subject: &str, at_unix: i64) -> Result<()> {
        self.inner.lock().unwrap().audits.push((
            who.to_string(),
            action.to_string(),
            subject.to_string(),
            at_unix,
        ));
        Ok(())
    }

    async fn forget_email(&self, email: &str) -> Result<u64> {
        let wanted = normalise_email(email);
        let mut inner = self.inner.lock().unwrap();

        let before = inner.licences.len();
        let doomed: Vec<String> = inner
            .licences
            .iter()
            .filter(|l| l.email == wanted)
            .map(|l| l.key.clone())
            .collect();

        inner.licences.retain(|l| l.email != wanted);
        for key in doomed {
            inner.activations.remove(&key);
            inner.filings.remove(&key);
        }
        inner.recoveries.retain(|(e, _)| *e != wanted);

        Ok((before - inner.licences.len()) as u64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn licence(key: &str, email: &str) -> IssuedLicence {
        IssuedLicence {
            key: key.into(),
            email: email.into(),
            token: "payload.signature".into(),
            product: "freshet-t1".into(),
            issued_unix: 1_000,
            expires_unix: None,
            revoked_unix: None,
            order_ref: Some("order_1".into()),
        }
    }

    #[tokio::test]
    async fn the_same_key_cannot_be_issued_twice() {
        let s = MemoryStore::new();
        s.insert(&licence("FRSHAAAA", "a@b.ca")).await.unwrap();

        assert!(matches!(
            s.insert(&licence("FRSHAAAA", "other@b.ca")).await,
            Err(StoreError::DuplicateKey)
        ));
    }

    #[tokio::test]
    async fn an_address_is_found_however_it_was_typed() {
        let s = MemoryStore::new();
        s.insert(&licence("FRSHAAAA", "  Selva@Freshettax.CA ")).await.unwrap();

        assert_eq!(s.for_email("selva@freshettax.ca").await.unwrap().len(), 1);
        assert_eq!(s.for_email("SELVA@FRESHETTAX.CA").await.unwrap().len(), 1);
    }

    #[tokio::test]
    async fn reinstalling_on_the_same_machine_is_not_a_second_device() {
        let s = MemoryStore::new();
        s.insert(&licence("FRSHAAAA", "a@b.ca")).await.unwrap();

        assert_eq!(s.record_activation("FRSHAAAA", "device-1", 1).await.unwrap(), 1);
        assert_eq!(s.record_activation("FRSHAAAA", "device-1", 2).await.unwrap(), 1);
        assert_eq!(s.record_activation("FRSHAAAA", "device-2", 3).await.unwrap(), 2);
    }

    #[tokio::test]
    async fn a_payment_event_is_only_ever_handled_once() {
        let s = MemoryStore::new();

        assert!(s.claim_event("evt_1", 10).await.unwrap());
        assert!(!s.claim_event("evt_1", 11).await.unwrap());
        assert!(s.claim_event("evt_2", 12).await.unwrap());
    }

    #[tokio::test]
    async fn recovery_is_limited_per_address_and_recovers_after_the_window() {
        let s = MemoryStore::new();

        assert!(s.recovery_permitted("a@b.ca", 100, 3600, 2).await.unwrap());
        assert!(s.recovery_permitted("a@b.ca", 110, 3600, 2).await.unwrap());
        assert!(!s.recovery_permitted("a@b.ca", 120, 3600, 2).await.unwrap());

        // A different address is unaffected by the first one's spending.
        assert!(s.recovery_permitted("c@d.ca", 120, 3600, 2).await.unwrap());

        // And the limit lifts once the window has passed.
        assert!(s.recovery_permitted("a@b.ca", 100 + 3601, 3600, 2).await.unwrap());
    }

    #[tokio::test]
    async fn revoking_twice_reports_that_the_second_time_changed_nothing() {
        let s = MemoryStore::new();
        s.insert(&licence("FRSHAAAA", "a@b.ca")).await.unwrap();

        assert!(s.revoke("FRSHAAAA", 500).await.unwrap());
        assert!(!s.revoke("FRSHAAAA", 600).await.unwrap());
        assert_eq!(s.by_key("FRSHAAAA").await.unwrap().unwrap().revoked_unix, Some(500));
    }

    #[tokio::test]
    async fn forgetting_an_address_takes_its_activations_with_it() {
        let s = MemoryStore::new();
        s.insert(&licence("FRSHAAAA", "a@b.ca")).await.unwrap();
        s.insert(&licence("FRSHBBBB", "keep@b.ca")).await.unwrap();
        s.record_activation("FRSHAAAA", "device-1", 1).await.unwrap();

        assert_eq!(s.forget_email("a@b.ca").await.unwrap(), 1);
        assert!(s.by_key("FRSHAAAA").await.unwrap().is_none());
        assert!(s.by_key("FRSHBBBB").await.unwrap().is_some());

        // The activation count restarts, because the record is genuinely gone
        // rather than merely hidden.
        assert_eq!(s.record_activation("FRSHAAAA", "device-2", 9).await.unwrap(), 1);
    }
}
