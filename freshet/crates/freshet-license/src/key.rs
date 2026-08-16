//! The human-typed licence key.
//!
//! Twenty characters in Crockford's base32 alphabet, of which the last four are
//! a checksum. The checksum exists so a mistyped key fails *here*, offline, with
//! "that key has a typo" rather than becoming a support ticket about the
//! activation server rejecting a purchase.

use crate::LicenceError;

/// Crockford base32: no I, L, O or U, so the characters people confuse are
/// simply absent rather than ambiguous.
const ALPHABET: &[u8] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";

const PAYLOAD_LEN: usize = 16;
const CHECK_LEN: usize = 4;

/// A syntactically valid key. Says nothing about whether it was ever sold.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LicenceKey(String);

impl LicenceKey {
    /// Parse a key as a person might type it: any case, dashes or spaces
    /// wherever, and the characters that look alike folded together.
    pub fn parse(raw: &str) -> Result<Self, LicenceError> {
        let cleaned: String = raw
            .chars()
            .filter(|c| c.is_ascii_alphanumeric())
            .map(|c| match c.to_ascii_uppercase() {
                // People transcribe these wrong constantly; accept the mistake
                // rather than making them squint at the email again.
                'O' => '0',
                'I' | 'L' => '1',
                'U' => 'V',
                other => other,
            })
            .collect();

        let cleaned = cleaned
            .strip_prefix("FRSH")
            .unwrap_or(&cleaned)
            .to_string();

        if cleaned.len() != PAYLOAD_LEN + CHECK_LEN {
            return Err(LicenceError::MalformedKey(format!(
                "a licence key has {} characters after the FRSH prefix, this has {}",
                PAYLOAD_LEN + CHECK_LEN,
                cleaned.len()
            )));
        }

        if let Some(bad) = cleaned.chars().find(|c| !ALPHABET.contains(&(*c as u8))) {
            return Err(LicenceError::MalformedKey(format!(
                "'{bad}' is not a character licence keys use"
            )));
        }

        let (payload, check) = cleaned.split_at(PAYLOAD_LEN);
        if check != checksum(payload) {
            return Err(LicenceError::MalformedKey(
                "the check characters do not match — the key has a typo in it".into(),
            ));
        }

        Ok(LicenceKey(cleaned))
    }

    /// Build a key from 16 payload characters, appending the checksum.
    pub fn from_payload(payload: &str) -> Result<Self, LicenceError> {
        if payload.len() != PAYLOAD_LEN {
            return Err(LicenceError::MalformedKey(format!(
                "payload must be {PAYLOAD_LEN} characters"
            )));
        }
        Self::parse(&format!("{payload}{}", checksum(payload)))
    }

    /// Canonical form, without separators.
    pub fn compact(&self) -> String {
        format!("FRSH{}", self.0)
    }

    /// How it is printed in an email and on screen.
    pub fn formatted(&self) -> String {
        let groups: Vec<String> = self
            .0
            .as_bytes()
            .chunks(4)
            .map(|c| String::from_utf8_lossy(c).into_owned())
            .collect();

        format!("FRSH-{}", groups.join("-"))
    }
}

impl std::fmt::Display for LicenceKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.formatted())
    }
}

/// FNV-1a over the payload, folded into four base32 characters.
///
/// This catches typos, not forgery — the signature does that. Anyone can
/// compute a well-formed key; only a signed licence actually unlocks filing.
fn checksum(payload: &str) -> String {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in payload.bytes() {
        h ^= u64::from(b);
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }

    (0..CHECK_LEN)
        .map(|i| ALPHABET[((h >> (i * 5)) & 0x1f) as usize] as char)
        .collect()
}
