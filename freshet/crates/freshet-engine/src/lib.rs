//! Freshet tax calculation engine.
//!
//! The engine is a pure function of (form definitions, parameter pack, facts).
//! It performs no I/O, holds no taxpayer identity, and is deterministic in
//! exact decimal arithmetic -- which is what makes it testable against CRA
//! certification vectors and reviewable by a tax professional who does not read
//! Rust.
//!
//! ```no_run
//! use freshet_engine::{compute, FactSet, FormSet, PackSet, ParamPack};
//! # fn main() -> Result<(), freshet_engine::EngineError> {
//! # let (forms_json, fed_json, on_json) = ("", "", "");
//! let forms = FormSet::from_json(forms_json)?;
//! let packs = PackSet {
//!     federal: ParamPack::from_json(fed_json)?,
//!     provincial: ParamPack::from_json(on_json)?,
//! };
//! let mut facts = FactSet::new();
//! facts.set("t4.employment_income", rust_decimal::Decimal::from(85_000));
//!
//! let assessment = compute(&forms, &packs, &facts)?;
//! assert!(assessment.is_filable());
//! # Ok(())
//! # }
//! ```

pub mod decimal;
pub mod eval;
pub mod expr;
pub mod facts;
pub mod form;
pub mod params;
pub mod period;

pub use eval::{compute, compute_for_period, Assessment, AuditEntry, Diagnostic, Evaluator};
pub use expr::{Cond, Expr};
pub use facts::FactSet;
pub use form::{CheckDef, FormSet, LineDef, Rounding, Severity};
pub use period::{Date, Period};
pub use params::{Band, BracketTable, PackSet, Param, ParamPack};

pub use rust_decimal::Decimal;

#[derive(Debug, thiserror::Error)]
pub enum EngineError {
    #[error("malformed parameter pack: {0}")]
    BadPack(String),

    #[error("malformed form definition: {0}")]
    BadForm(String),

    #[error("form defines line {0} more than once")]
    DuplicateLine(String),

    #[error("no such line: {0}")]
    UnknownLine(String),

    #[error("{0}")]
    BadPeriod(String),

    #[error("no such parameter {key} in jurisdiction {jurisdiction}")]
    UnknownParam { jurisdiction: String, key: String },

    #[error("parameter key {0} is missing a jurisdiction prefix (expected e.g. `fed:bpa_max`)")]
    UnnamespacedParam(String),

    #[error("no parameter pack loaded for jurisdiction {0}")]
    UnknownJurisdiction(String),

    #[error("circular line reference: {0}")]
    CircularReference(String),

    #[error("division by zero")]
    DivideByZero,

    #[error("min/max applied to an empty list")]
    EmptyFold,

    #[error("unsupported: {0}")]
    Unsupported(String),
}
