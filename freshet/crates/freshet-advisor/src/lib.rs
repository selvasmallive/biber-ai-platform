//! The Freshet tax advisor.
//!
//! Policy lives here; transport does not. Everything that decides *whether*
//! taxpayer data may leave the machine is in this crate, is pure, and is
//! covered by tests -- because "we forgot to redact that field" is the kind of
//! defect that ends a tax software business.

pub mod context;
pub mod provider;
pub mod redact;

pub use context::{grounding, SYSTEM_PROMPT};
pub use provider::{KeyRef, OutboundRequest, Provider, ProviderConfig, Role, Turn};
pub use redact::{Finding, PiiKind, Redaction, Redactor};

use serde::{Deserialize, Serialize};
use freshet_engine::Assessment;

/// A recorded, provider-specific grant to send return data off the device.
///
/// Consent is tied to the provider it was given for. Switching from a local
/// model to OpenAI is a new disclosure and requires a new grant -- silently
/// reusing the old one would be exactly the bait-and-switch users fear.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Consent {
    pub provider_label: String,
    pub granted_at_unix: i64,
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum AdvisorError {
    #[error("sending your return to {provider} requires consent, which has not been given")]
    ConsentRequired { provider: String },

    #[error("consent was given for {granted_for}, but the configured provider is now {current}")]
    ConsentStale { granted_for: String, current: String },

    #[error("refusing to send: {0:?} survived redaction")]
    RedactionFailed(Vec<PiiKind>),

    #[error("no API key is configured for {0}")]
    MissingApiKey(String),
}

/// A request that has cleared every policy check and is safe to transmit.
#[derive(Debug, Clone)]
pub struct Prepared {
    pub system: String,
    pub turns: Vec<Turn>,
    /// Categories of PII that were stripped, so the UI can tell the user what
    /// was caught rather than silently swallowing it.
    pub redacted: Vec<PiiKind>,
    pub remote: bool,
}

pub struct Advisor {
    pub config: ProviderConfig,
    redactor: Redactor,
}

impl Advisor {
    pub fn new(config: ProviderConfig) -> Self {
        Self {
            config,
            redactor: Redactor::new(),
        }
    }

    /// Run every egress check and assemble the request.
    ///
    /// Order matters: consent is checked before any text is processed, so a
    /// user who has not consented never has their return rendered into a
    /// prompt buffer at all.
    pub fn prepare(
        &self,
        assessment: &Assessment,
        history: &[Turn],
        user_message: &str,
        consent: Option<&Consent>,
    ) -> Result<Prepared, AdvisorError> {
        let remote = self.config.provider.is_remote();
        // The recipient, not the display name. A gateway re-pointed at another
        // host keeps its label and must not keep its consent.
        let current = self.config.provider.consent_key();

        if remote {
            match consent {
                None => {
                    return Err(AdvisorError::ConsentRequired { provider: current });
                }
                Some(c) if c.provider_label != current => {
                    return Err(AdvisorError::ConsentStale {
                        granted_for: c.provider_label.clone(),
                        current,
                    });
                }
                Some(_) => {}
            }
        }

        let mut redacted_kinds = Vec::new();
        let mut turns = Vec::with_capacity(history.len() + 1);

        for turn in history.iter().chain(std::iter::once(&Turn {
            role: Role::User,
            content: user_message.to_string(),
        })) {
            let r = self.redactor.redact(&turn.content);
            redacted_kinds.extend(r.kinds());

            // Fail closed: if a detector still fires on the redacted text, the
            // redaction did not do its job and we do not send at all.
            let residual: Vec<PiiKind> = self
                .redactor
                .scan(&r.text)
                .into_iter()
                .map(|f| f.kind)
                .filter(|k| k.is_critical())
                .collect();

            if !residual.is_empty() {
                return Err(AdvisorError::RedactionFailed(residual));
            }

            turns.push(Turn {
                role: turn.role,
                content: r.text,
            });
        }

        redacted_kinds.dedup();

        let system = format!("{SYSTEM_PROMPT}\n\n---\n\n{}", grounding(assessment));

        Ok(Prepared {
            system,
            turns,
            redacted: redacted_kinds,
            remote,
        })
    }

    /// Build the HTTP request for a prepared conversation.
    pub fn request(
        &self,
        prepared: &Prepared,
        api_key: Option<&str>,
    ) -> Result<OutboundRequest, AdvisorError> {
        if self.config.key_ref.is_some() && api_key.is_none() {
            return Err(AdvisorError::MissingApiKey(self.config.provider.label()));
        }

        Ok(self
            .config
            .build_request(&prepared.system, &prepared.turns, api_key))
    }
}
