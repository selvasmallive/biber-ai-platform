//! Taxpayer-supplied inputs.
//!
//! Facts are the leaves of the calculation: box amounts off a T4, an RRSP
//! receipt, a self-reported figure. They are deliberately a flat keyed map so
//! that the interview UI, slip importers and test vectors all produce the same
//! shape.

use std::collections::BTreeMap;

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct FactSet {
    #[serde(flatten)]
    values: BTreeMap<String, Decimal>,
}

impl FactSet {
    pub fn new() -> Self {
        Self::default()
    }

    /// Facts default to zero. A tax form treats an unanswered money question as
    /// nil, and forcing every unused line to be entered explicitly would make
    /// both the UI and the test vectors unusable.
    pub fn get(&self, key: &str) -> Decimal {
        self.values.get(key).copied().unwrap_or(Decimal::ZERO)
    }

    pub fn is_set(&self, key: &str) -> bool {
        self.values.contains_key(key)
    }

    pub fn set(&mut self, key: impl Into<String>, value: Decimal) -> &mut Self {
        self.values.insert(key.into(), value);
        self
    }

    pub fn iter(&self) -> impl Iterator<Item = (&String, &Decimal)> {
        self.values.iter()
    }
}

impl<K: Into<String>> FromIterator<(K, Decimal)> for FactSet {
    fn from_iter<T: IntoIterator<Item = (K, Decimal)>>(iter: T) -> Self {
        Self {
            values: iter.into_iter().map(|(k, v)| (k.into(), v)).collect(),
        }
    }
}
