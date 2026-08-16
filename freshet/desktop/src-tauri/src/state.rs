//! Persisted app settings.
//!
//! What lives here: which model provider is configured, and whether the user
//! has consented to sending return data to it. What never lives here: the API
//! key (OS keychain) and the return itself (not yet implemented; when it is, it
//! goes to an encrypted store, not this file).

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::Mutex;

use freshet_advisor::{Consent, KeyRef, Provider, ProviderConfig};
use freshet_autofill::ImportedData;
use freshet_store::{DataKey, KeySource, Store, Vault};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Settings {
    pub provider: Option<ProviderConfig>,
    pub consent: Option<Consent>,
    /// The signed licence token. Not secret: it is signed, and it has to be
    /// readable to be checked. Secrecy would add nothing a signature does not.
    #[serde(default)]
    pub licence: Option<String>,

    /// How many returns have been filed under each licence key.
    ///
    /// **Advisory, not authoritative.** It lives on the customer's machine, so
    /// reinstalling resets it and nothing here can stop that. Its job is to
    /// show an honest "2 of 5 used" and to fail fast before a transmission that
    /// would be refused anyway — not to enforce anything.
    ///
    /// For a counted licence the binding count is confirmed at transmission,
    /// which already requires the network. See `Allowance::needs_authoritative_count`.
    #[serde(default)]
    pub filings: BTreeMap<String, u32>,
}

/// What the frontend is allowed to see. Structurally cannot carry a secret.
#[derive(Debug, Clone, Serialize)]
pub struct SettingsView {
    pub provider: Option<Provider>,
    pub provider_label: Option<String>,
    /// True when a key is present in the OS keychain for the current provider.
    pub has_key: bool,
    /// True when the configured provider sends data off the device.
    pub is_remote: bool,
    /// True when consent is present *and* matches the current provider.
    pub consent_granted: bool,
}

pub const KEYCHAIN_SERVICE: &str = "ca.freshet.desktop";

/// Keychain entry for a provider, or `None` when the provider needs no auth.
pub fn key_ref_for(provider: &Provider) -> Option<KeyRef> {
    let slug = match provider {
        Provider::Anthropic { .. } => "anthropic",
        Provider::OpenAi { .. } => "openai",
        Provider::Biber { .. } => "biber",
        Provider::Local { .. } => return None,
    };

    Some(KeyRef {
        keychain_entry: format!("freshet.provider.{slug}"),
    })
}

pub fn read_key(key_ref: &KeyRef) -> Option<String> {
    keyring::Entry::new(KEYCHAIN_SERVICE, &key_ref.keychain_entry)
        .ok()?
        .get_password()
        .ok()
        .filter(|k| !k.is_empty())
}

pub fn write_key(key_ref: &KeyRef, key: &str) -> Result<(), String> {
    let entry = keyring::Entry::new(KEYCHAIN_SERVICE, &key_ref.keychain_entry)
        .map_err(|e| format!("could not open the keychain: {e}"))?;

    if key.is_empty() {
        // Deleting a key that was never stored is not an error.
        let _ = entry.delete_credential();
        return Ok(());
    }

    entry
        .set_password(key)
        .map_err(|e| format!("could not save the key to the keychain: {e}"))
}

/// Keychain entry holding the 32-byte vault key.
const VAULT_KEY_ENTRY: &str = "freshet.vault.key";

fn to_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn from_hex(s: &str) -> Option<[u8; 32]> {
    if s.len() != 64 {
        return None;
    }
    let mut out = [0u8; 32];
    for (i, chunk) in s.as_bytes().chunks(2).enumerate() {
        out[i] = u8::from_str_radix(std::str::from_utf8(chunk).ok()?, 16).ok()?;
    }
    Some(out)
}

/// Fetch the vault key from the OS keychain, creating one on first run.
///
/// If this entry is ever lost, the vault is unrecoverable by design — there is
/// no escrow and no backdoor. That is the correct trade for tax data, and it is
/// why the UI tells the user to keep their own copies of source documents.
fn vault_key() -> Result<DataKey, String> {
    let entry = keyring::Entry::new(KEYCHAIN_SERVICE, VAULT_KEY_ENTRY)
        .map_err(|e| format!("could not open the keychain: {e}"))?;

    if let Ok(existing) = entry.get_password() {
        if let Some(bytes) = from_hex(existing.trim()) {
            return Ok(DataKey::from_bytes(bytes));
        }
        // A malformed entry must not silently become a new key: that would
        // orphan an existing vault the user cannot then open.
        return Err(
            "the stored vault key is unreadable; your saved returns cannot be opened".into(),
        );
    }

    let key = DataKey::generate();
    entry
        .set_password(&to_hex(key.expose()))
        .map_err(|e| format!("could not save the vault key to the keychain: {e}"))?;

    Ok(key)
}

#[cfg(test)]
mod key_encoding_tests {
    use super::*;

    /// The keychain stores the vault key as hex. If this round-trip ever breaks,
    /// every saved return becomes undecryptable, so it is worth pinning.
    #[test]
    fn a_key_survives_the_hex_round_trip() {
        for pattern in [[0u8; 32], [0xffu8; 32], [0xa5u8; 32]] {
            let encoded = to_hex(&pattern);
            assert_eq!(encoded.len(), 64);
            assert_eq!(from_hex(&encoded), Some(pattern));
        }

        let mixed: [u8; 32] = std::array::from_fn(|i| (i * 7 + 3) as u8);
        assert_eq!(from_hex(&to_hex(&mixed)), Some(mixed));
    }

    #[test]
    fn a_malformed_entry_is_rejected_rather_than_silently_truncated() {
        assert_eq!(from_hex(""), None);
        assert_eq!(from_hex("ab"), None);
        // Right length, not hex.
        assert_eq!(from_hex(&"zz".repeat(32)), None);
        // One character short.
        assert_eq!(from_hex(&"a".repeat(63)), None);
    }

    /// Exercises the real OS credential store, so it is excluded from the
    /// default run: it writes to the developer's machine and would fail on a
    /// headless CI box. Run with `cargo test -- --ignored`.
    #[test]
    #[ignore = "touches the real OS keychain"]
    fn the_vault_key_is_created_once_and_returned_stably() {
        let first = vault_key().expect("OS keychain should be reachable");
        let second = vault_key().expect("OS keychain should be reachable");

        // A second call must return the *same* key, not mint a new one — a new
        // key here would orphan every previously saved return.
        assert_eq!(first.expose(), second.expose());
    }

    #[test]
    fn hex_output_is_lowercase_and_zero_padded() {
        let mut bytes = [0u8; 32];
        bytes[0] = 0x0f;
        bytes[31] = 0xa0;

        let encoded = to_hex(&bytes);
        assert!(encoded.starts_with("0f"));
        assert!(encoded.ends_with("a0"));
        assert_eq!(encoded, encoded.to_lowercase());
    }
}

pub struct VaultState {
    pub store: Store,
    pub vault: Vault,
}

impl VaultState {
    /// Persist the current vault.
    pub fn flush(&self) -> Result<(), String> {
        self.store.save(&self.vault).map_err(|e| e.to_string())
    }
}

pub struct AppState {
    pub settings: Mutex<Settings>,
    pub path: PathBuf,
    /// `None` when storage could not be opened; `vault_error` says why.
    pub vault: Mutex<Option<VaultState>>,
    pub vault_error: Option<String>,
    /// The most recent Auto-fill response, so accepting proposals does not
    /// require a second round trip to CRA.
    pub last_import: Mutex<Option<ImportedData>>,
}

impl AppState {
    pub fn load(dir: PathBuf) -> Self {
        let path = dir.join("settings.json");
        let settings = std::fs::read_to_string(&path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default();

        // Storage failing must not stop the app from launching: a user who
        // cannot open last year's return can still prepare this year's.
        let (vault, vault_error) = match Self::open_vault(dir.join("returns.dat")) {
            Ok(v) => (Some(v), None),
            Err(e) => (None, Some(e)),
        };

        Self {
            settings: Mutex::new(settings),
            path,
            vault: Mutex::new(vault),
            vault_error,
            last_import: Mutex::new(None),
        }
    }

    fn open_vault(path: PathBuf) -> Result<VaultState, String> {
        let key = vault_key()?;
        let (store, vault) =
            Store::open(path, key, KeySource::Keychain).map_err(|e| e.to_string())?;
        Ok(VaultState { store, vault })
    }

    pub fn save(&self) -> Result<(), String> {
        let settings = self.settings.lock().unwrap().clone();

        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }

        let json = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
        std::fs::write(&self.path, json).map_err(|e| e.to_string())
    }

    pub fn view(&self) -> SettingsView {
        let settings = self.settings.lock().unwrap();

        let Some(config) = settings.provider.as_ref() else {
            return SettingsView {
                provider: None,
                provider_label: None,
                has_key: false,
                is_remote: false,
                consent_granted: false,
            };
        };

        let label = config.provider.label();

        SettingsView {
            has_key: config
                .key_ref
                .as_ref()
                .map(|r| read_key(r).is_some())
                // A local provider needs no key, so it is never "missing" one.
                .unwrap_or(true),
            is_remote: config.provider.is_remote(),
            consent_granted: settings
                .consent
                .as_ref()
                .is_some_and(|c| c.provider_label == label),
            provider: Some(config.provider.clone()),
            provider_label: Some(label),
        }
    }
}
