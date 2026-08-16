//! Model provider configuration.
//!
//! Freshet is bring-your-own-key: the user supplies an Anthropic, OpenAI or
//! Biber key, or points at a local model. We never proxy inference through our
//! own servers, which keeps us out of the position of holding taxpayer prompts.
//!
//! This module builds requests but does not send them. Transport lives in the
//! app layer so that the advisor's policy logic stays free of I/O and can be
//! tested exhaustively.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Provider {
    Anthropic {
        model: String,
    },
    OpenAi {
        model: String,
    },
    /// The user's own Biber AI gateway.
    Biber {
        base_url: String,
        model: String,
    },
    /// An OpenAI-compatible endpoint on the user's own machine or network.
    /// Nothing leaves the device, so no egress consent is required.
    Local {
        base_url: String,
        model: String,
    },
}

impl Provider {
    /// Whether using this provider sends taxpayer data off the device.
    pub fn is_remote(&self) -> bool {
        !matches!(self, Provider::Local { .. })
    }

    pub fn label(&self) -> String {
        match self {
            Provider::Anthropic { model } => format!("Anthropic ({model})"),
            Provider::OpenAi { model } => format!("OpenAI ({model})"),
            Provider::Biber { model, .. } => format!("Biber ({model})"),
            Provider::Local { model, .. } => format!("local model ({model})"),
        }
    }

    pub fn model(&self) -> &str {
        match self {
            Provider::Anthropic { model }
            | Provider::OpenAi { model }
            | Provider::Biber { model, .. }
            | Provider::Local { model, .. } => model,
        }
    }
}

/// Where the API key lives. The key itself is never written to the config file
/// or to a log -- only the name of the OS keychain entry holding it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct KeyRef {
    /// Keychain service name, e.g. `freshet.provider.anthropic`.
    pub keychain_entry: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProviderConfig {
    pub provider: Provider,
    /// `None` for local providers that need no auth.
    pub key_ref: Option<KeyRef>,
    #[serde(default = "default_max_tokens")]
    pub max_tokens: u32,
}

fn default_max_tokens() -> u32 {
    2048
}

/// A ready-to-send HTTP request. The app layer performs the actual call.
#[derive(Debug, Clone)]
pub struct OutboundRequest {
    pub url: String,
    pub headers: Vec<(String, String)>,
    pub body: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Turn {
    pub role: Role,
    pub content: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    User,
    Assistant,
}

impl Role {
    fn as_str(self) -> &'static str {
        match self {
            Role::User => "user",
            Role::Assistant => "assistant",
        }
    }
}

impl ProviderConfig {
    /// Build the provider-specific request for a conversation.
    ///
    /// `api_key` is passed in at call time rather than held on the config, so a
    /// serialized `ProviderConfig` can never contain a secret.
    pub fn build_request(&self, system: &str, turns: &[Turn], api_key: Option<&str>) -> OutboundRequest {
        let messages: Vec<Value> = turns
            .iter()
            .map(|t| json!({ "role": t.role.as_str(), "content": t.content }))
            .collect();

        match &self.provider {
            Provider::Anthropic { model } => OutboundRequest {
                url: "https://api.anthropic.com/v1/messages".into(),
                headers: vec![
                    ("content-type".into(), "application/json".into()),
                    ("anthropic-version".into(), "2023-06-01".into()),
                    ("x-api-key".into(), api_key.unwrap_or_default().into()),
                ],
                body: json!({
                    "model": model,
                    "max_tokens": self.max_tokens,
                    "system": system,
                    "messages": messages,
                }),
            },

            Provider::OpenAi { model } => Self::openai_compatible(
                "https://api.openai.com/v1",
                model,
                system,
                &messages,
                self.max_tokens,
                api_key,
            ),

            Provider::Biber { base_url, model } | Provider::Local { base_url, model } => {
                Self::openai_compatible(
                    base_url.trim_end_matches('/'),
                    model,
                    system,
                    &messages,
                    self.max_tokens,
                    api_key,
                )
            }
        }
    }

    fn openai_compatible(
        base: &str,
        model: &str,
        system: &str,
        messages: &[Value],
        max_tokens: u32,
        api_key: Option<&str>,
    ) -> OutboundRequest {
        let mut all = vec![json!({ "role": "system", "content": system })];
        all.extend_from_slice(messages);

        let mut headers = vec![("content-type".to_string(), "application/json".to_string())];
        if let Some(key) = api_key {
            headers.push(("authorization".into(), format!("Bearer {key}")));
        }

        OutboundRequest {
            url: format!("{base}/chat/completions"),
            headers,
            body: json!({
                "model": model,
                "max_tokens": max_tokens,
                "messages": all,
            }),
        }
    }
}
