//! Form definitions: the ordered set of lines that make up a return.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::expr::{Cond, Expr};
use crate::EngineError;

#[derive(Debug, Clone, Copy, Deserialize, Serialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    /// The return is wrong or internally inconsistent. Blocks filing.
    Error,
    /// Probably wrong, but legitimately possible. Worth a second look.
    Warning,
    /// Something the taxpayer should know, not a defect.
    Info,
}

/// A review rule.
///
/// Checks are written in the same expression language as the form lines, so a
/// tax professional can review them without reading Rust, and so a rule can
/// reference any computed line without special plumbing. `when` is the
/// condition under which the check *fires* — that is, when something is wrong.
#[derive(Debug, Clone, Deserialize)]
pub struct CheckDef {
    pub id: String,
    pub severity: Severity,
    /// What is wrong, in the taxpayer's language.
    pub message: String,
    /// What to do about it.
    #[serde(default)]
    pub help: Option<String>,
    pub when: Cond,
}

/// How a computed line is rounded when it is written to the return.
#[derive(Debug, Clone, Copy, Default, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Rounding {
    /// Nearest cent, halves away from zero. The default for money.
    #[default]
    Cents,
    /// Nearest dollar.
    Dollars,
    /// No rounding -- for intermediate ratios and rates.
    None,
}

#[derive(Debug, Clone, Deserialize)]
pub struct LineDef {
    /// Namespaced line identifier, e.g. `fed.23600` or `on.5804`.
    pub id: String,
    /// Human label, shown in the UI and in the audit trail.
    pub label: String,
    pub expr: Expr,
    #[serde(default)]
    pub rounding: Rounding,
    /// Optional plain-language explanation surfaced in the UI and given to the
    /// advisor as grounding context.
    #[serde(default)]
    pub note: Option<String>,
}

/// What the federal return requires of every province.
///
/// Two lines, and nothing else. A province computes its tax however its own
/// legislation says — Ontario needs a surtax, a health premium and a low-income
/// reduction; Alberta needs none of them — and presents the result through
/// these. That is what keeps the federal form free of any one jurisdiction.
pub const PROVINCIAL_CONTRACT: &[&str] = &["prov.tax", "prov.refundable_credits"];

#[derive(Debug, Clone, Deserialize)]
pub struct FormSet {
    pub tax_year: u16,
    /// Province of residence on Dec 31, e.g. `"on"`.
    pub province: String,
    pub lines: Vec<LineDef>,
    /// Lines to surface as the headline result, in display order.
    #[serde(default)]
    pub summary: Vec<String>,
    /// Review rules run after every line resolves.
    #[serde(default)]
    pub checks: Vec<CheckDef>,
    #[serde(skip)]
    index: HashMap<String, usize>,
}

impl FormSet {
    pub fn from_json(s: &str) -> Result<Self, EngineError> {
        let mut set: FormSet =
            serde_json::from_str(s).map_err(|e| EngineError::BadForm(e.to_string()))?;
        set.reindex()?;
        Ok(set)
    }

    /// Build a return from the federal form plus one province.
    ///
    /// The federal T1 is three quarters of the return and identical everywhere,
    /// so it is stored once and composed with a provincial form at load time.
    /// Keeping this in the engine rather than in the loader is deliberate: the
    /// id index is an invariant of `FormSet`, and code that appends lines
    /// without rebuilding it produces a set that silently cannot resolve them.
    ///
    /// Reindexing also enforces the rule that matters once there are thirteen
    /// provincial files — a province that defines a line the federal form
    /// already owns is rejected as a duplicate rather than quietly shadowing it.
    pub fn compose(federal: FormSet, provincial: FormSet) -> Result<FormSet, EngineError> {
        let province = provincial.province.clone();
        let mut federal = Self::merge(federal, provincial)?;
        federal.province = province;

        // The federal return reaches into the province through exactly these
        // two ids and no others, so a province that omits one produces a set
        // that resolves nothing. Failing here names the missing line; failing
        // later names some federal line that looks unrelated.
        for required in PROVINCIAL_CONTRACT {
            if !federal.index.contains_key(*required) {
                return Err(EngineError::UnknownLine(format!(
                    "{} does not define {required}, which every province must supply",
                    federal.province
                )));
            }
        }

        Ok(federal)
    }

    /// Join a fragment into a form.
    ///
    /// Separate from [`compose`] because not every join is federal-plus-province.
    /// Capital cost allowance is the same arithmetic on a T1 and a T2 — classes,
    /// the half-year rule, recapture, terminal loss — so it lives once and is
    /// merged into both. Applying the provincial contract to that would be
    /// nonsense: a fragment supplies lines, not a jurisdiction.
    ///
    /// Reindexing still rejects a fragment that redefines a line the base
    /// already owns.
    ///
    /// [`compose`]: FormSet::compose
    pub fn merge(mut base: FormSet, fragment: FormSet) -> Result<FormSet, EngineError> {
        base.lines.extend(fragment.lines);
        base.checks.extend(fragment.checks);
        base.reindex()?;

        Ok(base)
    }

    fn reindex(&mut self) -> Result<(), EngineError> {
        self.index.clear();
        for (i, line) in self.lines.iter().enumerate() {
            if self.index.insert(line.id.clone(), i).is_some() {
                return Err(EngineError::DuplicateLine(line.id.clone()));
            }
        }
        Ok(())
    }

    pub fn line(&self, id: &str) -> Result<&LineDef, EngineError> {
        self.index
            .get(id)
            .map(|&i| &self.lines[i])
            .ok_or_else(|| EngineError::UnknownLine(id.to_string()))
    }
}
