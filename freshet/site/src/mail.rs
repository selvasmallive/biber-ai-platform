//! Delivering a licence.
//!
//! What goes in the email is the **signed licence**, not just the key. That is
//! the whole reason the desktop app never has to contact anything: the customer
//! already holds the thing that unlocks filing, and pasting it is the entire
//! process. The short key is included too, because it is what a person can read
//! over the phone to support.

use async_trait::async_trait;

use crate::config::SmtpConfig;
use crate::store::IssuedLicence;

#[derive(Debug, thiserror::Error)]
pub enum MailError {
    #[error("could not send mail: {0}")]
    Send(String),
}

#[async_trait]
pub trait Mailer: Send + Sync {
    async fn send(&self, to: &str, subject: &str, body: &str) -> Result<(), MailError>;
}

/// Used when no SMTP credentials are configured.
///
/// It logs instead of sending, so a local run works end to end without a mail
/// account — and, importantly, without silently pretending a customer received
/// something. The log line is the honest record that nothing left.
pub struct LoggingMailer;

#[async_trait]
impl Mailer for LoggingMailer {
    async fn send(&self, to: &str, subject: &str, body: &str) -> Result<(), MailError> {
        tracing::warn!(
            to,
            subject,
            "no SMTP configured — mail was NOT sent. Body follows:\n{body}"
        );
        Ok(())
    }
}

pub struct SmtpMailer {
    transport: lettre::AsyncSmtpTransport<lettre::Tokio1Executor>,
    from: String,
}

impl SmtpMailer {
    pub fn new(cfg: &SmtpConfig) -> Result<Self, MailError> {
        let creds = lettre::transport::smtp::authentication::Credentials::new(
            cfg.user.clone(),
            cfg.password.clone(),
        );

        let transport =
            lettre::AsyncSmtpTransport::<lettre::Tokio1Executor>::starttls_relay(&cfg.host)
                .map_err(|e| MailError::Send(e.to_string()))?
                .credentials(creds)
                .build();

        Ok(Self {
            transport,
            from: cfg.from.clone(),
        })
    }
}

#[async_trait]
impl Mailer for SmtpMailer {
    async fn send(&self, to: &str, subject: &str, body: &str) -> Result<(), MailError> {
        use lettre::AsyncTransport;

        let message = lettre::Message::builder()
            .from(self.from.parse().map_err(|e| MailError::Send(format!("{e}")))?)
            .to(to.parse().map_err(|e| MailError::Send(format!("{e}")))?)
            .subject(subject)
            .body(body.to_string())
            .map_err(|e| MailError::Send(e.to_string()))?;

        self.transport
            .send(message)
            .await
            .map_err(|e| MailError::Send(e.to_string()))?;

        Ok(())
    }
}

/// The message a customer gets, on purchase and on every resend.
///
/// Written to be usable by someone who has never heard of a licence file: the
/// first instruction is what to do, not what it is.
pub fn licence_email(licence: &IssuedLicence, formatted_key: &str) -> String {
    let expiry = match licence.expires_unix {
        Some(_) => {
            "\nThis licence covers one filing season. You will get a new one \
             when you buy next year's.\n"
        }
        None => "",
    };

    format!(
        "Your Freshet licence is below.

To use it: open Freshet, go to Settings, and paste everything between the
lines into the licence box. Freshet checks it on your own machine — it does
not contact us, and it will keep working whether or not we are online.

----- BEGIN FRESHET LICENCE -----
{token}
----- END FRESHET LICENCE -----

Licence key: {key}

Keep this email. If you lose it, ask for it again at {site}/recover and we
will send it back to this address.
{expiry}
Preparing a return in Freshet is free and always will be. This licence is
what lets you file one.
",
        token = licence.token,
        key = formatted_key,
        site = "https://freshettax.ca",
        expiry = expiry,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> IssuedLicence {
        IssuedLicence {
            key: "FRSHAAAABBBBCCCCDDDD".into(),
            email: "buyer@example.ca".into(),
            token: "cGF5bG9hZA.c2ln".into(),
            product: "freshet-t1".into(),
            issued_unix: 1_000,
            expires_unix: Some(2_000),
            revoked_unix: None,
            order_ref: None,
        }
    }

    #[test]
    fn the_email_carries_the_licence_itself_not_only_the_key() {
        let body = licence_email(&sample(), "FRSH-AAAA-BBBB-CCCC-DDDD");

        assert!(
            body.contains("cGF5bG9hZA.c2ln"),
            "the signed licence must be in the email, or the offline path does not work"
        );
        assert!(body.contains("FRSH-AAAA-BBBB-CCCC-DDDD"));
    }

    /// Where the body happens to wrap is not the property under test, so the
    /// assertion should not break the next time a word is added.
    fn flowed(licence: &IssuedLicence) -> String {
        licence_email(licence, "FRSH-AAAA-BBBB-CCCC-DDDD")
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ")
    }

    #[test]
    fn the_email_tells_the_customer_it_will_work_without_us() {
        let body = flowed(&sample());

        assert!(body.contains("does not contact us"), "{body}");
        assert!(body.contains("whether or not we are online"), "{body}");
    }

    #[test]
    fn an_expiring_licence_says_so_and_a_perpetual_one_does_not() {
        let mut l = sample();
        assert!(licence_email(&l, "k").contains("one filing season"));

        l.expires_unix = None;
        assert!(!licence_email(&l, "k").contains("one filing season"));
    }
}
