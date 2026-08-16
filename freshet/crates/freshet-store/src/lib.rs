//! Encrypted local storage for tax returns.
//!
//! A tax return is among the most sensitive documents a person owns: income,
//! employer, marital status, dependants, and — once CRA Auto-fill lands — their
//! SIN. It is stored encrypted at rest, in one sealed file the app rewrites
//! atomically, and the key never appears in the file or in any log.
//!
//! The crate does no key management of its own. It is handed a [`DataKey`] and
//! stays a pure function of (bytes, key), which is what makes the tamper cases
//! testable.

pub mod crypto;

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub use crypto::{DataKey, KeySource};
use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("could not read or write the vault: {0}")]
    Io(#[from] std::io::Error),

    #[error("the vault file is not valid: {0}")]
    Format(String),

    #[error("{0}")]
    Crypto(String),

    #[error("the vault could not be decrypted — wrong key, or the file has been altered")]
    WrongKeyOrTampered,

    #[error("the vault decrypted but its contents are not readable: {0}")]
    Contents(String),
}

/// One saved return. Deliberately holds the taxpayer's *inputs*, not the
/// computed result: the engine is deterministic, so recomputing on load is both
/// cheaper than storing and immune to a stale figure surviving a rule change.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredReturn {
    pub id: String,
    /// A user-chosen nickname such as "2025 — me". Not an identity field.
    pub label: String,
    pub tax_year: u16,
    pub province: String,
    pub facts: BTreeMap<String, String>,
    pub created_unix: i64,
    pub updated_unix: i64,
}

/// Everything in the vault.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Vault {
    #[serde(default)]
    pub returns: Vec<StoredReturn>,
}

impl Vault {
    pub fn get(&self, id: &str) -> Option<&StoredReturn> {
        self.returns.iter().find(|r| r.id == id)
    }

    /// Insert or replace, stamping `updated_unix`. Returns the id.
    pub fn upsert(
        &mut self,
        id: Option<String>,
        label: String,
        tax_year: u16,
        province: String,
        facts: BTreeMap<String, String>,
    ) -> String {
        let now = now_unix();

        if let Some(wanted) = id.as_deref() {
            if let Some(existing) = self.returns.iter_mut().find(|r| r.id == wanted) {
                existing.label = label;
                existing.tax_year = tax_year;
                existing.province = province;
                existing.facts = facts;
                existing.updated_unix = now;
                return existing.id.clone();
            }
        }

        let fresh = StoredReturn {
            id: id.unwrap_or_else(crypto::random_id),
            label,
            tax_year,
            province,
            facts,
            created_unix: now,
            updated_unix: now,
        };
        let id = fresh.id.clone();
        self.returns.push(fresh);
        id
    }

    pub fn remove(&mut self, id: &str) -> bool {
        let before = self.returns.len();
        self.returns.retain(|r| r.id != id);
        self.returns.len() != before
    }

    /// Most recently touched first.
    pub fn by_recency(&self) -> Vec<&StoredReturn> {
        let mut all: Vec<_> = self.returns.iter().collect();
        all.sort_by_key(|r| std::cmp::Reverse(r.updated_unix));
        all
    }
}

pub fn now_unix() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// A vault file on disk.
///
/// Safe to `Debug`: the contained key redacts itself.
#[derive(Debug)]
pub struct Store {
    path: PathBuf,
    key: DataKey,
    source: KeySource,
    salt: [u8; 16],
}

impl Store {
    /// Open an existing vault, or start an empty one if the file is absent.
    pub fn open(path: impl Into<PathBuf>, key: DataKey, source: KeySource) -> Result<(Self, Vault), StoreError> {
        let path = path.into();

        let (vault, salt) = match std::fs::read(&path) {
            Ok(sealed) => {
                let (_, salt) = crypto::inspect(&sealed)?;
                let plaintext = crypto::open(&sealed, &key)?;
                let vault: Vault = serde_json::from_slice(&plaintext)
                    .map_err(|e| StoreError::Contents(e.to_string()))?;
                (vault, salt)
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                (Vault::default(), crypto::random_salt())
            }
            Err(e) => return Err(StoreError::Io(e)),
        };

        Ok((
            Store {
                path,
                key,
                source,
                salt,
            },
            vault,
        ))
    }

    /// What kind of key a vault file needs, without opening it.
    pub fn inspect(path: impl AsRef<Path>) -> Result<Option<(KeySource, [u8; 16])>, StoreError> {
        match std::fs::read(path.as_ref()) {
            Ok(sealed) => crypto::inspect(&sealed).map(Some),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(StoreError::Io(e)),
        }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Seal and write the vault.
    ///
    /// Writes to a temporary file first and keeps the previous version as
    /// `.bak`. A crash mid-write therefore costs at most the current save, not
    /// the whole vault — the failure mode that would otherwise destroy years of
    /// returns in one bad moment.
    pub fn save(&self, vault: &Vault) -> Result<(), StoreError> {
        let plaintext =
            serde_json::to_vec(vault).map_err(|e| StoreError::Contents(e.to_string()))?;
        let sealed = crypto::seal(&plaintext, &self.key, self.source, self.salt)?;

        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let tmp = self.path.with_extension("tmp");
        std::fs::write(&tmp, &sealed)?;

        if self.path.exists() {
            let bak = self.path.with_extension("bak");
            let _ = std::fs::remove_file(&bak);
            std::fs::copy(&self.path, &bak)?;
            // Windows will not rename onto an existing path.
            std::fs::remove_file(&self.path)?;
        }

        std::fs::rename(&tmp, &self.path)?;
        Ok(())
    }
}
