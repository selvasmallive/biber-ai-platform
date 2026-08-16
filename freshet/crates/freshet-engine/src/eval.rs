//! The evaluator.
//!
//! Lines are resolved lazily and memoized, so a form is a DAG rather than an
//! ordered spreadsheet: line 42 may reference line 99 without the author having
//! to topologically sort by hand. Cycles are a hard error rather than a hang.

use std::collections::{BTreeMap, HashMap};

use rust_decimal::Decimal;
use serde::Serialize;

use crate::decimal::{floor_zero, round_cents, round_dollars};
use crate::expr::{Cond, Expr};
use crate::facts::FactSet;
use crate::form::{FormSet, Rounding, Severity};
use crate::params::PackSet;
use crate::EngineError;

/// One resolved line, retained so the UI can show "how did we get this?" and so
/// a reviewer can reconstruct the return without rerunning the engine.
#[derive(Debug, Clone, Serialize)]
pub struct AuditEntry {
    pub id: String,
    pub label: String,
    pub value: Decimal,
    pub note: Option<String>,
}

/// A review rule that fired.
#[derive(Debug, Clone, Serialize)]
pub struct Diagnostic {
    pub id: String,
    pub severity: Severity,
    pub message: String,
    pub help: Option<String>,
}

/// The result of computing a return.
#[derive(Debug, Clone, Serialize)]
pub struct Assessment {
    pub tax_year: u16,
    pub province: String,
    pub lines: BTreeMap<String, Decimal>,
    /// Resolution order, which is also a valid explanation order.
    pub audit: Vec<AuditEntry>,
    /// Problems with the *software*, e.g. parameters not yet human-verified.
    pub warnings: Vec<String>,
    /// Problems with the *return*, from the form's review rules.
    pub diagnostics: Vec<Diagnostic>,
}

impl Assessment {
    pub fn get(&self, id: &str) -> Option<Decimal> {
        self.lines.get(id).copied()
    }

    pub fn errors(&self) -> impl Iterator<Item = &Diagnostic> {
        self.diagnostics
            .iter()
            .filter(|d| d.severity == Severity::Error)
    }

    pub fn has_errors(&self) -> bool {
        self.errors().next().is_some()
    }

    /// True when the return may be transmitted to CRA.
    ///
    /// Two independent gates: every tax parameter behind it must be verified
    /// against its citation, and no review rule may be reporting an error. The
    /// first is our correctness; the second is the taxpayer's.
    pub fn is_filable(&self) -> bool {
        self.warnings.is_empty() && !self.has_errors()
    }
}

pub struct Evaluator<'a> {
    forms: &'a FormSet,
    packs: &'a PackSet,
    facts: &'a FactSet,
    memo: HashMap<String, Decimal>,
    stack: Vec<String>,
    audit: Vec<AuditEntry>,
}

impl<'a> Evaluator<'a> {
    pub fn new(forms: &'a FormSet, packs: &'a PackSet, facts: &'a FactSet) -> Self {
        Self {
            forms,
            packs,
            facts,
            memo: HashMap::new(),
            stack: Vec::new(),
            audit: Vec::new(),
        }
    }

    /// Resolve every line in the form set.
    pub fn run(mut self) -> Result<Assessment, EngineError> {
        for line in &self.forms.lines {
            self.line(&line.id)?;
        }

        let lines = self
            .memo
            .iter()
            .map(|(k, v)| (k.clone(), *v))
            .collect::<BTreeMap<_, _>>();

        let warnings = self
            .packs
            .unverified()
            .into_iter()
            .map(|k| format!("unverified tax parameter: {k}"))
            .collect();

        // Checks run last, so every line they reference is already resolved and
        // a rule cannot accidentally change what it is judging.
        let mut diagnostics = Vec::new();
        for check in &self.forms.checks {
            if self.cond(&check.when)? {
                diagnostics.push(Diagnostic {
                    id: check.id.clone(),
                    severity: check.severity,
                    message: check.message.clone(),
                    help: check.help.clone(),
                });
            }
        }
        diagnostics.sort_by_key(|d| d.severity);

        Ok(Assessment {
            tax_year: self.forms.tax_year,
            province: self.forms.province.clone(),
            lines,
            audit: self.audit,
            warnings,
            diagnostics,
        })
    }

    fn line(&mut self, id: &str) -> Result<Decimal, EngineError> {
        if let Some(v) = self.memo.get(id) {
            return Ok(*v);
        }

        if self.stack.iter().any(|s| s == id) {
            let mut path = self.stack.clone();
            path.push(id.to_string());
            return Err(EngineError::CircularReference(path.join(" -> ")));
        }

        let def = self.forms.line(id)?;
        // Clone what we need so `self` is free for the recursive descent.
        let (expr, label, rounding, note) = (
            def.expr.clone(),
            def.label.clone(),
            def.rounding,
            def.note.clone(),
        );

        self.stack.push(id.to_string());
        let raw = self.eval(&expr);
        self.stack.pop();

        let value = match rounding {
            Rounding::Cents => round_cents(raw?),
            Rounding::Dollars => round_dollars(raw?),
            Rounding::None => raw?,
        };

        self.memo.insert(id.to_string(), value);
        self.audit.push(AuditEntry {
            id: id.to_string(),
            label,
            value,
            note,
        });

        Ok(value)
    }

    fn eval(&mut self, e: &Expr) -> Result<Decimal, EngineError> {
        Ok(match e {
            Expr::Const { value } => *value,
            Expr::Fact { key } => self.facts.get(key),
            Expr::Line { id } => self.line(id)?,
            Expr::Param { key } => self.packs.scalar(key)?,

            Expr::Sum { of } => {
                let mut acc = Decimal::ZERO;
                for x in of {
                    acc += self.eval(x)?;
                }
                acc
            }

            Expr::Sub { from, minus } => self.eval(from)? - self.eval(minus)?,
            Expr::Mul { of, by } => self.eval(of)? * self.eval(by)?,

            Expr::Div { of, by } => {
                let denom = self.eval(by)?;
                if denom.is_zero() {
                    return Err(EngineError::DivideByZero);
                }
                self.eval(of)? / denom
            }

            Expr::Min { of } => self.fold(of, |a, b| if b < a { b } else { a })?,
            Expr::Max { of } => self.fold(of, |a, b| if b > a { b } else { a })?,

            Expr::FloorZero { of } => floor_zero(self.eval(of)?),

            Expr::Clamp { value, lo, hi } => {
                let (v, lo, hi) = (self.eval(value)?, self.eval(lo)?, self.eval(hi)?);
                if v < lo {
                    lo
                } else if v > hi {
                    hi
                } else {
                    v
                }
            }

            Expr::Round { of, dp } => {
                use rust_decimal::RoundingStrategy;
                self.eval(of)?
                    .round_dp_with_strategy(*dp, RoundingStrategy::MidpointAwayFromZero)
            }

            Expr::Ceil { of } => self.eval(of)?.ceil(),
            Expr::Floor { of } => self.eval(of)?.floor(),

            Expr::Bracket { table, base } => {
                let base = self.eval(base)?;
                self.packs.bracket(table)?.apply(base)
            }

            Expr::If {
                cond,
                then,
                otherwise,
            } => {
                if self.cond(cond)? {
                    self.eval(then)?
                } else {
                    self.eval(otherwise)?
                }
            }
        })
    }

    fn fold(
        &mut self,
        of: &[Expr],
        pick: fn(Decimal, Decimal) -> Decimal,
    ) -> Result<Decimal, EngineError> {
        let mut it = of.iter();
        let first = it.next().ok_or(EngineError::EmptyFold)?;
        let mut acc = self.eval(first)?;
        for x in it {
            acc = pick(acc, self.eval(x)?);
        }
        Ok(acc)
    }

    fn cond(&mut self, c: &Cond) -> Result<bool, EngineError> {
        Ok(match c {
            Cond::Gt { left, right } => self.eval(left)? > self.eval(right)?,
            Cond::Gte { left, right } => self.eval(left)? >= self.eval(right)?,
            Cond::Lt { left, right } => self.eval(left)? < self.eval(right)?,
            Cond::Lte { left, right } => self.eval(left)? <= self.eval(right)?,
            Cond::Eq { left, right } => self.eval(left)? == self.eval(right)?,
            Cond::Not { of } => !self.cond(of)?,
            Cond::And { all } => {
                for x in all {
                    if !self.cond(x)? {
                        return Ok(false);
                    }
                }
                true
            }
            Cond::Or { any } => {
                for x in any {
                    if self.cond(x)? {
                        return Ok(true);
                    }
                }
                false
            }
        })
    }
}

/// Compute a return.
pub fn compute(
    forms: &FormSet,
    packs: &PackSet,
    facts: &FactSet,
) -> Result<Assessment, EngineError> {
    Evaluator::new(forms, packs, facts).run()
}
