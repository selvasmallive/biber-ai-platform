//! Tests for the egress boundary.
//!
//! Every test here describes a way taxpayer data could leak. They are the
//! reason this crate exists.

use std::collections::BTreeMap;

use freshet_advisor::{
    Advisor, AdvisorError, Consent, KeyRef, PiiKind, Provider, ProviderConfig, Redactor, Role, Turn,
};
use freshet_engine::Assessment;

/// A structurally valid SIN: nine digits that pass the Luhn checksum.
const VALID_SIN: &str = "046 454 286";

fn assessment() -> Assessment {
    Assessment {
        tax_year: 2025,
        province: "on".into(),
        lines: BTreeMap::new(),
        audit: Vec::new(),
        warnings: Vec::new(),
        diagnostics: Vec::new(),
    }
}

fn remote() -> Advisor {
    Advisor::new(ProviderConfig {
        provider: Provider::OpenAi {
            model: "gpt-test".into(),
        },
        key_ref: Some(KeyRef {
            keychain_entry: "freshet.provider.openai".into(),
        }),
        max_tokens: 1024,
    })
}

fn local() -> Advisor {
    Advisor::new(ProviderConfig {
        provider: Provider::Local {
            base_url: "http://127.0.0.1:11434/v1".into(),
            model: "llama-test".into(),
        },
        key_ref: None,
        max_tokens: 1024,
    })
}

fn consent_for(a: &Advisor) -> Consent {
    Consent {
        provider_label: a.config.provider.label(),
        granted_at_unix: 1_760_000_000,
    }
}

// -- redaction ------------------------------------------------------------

#[test]
fn a_valid_sin_is_redacted() {
    let r = Redactor::new().redact(&format!("my sin is {VALID_SIN} ok"));

    assert_eq!(r.text, "my sin is [SIN] ok");
    assert_eq!(r.kinds(), vec![PiiKind::Sin]);
}

#[test]
fn sin_is_caught_in_every_common_format() {
    let redactor = Redactor::new();

    for form in ["046 454 286", "046-454-286", "046454286"] {
        let r = redactor.redact(form);
        assert_eq!(r.text, "[SIN]", "missed SIN written as {form}");
    }
}

#[test]
fn nine_digits_that_fail_the_checksum_are_left_alone() {
    // Over-redaction is safe; this guards the other direction, so that ordinary
    // reference numbers in a conversation survive intact.
    let r = Redactor::new().redact("invoice 123456789 is unpaid");

    assert!(r.is_clean(), "false positive: {:?}", r.findings);
    assert_eq!(r.text, "invoice 123456789 is unpaid");
}

#[test]
fn contact_details_and_postal_codes_are_redacted() {
    let r = Redactor::new()
        .redact("reach me at jo@example.ca or 416-555-0134, I'm at M5V 3L9");

    assert_eq!(r.text, "reach me at [EMAIL] or [PHONE], I'm at [POSTAL-CODE]");
}

#[test]
fn a_business_number_wins_over_the_overlapping_sin_and_phone_rules() {
    let r = Redactor::new().redact("BN 123456789 RC0001 for the corp");

    assert_eq!(r.text, "BN [BUSINESS-NUMBER] for the corp");
    assert_eq!(r.kinds(), vec![PiiKind::BusinessNumber]);
}

#[test]
fn each_run_of_pii_is_reported_once_not_once_per_matching_rule() {
    let findings = Redactor::new().scan(VALID_SIN);
    assert_eq!(findings.len(), 1, "overlapping findings: {findings:?}");
}

// -- consent --------------------------------------------------------------

#[test]
fn a_remote_provider_refuses_to_send_without_consent() {
    let err = remote()
        .prepare(&assessment(), &[], "how do I save tax?", None)
        .unwrap_err();

    assert!(matches!(err, AdvisorError::ConsentRequired { .. }));
}

#[test]
fn consent_does_not_carry_over_when_the_provider_changes() {
    let stale = Consent {
        provider_label: "Anthropic (claude-test)".into(),
        granted_at_unix: 1_760_000_000,
    };

    let err = remote()
        .prepare(&assessment(), &[], "hello", Some(&stale))
        .unwrap_err();

    match err {
        AdvisorError::ConsentStale { granted_for, current } => {
            assert_eq!(granted_for, "Anthropic (claude-test)");
            assert_eq!(current, "OpenAI (gpt-test)");
        }
        other => panic!("expected stale consent, got {other}"),
    }
}

#[test]
fn a_local_model_needs_no_consent_because_nothing_leaves_the_device() {
    let prepared = local()
        .prepare(&assessment(), &[], "how do I save tax?", None)
        .expect("local inference should not be gated on egress consent");

    assert!(!prepared.remote);
}

// -- assembled request ----------------------------------------------------

#[test]
fn pii_is_stripped_from_the_message_that_actually_gets_sent() {
    let advisor = remote();
    let consent = consent_for(&advisor);

    let prepared = advisor
        .prepare(
            &assessment(),
            &[],
            &format!("I'm at M5V 3L9, sin {VALID_SIN}, what can I claim?"),
            Some(&consent),
        )
        .unwrap();

    let sent = &prepared.turns.last().unwrap().content;
    assert!(!sent.contains("046"), "SIN reached the outbound turn: {sent}");
    assert!(!sent.contains("M5V"), "postal code reached the outbound turn: {sent}");
    assert!(prepared.redacted.contains(&PiiKind::Sin));
}

#[test]
fn earlier_turns_are_redacted_too_not_just_the_newest_message() {
    let advisor = remote();
    let consent = consent_for(&advisor);

    let history = vec![Turn {
        role: Role::User,
        content: format!("my sin is {VALID_SIN}"),
    }];

    let prepared = advisor
        .prepare(&assessment(), &history, "and now?", Some(&consent))
        .unwrap();

    assert!(
        prepared.turns.iter().all(|t| !t.content.contains("046")),
        "history leaked a SIN: {:?}",
        prepared.turns
    );
}

#[test]
fn the_system_prompt_carries_the_return_but_never_an_identity() {
    let advisor = local();
    let prepared = advisor
        .prepare(&assessment(), &[], "hi", None)
        .unwrap();

    assert!(prepared.system.contains("Tax year: 2025"));
    assert!(prepared.system.contains("Province of residence: ON"));
    assert!(prepared.system.contains("must not ask for"));
}

#[test]
fn a_request_without_its_key_is_refused_rather_than_sent_unauthenticated() {
    let advisor = remote();
    let consent = consent_for(&advisor);
    let prepared = advisor
        .prepare(&assessment(), &[], "hi", Some(&consent))
        .unwrap();

    assert!(matches!(
        advisor.request(&prepared, None),
        Err(AdvisorError::MissingApiKey(_))
    ));
}

#[test]
fn a_serialized_provider_config_never_contains_the_secret() {
    let advisor = remote();
    let json = serde_json::to_string(&advisor.config).unwrap();

    assert!(json.contains("keychain_entry"));
    assert!(
        !json.to_lowercase().contains("sk-"),
        "config serialization looks like it carries a key: {json}"
    );
}

#[test]
fn the_outbound_body_matches_the_provider_wire_format() {
    let advisor = remote();
    let consent = consent_for(&advisor);
    let prepared = advisor
        .prepare(&assessment(), &[], "hi", Some(&consent))
        .unwrap();

    let req = advisor.request(&prepared, Some("test-key")).unwrap();

    assert_eq!(req.url, "https://api.openai.com/v1/chat/completions");
    assert!(req
        .headers
        .iter()
        .any(|(k, v)| k == "authorization" && v == "Bearer test-key"));

    // OpenAI takes the system prompt as the first message, not a top-level field.
    let messages = req.body["messages"].as_array().unwrap();
    assert_eq!(messages[0]["role"], "system");
    assert_eq!(messages[1]["content"], "hi");
}

#[test]
fn anthropic_gets_a_top_level_system_field_and_an_x_api_key_header() {
    let advisor = Advisor::new(ProviderConfig {
        provider: Provider::Anthropic {
            model: "claude-test".into(),
        },
        key_ref: Some(KeyRef {
            keychain_entry: "freshet.provider.anthropic".into(),
        }),
        max_tokens: 512,
    });
    let consent = consent_for(&advisor);
    let prepared = advisor
        .prepare(&assessment(), &[], "hi", Some(&consent))
        .unwrap();

    let req = advisor.request(&prepared, Some("test-key")).unwrap();

    assert_eq!(req.url, "https://api.anthropic.com/v1/messages");
    assert!(req.body["system"].is_string());
    assert!(req.headers.iter().any(|(k, _)| k == "x-api-key"));
    assert!(req.headers.iter().any(|(k, _)| k == "anthropic-version"));
}

// -- the destination, not the label ---------------------------------------
//
// Found by an audit on 2026-10-17. Every test above passed while both of
// these held, which is why they are here: the suite was checking the shape of
// the configuration rather than where the data was going.

fn local_provider(url: &str) -> Provider {
    Provider::Local {
        base_url: url.into(),
        model: "llama-test".into(),
    }
}

fn local_at(url: &str) -> Advisor {
    Advisor::new(ProviderConfig {
        provider: local_provider(url),
        key_ref: None,
        max_tokens: 1024,
    })
}

/// A "Local model" pointed at a public host is a remote provider.
///
/// `is_remote()` answered from the enum variant, so this skipped the consent
/// block entirely — while the settings screen told the user, in three places,
/// that nothing was leaving the device. The whole return went to a stranger
/// and the product reassured them while it happened.
#[test]
fn a_local_provider_pointed_at_the_internet_is_remote_and_needs_consent() {
    let advisor = local_at("https://not-my-machine.example.com/v1");

    assert!(local_provider("https://not-my-machine.example.com/v1").is_remote());

    let err = advisor
        .prepare(&assessment(), &[], "hello", None)
        .unwrap_err();

    assert!(
        matches!(err, AdvisorError::ConsentRequired { .. }),
        "expected consent to be required, got {err}"
    );
}

/// And a genuinely local one still needs none, in every form a person writes.
#[test]
fn a_local_provider_on_this_machine_needs_no_consent() {
    for url in [
        "http://localhost:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://[::1]:11434/v1",
        "http://192.168.1.50:8080/v1",
        "http://10.0.0.7:8080/v1",
        "https://127.0.0.1/v1",
    ] {
        let advisor = local_at(url);
        assert!(!local_provider(url).is_remote(), "{url} should be local");
        advisor
            .prepare(&assessment(), &[], "hello", None)
            .unwrap_or_else(|e| panic!("{url} should need no consent, got {e}"));
    }
}

/// A bare hostname is not trusted, even one that looks harmless.
///
/// Resolving it would mean a DNS lookup inside a policy decision, and a name
/// that resolves to loopback today can resolve elsewhere tomorrow. Anything
/// not confidently local is remote; a false "remote" costs a prompt, a false
/// "local" costs a tax return.
#[test]
fn a_hostname_is_not_assumed_local() {
    for url in [
        "http://my-nas/v1",
        "http://localhost.evil.example.com/v1",
        "http://127.0.0.1.evil.example.com/v1",
        "ftp://127.0.0.1/v1",
        "127.0.0.1:11434",
    ] {
        assert!(
            local_provider(url).is_remote(),
            "{url} must not be treated as local"
        );
    }
}

/// Re-pointing a gateway at another company invalidates consent.
///
/// Consent identity was the display label, and the label omits `base_url`.
/// Both of these are `Biber (biber-1)`, so consent survived a change of
/// recipient — the most material provider change there is, and the one the
/// key could not see.
#[test]
fn consent_does_not_survive_a_change_of_destination_host() {
    let mine = Provider::Biber {
        base_url: "https://gw.mycorp.internal/v1".into(),
        model: "biber-1".into(),
    };
    let theirs = Provider::Biber {
        base_url: "https://someone-else.example.com/v1".into(),
        model: "biber-1".into(),
    };

    // The thing that made this invisible: the labels are identical.
    assert_eq!(mine.label(), theirs.label());
    assert_ne!(mine.consent_key(), theirs.consent_key());

    let advisor = Advisor::new(ProviderConfig {
        provider: theirs,
        key_ref: Some(KeyRef {
            keychain_entry: "test".into(),
        }),
        max_tokens: 1024,
    });

    let granted_for_mine = Consent {
        provider_label: mine.consent_key(),
        granted_at_unix: 1_760_000_000,
    };

    let err = advisor
        .prepare(&assessment(), &[], "hello", Some(&granted_for_mine))
        .unwrap_err();

    assert!(
        matches!(err, AdvisorError::ConsentStale { .. }),
        "consent must not follow the data to a different host, got {err}"
    );
}
