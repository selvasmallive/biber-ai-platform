//! Everything the service needs to know, and where it refuses to start.
//!
//! The rule here is that a misconfiguration should stop the process at boot,
//! loudly, rather than surface months later as a customer who cannot file. A
//! licensing service that starts without a signing key is worse than one that
//! does not start.

use std::env;

use freshet_license::sign::SigningKey;

#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("{0} is not set")]
    Missing(&'static str),

    #[error("{0} is not usable: {1}")]
    Invalid(&'static str, String),
}

pub struct Config {
    /// Where the service believes it lives. Used in emails, never trusted from
    /// a request header — a `Host` header is attacker-controlled, and using one
    /// to build a recovery link is how you mail people a link to someone
    /// else's server.
    pub public_url: String,

    pub port: u16,
    pub database_url: String,

    /// The private half of the production keypair. Held only in memory, only
    /// here, injected from Secret Manager at deploy time.
    pub signing_key: SigningKey,

    pub stripe_webhook_secret: Option<String>,
    pub smtp: Option<SmtpConfig>,

    /// Who may see the admin pages. Empty means admin is switched off, which
    /// is the safe default for a service that has not been put behind IAP yet.
    pub admin_emails: Vec<String>,

    /// The tax year a purchase entitles the buyer to file.
    ///
    /// Configuration rather than a constant: it changes every year, and a
    /// certification window that slips moves it without any code changing.
    /// Selling a licence for the wrong year is a refund and an apology, so it
    /// is worth being able to correct without a deploy.
    pub sale_year: u16,
}

pub struct SmtpConfig {
    pub host: String,
    pub user: String,
    pub password: String,
    pub from: String,
}

fn var(name: &'static str) -> Result<String, ConfigError> {
    env::var(name)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .ok_or(ConfigError::Missing(name))
}

impl Config {
    pub fn from_env() -> Result<Self, ConfigError> {
        let raw = var("FRESHET_SIGNING_KEY")?;
        let signing_key = parse_signing_key(&raw)
            .map_err(|e| ConfigError::Invalid("FRESHET_SIGNING_KEY", e))?;

        // Cloud Run supplies PORT. Defaulting matters only for local runs.
        let port = env::var("PORT")
            .unwrap_or_else(|_| "8080".into())
            .parse()
            .map_err(|e| ConfigError::Invalid("PORT", format!("{e}")))?;

        let smtp = match (
            env::var("SMTP_HOST").ok(),
            env::var("SMTP_USER").ok(),
            env::var("SMTP_PASSWORD").ok(),
            env::var("MAIL_FROM").ok(),
        ) {
            (Some(host), Some(user), Some(password), Some(from))
                if !host.is_empty() && !from.is_empty() =>
            {
                Some(SmtpConfig { host, user, password, from })
            }
            _ => None,
        };

        // The certification target as of this writing. CRA's application
        // window for the 2026 T1 closed before this product applied, so the
        // first year it can be certified to file is 2027.
        let sale_year = env::var("SALE_YEAR")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .map(|v| v.trim().parse::<u16>())
            .transpose()
            .map_err(|e| ConfigError::Invalid("SALE_YEAR", format!("{e}")))?
            .unwrap_or(2027);

        Ok(Config {
            sale_year,
            public_url: var("PUBLIC_URL").unwrap_or_else(|_| "https://freshettax.ca".into()),
            port,
            database_url: var("DATABASE_URL")?,
            signing_key,
            stripe_webhook_secret: env::var("STRIPE_WEBHOOK_SECRET").ok().filter(|s| !s.is_empty()),
            smtp,
            admin_emails: env::var("ADMIN_EMAILS")
                .unwrap_or_default()
                .split(',')
                .map(|s| s.trim().to_ascii_lowercase())
                .filter(|s| !s.is_empty())
                .collect(),
        })
    }
}

/// Read a 32-byte Ed25519 seed from hex.
///
/// Rejected rather than truncated or padded: a key of the wrong length is a
/// deployment mistake, and quietly deriving *something* from it would mean
/// issuing licences no installed copy of Freshet can verify.
pub fn parse_signing_key(hex_seed: &str) -> Result<SigningKey, String> {
    let bytes = hex::decode(hex_seed.trim())
        .map_err(|e| format!("expected 64 hex characters: {e}"))?;

    let seed: [u8; 32] = bytes
        .as_slice()
        .try_into()
        .map_err(|_| format!("expected 32 bytes, got {}", bytes.len()))?;

    Ok(SigningKey::from_bytes(&seed))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_key_of_the_wrong_length_is_refused_rather_than_padded() {
        for bad in ["", "ab", &"aa".repeat(31), &"aa".repeat(33)] {
            assert!(
                parse_signing_key(bad).is_err(),
                "accepted a {}-char key",
                bad.len()
            );
        }
    }

    #[test]
    fn a_well_formed_key_round_trips_to_a_usable_signer() {
        let seed = "11".repeat(32);
        let key = parse_signing_key(&seed).unwrap();
        assert_eq!(key.to_bytes().to_vec(), vec![0x11u8; 32]);
    }

    #[test]
    fn surrounding_whitespace_does_not_break_a_secret_read_from_a_file() {
        let seed = format!("  {}\n", "22".repeat(32));
        assert!(parse_signing_key(&seed).is_ok());
    }
}
