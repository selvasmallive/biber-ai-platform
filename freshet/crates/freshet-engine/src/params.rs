//! Versioned tax parameter packs.
//!
//! Rates, thresholds and dollar amounts are *data*, never Rust constants. Each
//! tax year and jurisdiction ships as one pack, and every value in a pack must
//! carry a `source` citation. A pack whose values are not all `verified` cannot
//! be used to produce a filed return -- see [`ParamPack::unverified`].
//!
//! This exists because the failure mode that kills tax software is a single
//! stale threshold silently surviving into a new tax year. Making provenance a
//! required field means an unsourced number cannot be added by accident.

use std::collections::BTreeMap;

use rust_decimal::Decimal;
use serde::Deserialize;

use crate::decimal::{de_decimal, de_decimal_opt};
use crate::EngineError;

/// A single scalar parameter, e.g. the basic personal amount.
#[derive(Debug, Clone, Deserialize)]
pub struct Param {
    #[serde(deserialize_with = "de_decimal")]
    pub value: Decimal,
    /// Citation for the value: CRA form/line, guide section, or statute.
    pub source: String,
    /// Set true only after a human has checked the value against `source`.
    #[serde(default)]
    pub verified: bool,
}

/// One band of a progressive rate table.
#[derive(Debug, Clone, Deserialize)]
pub struct Band {
    /// Upper bound of the band. `None` means the band is open-ended (top bracket).
    #[serde(default, deserialize_with = "de_decimal_opt")]
    pub up_to: Option<Decimal>,
    #[serde(deserialize_with = "de_decimal")]
    pub rate: Decimal,
}

/// A progressive rate table, e.g. the federal income tax brackets.
#[derive(Debug, Clone, Deserialize)]
pub struct BracketTable {
    pub bands: Vec<Band>,
    pub source: String,
    #[serde(default)]
    pub verified: bool,
}

impl BracketTable {
    /// Apply the table progressively to `base`, returning tax before credits.
    ///
    /// Bands are applied in order; each band taxes only the portion of `base`
    /// that falls inside it. A negative `base` yields zero.
    pub fn apply(&self, base: Decimal) -> Decimal {
        if base <= Decimal::ZERO {
            return Decimal::ZERO;
        }

        let mut tax = Decimal::ZERO;
        let mut lower = Decimal::ZERO;

        for band in &self.bands {
            let upper = band.up_to.unwrap_or(base);
            let ceiling = if base < upper { base } else { upper };
            let in_band = ceiling - lower;

            if in_band > Decimal::ZERO {
                tax += in_band * band.rate;
            }

            lower = upper;
            if base <= upper {
                break;
            }
        }

        tax
    }
}

/// All parameters for one jurisdiction in one tax year.
#[derive(Debug, Clone, Deserialize)]
pub struct ParamPack {
    /// `"fed"`, `"on"`, `"bc"`, ...
    pub jurisdiction: String,
    pub tax_year: u16,
    #[serde(default)]
    pub scalars: BTreeMap<String, Param>,
    #[serde(default)]
    pub brackets: BTreeMap<String, BracketTable>,
}

impl ParamPack {
    pub fn from_json(s: &str) -> Result<Self, EngineError> {
        serde_json::from_str(s).map_err(|e| EngineError::BadPack(e.to_string()))
    }

    pub fn scalar(&self, key: &str) -> Result<Decimal, EngineError> {
        self.scalars
            .get(key)
            .map(|p| p.value)
            .ok_or_else(|| EngineError::UnknownParam {
                jurisdiction: self.jurisdiction.clone(),
                key: key.to_string(),
            })
    }

    pub fn bracket(&self, key: &str) -> Result<&BracketTable, EngineError> {
        self.brackets
            .get(key)
            .ok_or_else(|| EngineError::UnknownParam {
                jurisdiction: self.jurisdiction.clone(),
                key: key.to_string(),
            })
    }

    /// Keys whose values have not been human-verified against their citation.
    ///
    /// Callers building a *filed* return must treat a non-empty result as fatal.
    pub fn unverified(&self) -> Vec<String> {
        let scalars = self
            .scalars
            .iter()
            .filter(|(_, p)| !p.verified)
            .map(|(k, _)| format!("scalars.{k}"));

        let brackets = self
            .brackets
            .iter()
            .filter(|(_, t)| !t.verified)
            .map(|(k, _)| format!("brackets.{k}"));

        scalars.chain(brackets).collect()
    }
}

impl ParamPack {
    /// Layer one pack over another, the overlay winning on a clash.
    ///
    /// Used so a T2 can draw on the federal parameters a T1 already verified —
    /// capital cost allowance rates are the same statute for both — without a
    /// second copy of them drifting out of step with the first.
    pub fn layered(base: &ParamPack, overlay: &ParamPack) -> ParamPack {
        let mut merged = base.clone();
        merged.tax_year = overlay.tax_year;

        for (key, value) in &overlay.scalars {
            merged.scalars.insert(key.clone(), value.clone());
        }
        for (key, value) in &overlay.brackets {
            merged.brackets.insert(key.clone(), value.clone());
        }

        merged
    }
}

/// The set of packs in play for one return: federal plus one province.
#[derive(Debug, Clone)]
pub struct PackSet {
    pub federal: ParamPack,
    pub provincial: ParamPack,
}

impl PackSet {
    /// Resolve a namespaced key such as `fed:bpa_max` or `on:bpa`.
    pub fn scalar(&self, key: &str) -> Result<Decimal, EngineError> {
        let (pack, rest) = self.split(key)?;
        pack.scalar(rest)
    }

    pub fn bracket(&self, key: &str) -> Result<&BracketTable, EngineError> {
        let (pack, rest) = self.split(key)?;
        pack.bracket(rest)
    }

    /// The pack borrow and the key borrow are independent: the returned table
    /// lives as long as `self`, not as long as the lookup string.
    fn split<'s, 'k>(&'s self, key: &'k str) -> Result<(&'s ParamPack, &'k str), EngineError> {
        let (ns, rest) = key
            .split_once(':')
            .ok_or_else(|| EngineError::UnnamespacedParam(key.to_string()))?;

        match ns {
            "fed" => Ok((&self.federal, rest)),
            other if other == self.provincial.jurisdiction => Ok((&self.provincial, rest)),
            other => Err(EngineError::UnknownJurisdiction(other.to_string())),
        }
    }

    pub fn unverified(&self) -> Vec<String> {
        let fed = self
            .federal
            .unverified()
            .into_iter()
            .map(|k| format!("fed:{k}"));

        let prov = self
            .provincial
            .unverified()
            .into_iter()
            .map(|k| format!("{}:{k}", self.provincial.jurisdiction));

        fed.chain(prov).collect()
    }
}

// -- fiscal periods --------------------------------------------------------

/// Parameter packs for a fiscal period, which may straddle a rate change.
///
/// A T1 resolves parameters from one year's pack. A corporation with a June
/// year-end sits in two, and if a rate moved between them the return is
/// apportioned by the days falling either side. This holds one pack per
/// calendar year the period touches, together with that year's share of it.
#[derive(Debug)]
pub struct PeriodPacks {
    pub period: crate::Period,
    /// One entry per calendar year touched, in order: year, days, packs.
    ///
    /// Days rather than a precomputed weight, deliberately — see [`blended`].
    ///
    /// [`blended`]: PeriodPacks::blended
    years: Vec<(i32, i64, PackSet)>,
}

impl PeriodPacks {
    /// The ordinary case: a period inside a single calendar year.
    pub fn single(period: crate::Period, packs: PackSet) -> Result<Self, EngineError> {
        Self::new(period, vec![(period.start.year, packs)])
    }

    pub fn new(
        period: crate::Period,
        packs_by_year: Vec<(i32, PackSet)>,
    ) -> Result<Self, EngineError> {
        let needed = period.days_by_year();

        if packs_by_year.len() != needed.len() {
            return Err(EngineError::BadPeriod(format!(
                "{period} touches {} calendar year(s) but {} pack(s) were supplied; \
                 a straddling period needs the parameters for every year it covers",
                needed.len(),
                packs_by_year.len()
            )));
        }

        let mut years = Vec::new();
        for ((want_year, days), (got_year, packs)) in needed.into_iter().zip(packs_by_year) {
            if want_year != got_year {
                return Err(EngineError::BadPeriod(format!(
                    "{period} needs the {want_year} parameters, but {got_year} was supplied"
                )));
            }
            years.push((want_year, days, packs));
        }

        Ok(PeriodPacks { period, years })
    }

    /// Whether this period draws on more than one year's parameters.
    pub fn straddles(&self) -> bool {
        self.years.len() > 1
    }

    /// The packs for the year the period ends in.
    ///
    /// Amounts that are *not* apportioned — the ones the Act fixes by
    /// year-end rather than by days — resolve from here.
    pub fn at_year_end(&self) -> &PackSet {
        &self.years.last().expect("a period touches at least one year").2
    }

    /// Every unverified parameter across every year the period touches.
    ///
    /// The union, not one year's. A fiscal period drawing on two years is only
    /// as trustworthy as the worse of them, so a return that straddles an
    /// unverified year must not be filable merely because the other year is
    /// clean.
    pub fn unverified(&self) -> Vec<String> {
        let mut all: Vec<String> = self
            .years
            .iter()
            .flat_map(|(year, _, packs)| {
                packs
                    .unverified()
                    .into_iter()
                    .map(move |k| format!("{year} {k}"))
            })
            .collect();

        all.sort();
        all.dedup();
        all
    }

    /// A parameter apportioned across the period by days.
    ///
    /// Computed as `Σ(days × value) / total_days` — every multiplication
    /// first, one division last, so there is a single rounding step rather
    /// than one per year.
    ///
    /// The obvious alternative, `Σ((days/total) × value)`, rounds each share
    /// before adding. I could not construct a case where the two disagree
    /// under `rust_decimal`, so this ordering is a precaution rather than a fix
    /// for an observed defect — fewer rounding steps, at no cost. Do not read
    /// the choice as evidence that the other ordering is broken.
    pub fn blended(&self, key: &str) -> Result<Decimal, EngineError> {
        let mut weighted = Decimal::ZERO;

        for (_, days, packs) in &self.years {
            weighted += Decimal::from(*days) * packs.scalar(key)?;
        }

        Ok(weighted / Decimal::from(self.period.days()))
    }
}
