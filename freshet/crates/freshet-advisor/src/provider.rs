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
    /// An OpenAI-compatible endpoint on the user's own machine.
    ///
    /// Only genuinely local when the URL is: see [`Provider::is_remote`],
    /// which asks the destination rather than the variant.
    Local {
        base_url: String,
        model: String,
    },
}

/// Whether a URL's host is this machine or a private network.
///
/// Deliberately conservative: anything it cannot confidently classify as local
/// is treated as remote. A false "remote" costs a consent prompt; a false
/// "local" sends a tax return to a stranger.
///
/// Hostname resolution is not attempted. A name could resolve anywhere, and
/// resolving it here would mean a DNS lookup inside a policy decision — and a
/// name that resolved to loopback today could resolve elsewhere tomorrow,
/// which is a consent decision made on a value that does not hold still.
/// `localhost` is accepted by name because it is the one name whose meaning is
/// fixed by standard.
pub fn host_is_local(base_url: &str) -> bool {
    let rest = match base_url.split_once("://") {
        Some((scheme, rest)) if scheme.eq_ignore_ascii_case("http") => rest,
        Some((scheme, rest)) if scheme.eq_ignore_ascii_case("https") => rest,
        // No scheme, or one we do not understand. Not confidently local.
        _ => return false,
    };

    // Strip credentials, path, query, and then the port.
    let authority = rest.split(['/', '?', '#']).next().unwrap_or("");
    let host_port = authority.rsplit_once('@').map_or(authority, |(_, h)| h);

    let host = if let Some(end) = host_port.strip_prefix('[') {
        // IPv6 literal: [::1]:11434
        match end.split_once(']') {
            Some((inner, _)) => inner,
            None => return false,
        }
    } else {
        host_port.split(':').next().unwrap_or("")
    };

    if host.eq_ignore_ascii_case("localhost") {
        return true;
    }

    match host.parse::<std::net::IpAddr>() {
        Ok(std::net::IpAddr::V4(v4)) => {
            v4.is_loopback() || v4.is_private() || v4.is_link_local()
        }
        Ok(std::net::IpAddr::V6(v6)) => {
            // Unique-local (fc00::/7) and link-local (fe80::/10) alongside ::1.
            let first = v6.octets()[0];
            v6.is_loopback() || (first & 0xfe) == 0xfc || (first == 0xfe && (v6.octets()[1] & 0xc0) == 0x80)
        }
        // A bare hostname. See above: not resolved, so not trusted.
        Err(_) => false,
    }
}

impl Provider {
    /// Whether using this provider sends taxpayer data off the device.
    ///
    /// Asks the **destination**, not the variant. `Local` was once assumed
    /// local by construction, which made "Local model" pointed at a public
    /// host a silent, consentless egress of the whole return — with the UI
    /// stating that nothing was leaving. The variant is a label the user
    /// chose; the URL is where the data actually goes.
    pub fn is_remote(&self) -> bool {
        match self {
            Provider::Local { base_url, .. } => !host_is_local(base_url),
            _ => true,
        }
    }

    /// The identity consent is recorded against.
    ///
    /// Distinct from [`label`], which is for display. Consent is agreement to
    /// disclose to a **recipient**, so the recipient's address belongs in the
    /// key: re-pointing a gateway at a different company must invalidate it.
    /// The label omits `base_url`, so using it here meant that exact change
    /// was the one thing consent could not notice.
    ///
    /// [`label`]: Provider::label
    pub fn consent_key(&self) -> String {
        match self {
            Provider::Biber { base_url, model } => format!("Biber ({model}) at {base_url}"),
            Provider::Local { base_url, model } => {
                format!("local model ({model}) at {base_url}")
            }
            other => other.label(),
        }
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
