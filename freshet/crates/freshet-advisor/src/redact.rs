//! PII detection and redaction.
//!
//! This is the boundary between the taxpayer's machine and a third-party model
//! provider. Anything crossing it has left the user's control: prompts are
//! routinely retained by providers for abuse monitoring, so a SIN that reaches
//! an inference endpoint is a reportable privacy breach, not a bug.
//!
//! The design is deliberately conservative. Detectors that could be noisy
//! (9-digit SIN, card numbers) are checksum-validated to keep false positives
//! low, and everything else errs toward over-redaction: a mangled postal code
//! costs the user nothing, a leaked one costs them their address.

use std::sync::OnceLock;

use regex::Regex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PiiKind {
    /// Social insurance number. The single most damaging field in a return.
    Sin,
    /// CRA business number, e.g. `123456789 RC0001`.
    BusinessNumber,
    CreditCard,
    Email,
    Phone,
    PostalCode,
    /// A date specific enough to be a date of birth.
    DateOfBirth,
}

impl PiiKind {
    pub fn placeholder(self) -> &'static str {
        match self {
            PiiKind::Sin => "[SIN]",
            PiiKind::BusinessNumber => "[BUSINESS-NUMBER]",
            PiiKind::CreditCard => "[CARD-NUMBER]",
            PiiKind::Email => "[EMAIL]",
            PiiKind::Phone => "[PHONE]",
            PiiKind::PostalCode => "[POSTAL-CODE]",
            PiiKind::DateOfBirth => "[DATE]",
        }
    }

    /// Whether finding this after redaction should hard-fail the request.
    pub fn is_critical(self) -> bool {
        matches!(self, PiiKind::Sin | PiiKind::BusinessNumber | PiiKind::CreditCard)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Finding {
    pub kind: PiiKind,
    pub start: usize,
    pub end: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct Redaction {
    /// The text with every finding replaced by its placeholder.
    pub text: String,
    pub findings: Vec<Finding>,
}

impl Redaction {
    pub fn is_clean(&self) -> bool {
        self.findings.is_empty()
    }

    pub fn kinds(&self) -> Vec<PiiKind> {
        let mut kinds: Vec<_> = self.findings.iter().map(|f| f.kind).collect();
        kinds.dedup();
        kinds
    }
}

struct Rule {
    kind: PiiKind,
    re: Regex,
    /// Lower runs first and wins an overlap. A SIN must be claimed before the
    /// phone-number rule can eat the same nine digits.
    priority: u8,
    validate: Option<fn(&str) -> bool>,
}

fn rules() -> &'static [Rule] {
    static RULES: OnceLock<Vec<Rule>> = OnceLock::new();

    RULES
        .get_or_init(|| {
            vec![
                Rule {
                    kind: PiiKind::BusinessNumber,
                    re: Regex::new(r"(?i)\b\d{9}\s?(?:RC|RP|RT|RM|RZ)\s?\d{4}\b").unwrap(),
                    priority: 0,
                    validate: None,
                },
                Rule {
                    kind: PiiKind::CreditCard,
                    re: Regex::new(r"\b(?:\d[ -]?){12,18}\d\b").unwrap(),
                    priority: 1,
                    validate: Some(luhn),
                },
                Rule {
                    kind: PiiKind::Sin,
                    re: Regex::new(r"\b\d{3}[- ]?\d{3}[- ]?\d{3}\b").unwrap(),
                    priority: 2,
                    validate: Some(luhn),
                },
                Rule {
                    kind: PiiKind::Email,
                    re: Regex::new(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b").unwrap(),
                    priority: 3,
                    validate: None,
                },
                Rule {
                    kind: PiiKind::PostalCode,
                    re: Regex::new(r"(?i)\b[abceghjklmnprstvxy]\d[abceghjklmnprstvwxyz][ -]?\d[abceghjklmnprstvwxyz]\d\b")
                        .unwrap(),
                    priority: 4,
                    validate: None,
                },
                Rule {
                    kind: PiiKind::Phone,
                    re: Regex::new(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")
                        .unwrap(),
                    priority: 5,
                    validate: None,
                },
                Rule {
                    kind: PiiKind::DateOfBirth,
                    re: Regex::new(r"\b(?:19|20)\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b")
                        .unwrap(),
                    priority: 6,
                    validate: None,
                },
            ]
        })
        .as_slice()
}

/// The Luhn checksum, used by both Canadian SINs and payment cards.
fn luhn(s: &str) -> bool {
    let digits: Vec<u32> = s.chars().filter_map(|c| c.to_digit(10)).collect();
    if digits.len() < 9 {
        return false;
    }

    let sum: u32 = digits
        .iter()
        .rev()
        .enumerate()
        .map(|(i, &d)| {
            if i % 2 == 1 {
                let doubled = d * 2;
                if doubled > 9 {
                    doubled - 9
                } else {
                    doubled
                }
            } else {
                d
            }
        })
        .sum();

    sum % 10 == 0
}

#[derive(Debug, Clone, Default)]
pub struct Redactor;

impl Redactor {
    pub fn new() -> Self {
        Self
    }

    /// Locate PII without modifying the text.
    pub fn scan(&self, text: &str) -> Vec<Finding> {
        let mut hits: Vec<(u8, Finding)> = Vec::new();

        for rule in rules() {
            for m in rule.re.find_iter(text) {
                if let Some(check) = rule.validate {
                    if !check(m.as_str()) {
                        continue;
                    }
                }
                hits.push((
                    rule.priority,
                    Finding {
                        kind: rule.kind,
                        start: m.start(),
                        end: m.end(),
                    },
                ));
            }
        }

        // Resolve overlaps: prefer the higher-priority rule, then the longer
        // match. Without this a SIN would be reported twice, once as a phone.
        hits.sort_by_key(|(prio, f)| (*prio, std::cmp::Reverse(f.end - f.start), f.start));

        let mut kept: Vec<Finding> = Vec::new();
        for (_, f) in hits {
            let overlaps = kept.iter().any(|k| f.start < k.end && k.start < f.end);
            if !overlaps {
                kept.push(f);
            }
        }

        kept.sort_by_key(|f| f.start);
        kept
    }

    /// Replace every finding with its placeholder.
    pub fn redact(&self, text: &str) -> Redaction {
        let findings = self.scan(text);
        let mut out = String::with_capacity(text.len());
        let mut cursor = 0;

        for f in &findings {
            out.push_str(&text[cursor..f.start]);
            out.push_str(f.kind.placeholder());
            cursor = f.end;
        }
        out.push_str(&text[cursor..]);

        Redaction {
            text: out,
            findings,
        }
    }
}
