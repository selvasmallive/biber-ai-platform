//! The expression language that tax forms are written in.
//!
//! A form definition is data, not code: each line carries an `Expr` tree that is
//! deserialized from JSON. Keeping the form logic out of Rust means a new tax
//! year is a data change reviewable by a tax professional, and it lets the
//! evaluator record a complete audit trail for free.

use rust_decimal::Decimal;
use serde::Deserialize;

use crate::decimal::de_decimal;

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Expr {
    /// A literal. Prefer `param` so the value carries a citation.
    Const {
        #[serde(deserialize_with = "de_decimal")]
        value: Decimal,
    },

    /// A value entered by the taxpayer or imported from a slip.
    Fact { key: String },

    /// Another line on this return, e.g. `fed.23600`.
    Line { id: String },

    /// A namespaced parameter, e.g. `fed:bpa_max`.
    Param { key: String },

    /// A parameter apportioned across the reporting period by days.
    ///
    /// For a corporation whose fiscal year straddles a rate change, the tax is
    /// split by the days falling either side. Marked in the form rather than
    /// applied to every parameter, because the Act fixes some amounts at
    /// year-end and blending those would be wrong — which of the two a given
    /// parameter is, is a tax question, so it belongs in the form where it can
    /// be read against the legislation.
    ///
    /// Identical to [`Expr::Param`] when the period sits inside one calendar
    /// year, which is every T1.
    BlendedParam { key: String },

    Sum { of: Vec<Expr> },
    Sub { from: Box<Expr>, minus: Box<Expr> },
    Mul { of: Box<Expr>, by: Box<Expr> },

    /// Division guarded against a zero denominator.
    Div { of: Box<Expr>, by: Box<Expr> },

    Min { of: Vec<Expr> },
    Max { of: Vec<Expr> },

    /// "If negative, enter 0" -- the most common instruction on any tax form.
    FloorZero { of: Box<Expr> },

    Clamp {
        value: Box<Expr>,
        lo: Box<Expr>,
        hi: Box<Expr>,
    },

    Round {
        of: Box<Expr>,
        #[serde(default = "two")]
        dp: u32,
    },

    /// Round up to a whole number. Tax rules that say "for each $2,500 **or
    /// portion**" are step functions, and linear interpolation gets them wrong
    /// at every boundary.
    Ceil { of: Box<Expr> },

    /// Round down to a whole number.
    Floor { of: Box<Expr> },

    /// Apply a progressive rate table, e.g. `fed:income_tax`.
    Bracket { table: String, base: Box<Expr> },

    If {
        cond: Box<Cond>,
        then: Box<Expr>,
        #[serde(rename = "else")]
        otherwise: Box<Expr>,
    },
}

fn two() -> u32 {
    2
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "cmp", rename_all = "snake_case")]
pub enum Cond {
    Gt { left: Expr, right: Expr },
    Gte { left: Expr, right: Expr },
    Lt { left: Expr, right: Expr },
    Lte { left: Expr, right: Expr },
    Eq { left: Expr, right: Expr },
    And { all: Vec<Cond> },
    Or { any: Vec<Cond> },
    Not { of: Box<Cond> },
}
