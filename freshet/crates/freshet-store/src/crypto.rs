//! The sealed-file format.
//!
//! ```text
//! offset  size  field
//! 0       8     magic  b"FRESHET1"
//! 8       1     format version
//! 9       1     key source (1 = keychain data key, 2 = passphrase)
//! 10      16    Argon2 salt (all zero when the key source is the keychain)
//! 26      24    XChaCha20 nonce
//! 50      ..    ciphertext || Poly1305 tag
//! ```
//!
//! The whole 50-byte header is passed as associated data, so an attacker cannot
//! flip the key-source byte or swap the salt to steer decryption without the
//! tag failing. Every save draws a fresh nonce.

use chacha20poly1305::aead::rand_core::RngCore;
use chacha20poly1305::aead::{Aead, AeadCore, KeyInit, OsRng, Payload};
use chacha20poly1305::{Key, XChaCha20Poly1305, XNonce};
use zeroize::{Zeroize, ZeroizeOnDrop};

use crate::StoreError;

const MAGIC: &[u8; 8] = b"FRESHET1";
const VERSION: u8 = 1;
const SALT_LEN: usize = 16;
const NONCE_LEN: usize = 24;
pub const HEADER_LEN: usize = 8 + 1 + 1 + SALT_LEN + NONCE_LEN;
/// Offset of the nonce within the header.
pub const NONCE_OFFSET: usize = 10 + SALT_LEN;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeySource {
    /// A random 32-byte key held in the OS keychain. Zero friction: the vault
    /// opens whenever the user's desktop session is unlocked.
    Keychain = 1,
    /// Argon2id over a user passphrase. Protects the vault even from someone
    /// with the unlocked machine, at the cost of something to remember.
    Passphrase = 2,
}

impl KeySource {
    fn from_byte(b: u8) -> Result<Self, StoreError> {
        match b {
            1 => Ok(KeySource::Keychain),
            2 => Ok(KeySource::Passphrase),
            other => Err(StoreError::Format(format!("unknown key source {other}"))),
        }
    }
}

/// A 32-byte data key, wiped from memory when dropped.
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct DataKey([u8; 32]);

impl DataKey {
    pub fn from_bytes(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    /// Generate a fresh key. Used once, the first time a vault is created.
    pub fn generate() -> Self {
        let key = XChaCha20Poly1305::generate_key(&mut OsRng);
        let mut bytes = [0u8; 32];
        bytes.copy_from_slice(&key);
        Self(bytes)
    }

    pub fn expose(&self) -> &[u8; 32] {
        &self.0
    }
}

impl std::fmt::Debug for DataKey {
    /// Never let a key reach a log line through a derived Debug.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("DataKey(redacted)")
    }
}

/// Stretch a passphrase into a data key with Argon2id.
pub fn derive_from_passphrase(passphrase: &str, salt: &[u8; SALT_LEN]) -> Result<DataKey, StoreError> {
    let mut bytes = [0u8; 32];

    argon2::Argon2::default()
        .hash_password_into(passphrase.as_bytes(), salt, &mut bytes)
        .map_err(|e| StoreError::Crypto(format!("key derivation failed: {e}")))?;

    let key = DataKey::from_bytes(bytes);
    bytes.zeroize();
    Ok(key)
}

fn cipher(key: &DataKey) -> XChaCha20Poly1305 {
    XChaCha20Poly1305::new(Key::from_slice(key.expose()))
}

/// Encrypt `plaintext` into the sealed file format.
pub fn seal(
    plaintext: &[u8],
    key: &DataKey,
    source: KeySource,
    salt: [u8; SALT_LEN],
) -> Result<Vec<u8>, StoreError> {
    let nonce = XChaCha20Poly1305::generate_nonce(&mut OsRng);

    let mut header = Vec::with_capacity(HEADER_LEN);
    header.extend_from_slice(MAGIC);
    header.push(VERSION);
    header.push(source as u8);
    header.extend_from_slice(&salt);
    header.extend_from_slice(&nonce);
    debug_assert_eq!(header.len(), HEADER_LEN);

    let ciphertext = cipher(key)
        .encrypt(
            &nonce,
            Payload {
                msg: plaintext,
                aad: &header,
            },
        )
        .map_err(|_| StoreError::Crypto("encryption failed".into()))?;

    let mut out = header;
    out.extend_from_slice(&ciphertext);
    Ok(out)
}

/// The key source and salt of a sealed file, readable without the key.
///
/// The app needs this to know whether to fetch a keychain key or prompt for a
/// passphrase before it can even attempt to open the vault.
pub fn inspect(sealed: &[u8]) -> Result<(KeySource, [u8; SALT_LEN]), StoreError> {
    // Identity before size: someone who points the app at the wrong file is
    // better served by "not a Freshet vault" than by "truncated".
    if sealed.len() < MAGIC.len() || &sealed[..MAGIC.len()] != MAGIC {
        return Err(StoreError::Format("not a Freshet vault".into()));
    }
    if sealed.len() < HEADER_LEN {
        return Err(StoreError::Format(
            "this vault file is truncated — try the .bak file beside it".into(),
        ));
    }
    if sealed[8] != VERSION {
        return Err(StoreError::Format(format!(
            "vault format version {} was written by a newer build of Freshet",
            sealed[8]
        )));
    }

    let source = KeySource::from_byte(sealed[9])?;
    let mut salt = [0u8; SALT_LEN];
    salt.copy_from_slice(&sealed[10..10 + SALT_LEN]);

    Ok((source, salt))
}

/// Decrypt a sealed file.
pub fn open(sealed: &[u8], key: &DataKey) -> Result<Vec<u8>, StoreError> {
    inspect(sealed)?;

    let header = &sealed[..HEADER_LEN];
    let nonce = XNonce::from_slice(&sealed[10 + SALT_LEN..HEADER_LEN]);

    cipher(key)
        .decrypt(
            nonce,
            Payload {
                msg: &sealed[HEADER_LEN..],
                aad: header,
            },
        )
        .map_err(|_| StoreError::WrongKeyOrTampered)
}

pub fn random_salt() -> [u8; SALT_LEN] {
    let mut salt = [0u8; SALT_LEN];
    OsRng.fill_bytes(&mut salt);
    salt
}

/// A hex id with 128 bits of entropy, so returns can be addressed without
/// pulling in a UUID dependency.
pub fn random_id() -> String {
    let mut bytes = [0u8; 16];
    OsRng.fill_bytes(&mut bytes);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
