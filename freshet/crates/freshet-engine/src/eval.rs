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
use crate::params::PeriodPacks;
use crate::period::Period;
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

/// Where parameters come from.
///
/// A T1 draws on one year. A corporation whose fiscal period straddles a
/// calendar boundary draws on two, and a rate that moved between them is
/// apportioned by days.
pub enum Parameters<'a> {
    Single(&'a PackSet),
    OverPeriod(&'a PeriodPacks),
}

impl Parameters<'_> {
    fn packs(&self) -> &PackSet {
        match self {
            // Amounts the Act fixes at year-end resolve from the closing year,
            // which is also the only year a single-pack return has.
            Parameters::Single(p) => p,
            Parameters::OverPeriod(p) => p.at_year_end(),
        }
    }

    fn unverified(&self) -> Vec<String> {
        match self {
            Parameters::Single(p) => p.unverified(),
            Parameters::OverPeriod(p) => p.unverified(),
        }
    }

    fn blended(&self, key: &str) -> Result<Decimal, EngineError> {
        match self {
            Parameters::Single(p) => p.scalar(key),
            Parameters::OverPeriod(p) => p.blended(key),
        }
    }
}

pub struct Evaluator<'a> {
    forms: &'a FormSet,
    packs: Parameters<'a>,
    facts: &'a FactSet,
    memo: HashMap<String, Decimal>,
    stack: Vec<String>,
    audit: Vec<AuditEntry>,
}

impl<'a> Evaluator<'a> {
    pub fn new(forms: &'a FormSet, packs: &'a PackSet, facts: &'a FactSet) -> Self {
        Self::over(forms, Parameters::Single(packs), facts)
    }

    pub fn over(forms: &'a FormSet, packs: Parameters<'a>, facts: &'a FactSet) -> Self {
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
            Expr::Param { key } => self.packs.packs().scalar(key)?,
            Expr::BlendedParam { key } => self.packs.blended(key)?,

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
                self.packs.packs().bracket(table)?.apply(base)
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
/// The fact namespace the engine fills in from the reporting period.
///
/// Reserved: a caller supplying one of these would silently override the real
/// period, so it is refused rather than merged.
pub const PERIOD_FACT_PREFIX: &str = "period.";

/// Facts derived from the reporting period.
///
/// Supplied as facts rather than as new expression operators so that proration
/// stays visible in the form definition. A T2 line that reduces the business
/// limit for a short year reads as `limit × period.days ÷ 365` — arithmetic
/// anyone can check against the Act, with the 365 written where the Act puts
/// it rather than buried in the engine.
///
/// The two year counts are positional, not named by year. `second_year` is nil
/// for a period inside one calendar year, so a blend written as
/// `(first × rate_a + second × rate_b) ÷ days` gives `rate_a` unchanged when
/// there is nothing to blend, and needs no special case in the form.
fn period_facts(period: &Period) -> Vec<(&'static str, Decimal)> {
    let split = period.days_by_year();

    let (first_year, first_days) = split[0];
    let (second_year, second_days) = split.get(1).copied().unwrap_or((first_year, 0));

    vec![
        ("period.days", Decimal::from(period.days())),
        ("period.is_short", bit(period.is_short())),
        ("period.straddles", bit(period.straddles())),
        ("period.first_year", Decimal::from(first_year)),
        ("period.second_year", Decimal::from(second_year)),
        ("period.days_in_first_year", Decimal::from(first_days)),
        ("period.days_in_second_year", Decimal::from(second_days)),
    ]
}

fn bit(yes: bool) -> Decimal {
    if yes {
        Decimal::ONE
    } else {
        Decimal::ZERO
    }
}

/// Compute a return for an explicit reporting period.
///
/// A T1 is filed for a calendar year and a T2 for a fiscal period, but a
/// calendar year *is* a period, so both go through here. [`compute`] is the T1
/// case with the period implied by the form's tax year.
pub fn compute_for_period(
    forms: &FormSet,
    packs: &PackSet,
    facts: &FactSet,
    period: Period,
) -> Result<Assessment, EngineError> {
    // A period crossing a calendar boundary may sit either side of a rate
    // change, and one year's parameters cannot express that. Refusing is the
    // point: the alternative is silently applying the closing year's rate to
    // the whole period, which is wrong by however much the rate moved.
    if period.straddles() {
        return Err(EngineError::BadPeriod(format!(
            "{period} crosses a calendar year, so one year of parameters              cannot express a rate change inside it. Use compute_across with              both years."
        )));
    }

    compute_over_period(forms, Parameters::Single(packs), facts, period)
}

/// Compute a return whose parameters may span two calendar years.
///
/// The entry point for a corporation with an off-calendar year-end. A rate that
/// moved between the years is apportioned by days wherever the form asks for a
/// blended parameter.
pub fn compute_across(
    forms: &FormSet,
    packs: &PeriodPacks,
    facts: &FactSet,
) -> Result<Assessment, EngineError> {
    compute_over_period(forms, Parameters::OverPeriod(packs), facts, packs.period)
}

fn compute_over_period(
    forms: &FormSet,
    packs: Parameters<'_>,
    facts: &FactSet,
    period: Period,
) -> Result<Assessment, EngineError> {
    if let Some(key) = facts
        .iter()
        .map(|(k, _)| k)
        .find(|k| k.starts_with(PERIOD_FACT_PREFIX))
    {
        return Err(EngineError::BadPeriod(format!(
            "`{key}` is derived from the reporting period, not entered. A caller              setting it would override the real period without anything saying so."
        )));
    }

    let mut derived = facts.clone();
    for (key, value) in period_facts(&period) {
        derived.set(key, value);
    }

    Evaluator::over(forms, packs, &derived).run()
}

/// Compute a return for a calendar tax year.
pub fn compute(
    forms: &FormSet,
    packs: &PackSet,
    facts: &FactSet,
) -> Result<Assessment, EngineError> {
    compute_for_period(forms, packs, facts, Period::calendar(forms.tax_year as i32))
}
