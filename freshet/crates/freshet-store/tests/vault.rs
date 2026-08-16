//! Tests for the encrypted vault.
//!
//! The tamper cases matter most: a store that decrypts a modified file is worse
//! than no encryption, because it looks trustworthy while it lies.

use std::collections::BTreeMap;

use freshet_store::crypto::{self, HEADER_LEN, NONCE_OFFSET};
use freshet_store::{DataKey, KeySource, Store, StoreError, Vault};

fn scratch(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("freshet-test-{}-{name}", crypto::random_id()));
    std::fs::create_dir_all(&dir).unwrap();
    dir.join("returns.dat")
}

fn facts() -> BTreeMap<String, String> {
    [
        ("t4.employment_income".to_string(), "85000".to_string()),
        ("rrsp.deduction_claimed".to_string(), "5000".to_string()),
    ]
    .into_iter()
    .collect()
}

fn filled() -> Vault {
    let mut v = Vault::default();
    v.upsert(None, "2025 — me".into(), 2025, "on".into(), facts());
    v
}

// -- round trip -----------------------------------------------------------

#[test]
fn a_saved_return_comes_back_intact() {
    let path = scratch("roundtrip");
    let key = DataKey::generate();

    let (store, _) = Store::open(&path, key.clone(), KeySource::Keychain).unwrap();
    store.save(&filled()).unwrap();

    let (_, reopened) = Store::open(&path, key, KeySource::Keychain).unwrap();

    assert_eq!(reopened.returns.len(), 1);
    let r = &reopened.returns[0];
    assert_eq!(r.label, "2025 — me");
    assert_eq!(r.tax_year, 2025);
    assert_eq!(r.facts["t4.employment_income"], "85000");
}

#[test]
fn opening_a_vault_that_does_not_exist_yet_starts_an_empty_one() {
    let path = scratch("missing");
    let (_, vault) = Store::open(&path, DataKey::generate(), KeySource::Keychain).unwrap();

    assert!(vault.returns.is_empty());
    assert!(!path.exists(), "opening should not create the file");
}

#[test]
fn the_plaintext_is_not_recoverable_from_the_file() {
    let path = scratch("opaque");
    let (store, _) = Store::open(&path, DataKey::generate(), KeySource::Keychain).unwrap();
    store.save(&filled()).unwrap();

    let raw = std::fs::read(&path).unwrap();
    let as_text = String::from_utf8_lossy(&raw);

    assert!(!as_text.contains("85000"), "an amount survived in cleartext");
    assert!(!as_text.contains("employment_income"));
    assert!(!as_text.contains("2025 — me"));
}

// -- tamper and wrong key -------------------------------------------------

#[test]
fn the_wrong_key_does_not_open_the_vault() {
    let path = scratch("wrongkey");
    let (store, _) = Store::open(&path, DataKey::generate(), KeySource::Keychain).unwrap();
    store.save(&filled()).unwrap();

    let err = Store::open(&path, DataKey::generate(), KeySource::Keychain).unwrap_err();
    assert!(matches!(err, StoreError::WrongKeyOrTampered));
}

#[test]
fn a_flipped_ciphertext_bit_is_detected() {
    let path = scratch("bitflip");
    let key = DataKey::generate();
    let (store, _) = Store::open(&path, key.clone(), KeySource::Keychain).unwrap();
    store.save(&filled()).unwrap();

    let mut raw = std::fs::read(&path).unwrap();
    let last = raw.len() - 1;
    raw[last] ^= 0x01;
    std::fs::write(&path, &raw).unwrap();

    let err = Store::open(&path, key, KeySource::Keychain).unwrap_err();
    assert!(matches!(err, StoreError::WrongKeyOrTampered));
}

#[test]
fn rewriting_the_header_is_detected_because_it_is_authenticated() {
    // The header is passed as associated data. Without that, an attacker could
    // rewrite the key-source byte to steer the app down a different unlock path
    // and the tag would still verify.
    let path = scratch("header");
    let key = DataKey::generate();
    let (store, _) = Store::open(&path, key.clone(), KeySource::Keychain).unwrap();
    store.save(&filled()).unwrap();

    let mut raw = std::fs::read(&path).unwrap();
    raw[9] = KeySource::Passphrase as u8;
    std::fs::write(&path, &raw).unwrap();

    let err = Store::open(&path, key, KeySource::Keychain).unwrap_err();
    assert!(matches!(err, StoreError::WrongKeyOrTampered));
}

#[test]
fn a_file_that_is_not_a_vault_is_rejected_clearly() {
    let path = scratch("garbage");
    std::fs::write(&path, b"this is not a vault at all, not even close").unwrap();

    let err = Store::open(&path, DataKey::generate(), KeySource::Keychain).unwrap_err();
    match err {
        StoreError::Format(msg) => assert!(msg.contains("not a Freshet vault"), "{msg}"),
        other => panic!("expected a format error, got {other}"),
    }
}

#[test]
fn a_truncated_file_is_rejected_rather_than_panicking() {
    let path = scratch("short");
    std::fs::write(&path, b"FRESHET1").unwrap();

    assert!(matches!(
        Store::open(&path, DataKey::generate(), KeySource::Keychain),
        Err(StoreError::Format(_))
    ));
}

// -- nonces and key handling ---------------------------------------------

#[test]
fn every_save_draws_a_fresh_nonce() {
    // Reusing a nonce under the same key would leak the XOR of two vaults.
    let key = DataKey::generate();
    let salt = crypto::random_salt();

    let a = crypto::seal(b"payload", &key, KeySource::Keychain, salt).unwrap();
    let b = crypto::seal(b"payload", &key, KeySource::Keychain, salt).unwrap();

    assert_ne!(
        a[NONCE_OFFSET..HEADER_LEN],
        b[NONCE_OFFSET..HEADER_LEN],
        "nonce was reused across saves"
    );
    assert_ne!(a[HEADER_LEN..], b[HEADER_LEN..]);
}

#[test]
fn a_key_cannot_be_leaked_through_its_debug_output() {
    let key = DataKey::from_bytes([7u8; 32]);
    let printed = format!("{key:?}");

    assert_eq!(printed, "DataKey(redacted)");
    assert!(!printed.contains('7'));
}

// -- passphrase mode ------------------------------------------------------

#[test]
fn a_passphrase_vault_opens_with_the_right_passphrase_only() {
    let path = scratch("passphrase");
    let salt = crypto::random_salt();

    let key = crypto::derive_from_passphrase("correct horse battery staple", &salt).unwrap();
    let sealed = crypto::seal(
        &serde_json::to_vec(&filled()).unwrap(),
        &key,
        KeySource::Passphrase,
        salt,
    )
    .unwrap();
    std::fs::write(&path, &sealed).unwrap();

    // The app can learn which unlock path to offer without holding any key.
    let (source, found_salt) = Store::inspect(&path).unwrap().unwrap();
    assert_eq!(source, KeySource::Passphrase);
    assert_eq!(found_salt, salt);

    let right = crypto::derive_from_passphrase("correct horse battery staple", &salt).unwrap();
    assert!(Store::open(&path, right, KeySource::Passphrase).is_ok());

    let wrong = crypto::derive_from_passphrase("Correct horse battery staple", &salt).unwrap();
    assert!(matches!(
        Store::open(&path, wrong, KeySource::Passphrase),
        Err(StoreError::WrongKeyOrTampered)
    ));
}

#[test]
fn the_same_passphrase_under_a_different_salt_is_a_different_key() {
    let a = crypto::derive_from_passphrase("hunter2", &crypto::random_salt()).unwrap();
    let b = crypto::derive_from_passphrase("hunter2", &crypto::random_salt()).unwrap();

    assert_ne!(a.expose(), b.expose());
}

// -- durability -----------------------------------------------------------

#[test]
fn the_previous_version_is_kept_as_a_backup() {
    let path = scratch("backup");
    let key = DataKey::generate();
    let (store, mut vault) = Store::open(&path, key.clone(), KeySource::Keychain).unwrap();

    store.save(&vault).unwrap();
    vault.upsert(None, "second".into(), 2025, "on".into(), facts());
    store.save(&vault).unwrap();

    let bak = path.with_extension("bak");
    assert!(bak.exists(), "no backup was written");

    // The backup is a real vault holding the previous state.
    let (_, restored) = Store::open(&bak, key, KeySource::Keychain).unwrap();
    assert!(restored.returns.is_empty());
}

#[test]
fn saving_leaves_no_temporary_file_behind() {
    let path = scratch("tmp");
    let (store, _) = Store::open(&path, DataKey::generate(), KeySource::Keychain).unwrap();
    store.save(&filled()).unwrap();

    assert!(!path.with_extension("tmp").exists());
}

// -- vault semantics ------------------------------------------------------

#[test]
fn upsert_replaces_by_id_rather_than_adding_a_duplicate() {
    let mut vault = Vault::default();
    let id = vault.upsert(None, "first".into(), 2025, "on".into(), facts());

    let same = vault.upsert(
        Some(id.clone()),
        "renamed".into(),
        2025,
        "on".into(),
        BTreeMap::new(),
    );

    assert_eq!(same, id);
    assert_eq!(vault.returns.len(), 1);
    assert_eq!(vault.get(&id).unwrap().label, "renamed");
    assert!(vault.get(&id).unwrap().facts.is_empty());
}

#[test]
fn returns_are_listed_most_recently_touched_first() {
    let mut vault = Vault::default();
    vault.upsert(None, "older".into(), 2025, "on".into(), facts());
    vault.upsert(None, "newer".into(), 2025, "on".into(), facts());

    // upsert stamps both in the same second, so order the second one explicitly.
    vault.returns[1].updated_unix += 60;

    assert_eq!(vault.by_recency()[0].label, "newer");
}

#[test]
fn removing_a_return_reports_whether_anything_was_removed() {
    let mut vault = Vault::default();
    let id = vault.upsert(None, "one".into(), 2025, "on".into(), facts());

    assert!(vault.remove(&id));
    assert!(!vault.remove(&id));
    assert!(vault.returns.is_empty());
}
