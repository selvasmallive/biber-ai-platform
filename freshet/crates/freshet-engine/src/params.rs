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
    #[serde(default)]
    pub kind: ParamKind,
}

/// Whether a figure comes from the law or from us.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ParamKind {
    /// Fixed by the Act, a regulation or a CRA publication. Has a source, and
    /// must be checked against it before anything is filed.
    #[default]
    Tax,

    /// A threshold Freshet chose, affecting only what the software says to the
    /// user — when to raise a review note, when a figure looks worth querying.
    ///
    /// Deliberately outside [`ParamPack::unverified`]. There is no publication
    /// to check it against, so a `verified` flag on one would be either a
    /// falsehood or a permanent block on filing, and the presence of such a
    /// flag in this namespace weakens every other flag in it. A review
    /// threshold being wrong produces a note nobody needed; a tax parameter
    /// being wrong produces a wrong return. They are not the same risk and
    /// should not share a gate.
    Review,
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
            // Review thresholds are excluded by kind, not by having been
            // marked verified. See [`ParamKind::Review`].
            .filter(|(_, p)| p.kind == ParamKind::Tax && !p.verified)
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
    /// The period cut into stretches over which every parameter holds still,
    /// in order.
    ///
    /// Usually one per calendar year, because that is where parameters
    /// normally change. Not always: Ontario's lower corporate rate falls from
    /// 3.2% to 2.2% on 1 July 2026, so a corporation with an October year end
    /// has three segments in play, two of them inside one calendar year.
    ///
    /// Days rather than a precomputed weight, deliberately — see [`blended`].
    ///
    /// [`blended`]: PeriodPacks::blended
    segments: Vec<Segment>,
}

/// One stretch of a fiscal period over which the parameters do not move.
#[derive(Debug, Clone)]
struct Segment {
    /// How this stretch is named when reporting an unverified parameter.
    ///
    /// A year on its own where a year is all there is, so the common case
    /// reads as it always did; something like `2026 from 07-01` when a year
    /// had to be cut.
    label: String,
    days: i64,
    packs: PackSet,
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

        let mut segments = Vec::new();
        for ((want_year, days), (got_year, packs)) in needed.into_iter().zip(packs_by_year) {
            if want_year != got_year {
                return Err(EngineError::BadPeriod(format!(
                    "{period} needs the {want_year} parameters, but {got_year} was supplied"
                )));
            }
            segments.push(Segment {
                label: want_year.to_string(),
                days,
                packs,
            });
        }

        Ok(PeriodPacks { period, segments })
    }

    /// Segments given explicitly, for a parameter that changes part-way
    /// through a calendar year.
    ///
    /// Each entry is a label, the stretch it covers, and the packs in force
    /// over it. They must be in order, must not overlap or leave a gap, and
    /// together must cover the period exactly.
    ///
    /// That validation is the whole value of this constructor. A gap or an
    /// overlap does not fail loudly — it produces a weighted average over the
    /// wrong denominator, which is a plausible-looking rate and therefore a
    /// plausible-looking return. It is checked here so it cannot be got wrong
    /// by a caller assembling the segments.
    pub fn segmented(
        period: crate::Period,
        segments: Vec<(String, crate::Period, PackSet)>,
    ) -> Result<Self, EngineError> {
        if segments.is_empty() {
            return Err(EngineError::BadPeriod(format!(
                "{period} was given no parameter segments"
            )));
        }

        let mut expected = period.start;
        let mut built = Vec::new();

        for (label, stretch, packs) in segments {
            if stretch.start != expected {
                return Err(EngineError::BadPeriod(format!(
                    "parameter segments for {period} are not contiguous: \
                     expected one beginning {expected}, got {stretch}"
                )));
            }

            if stretch.end > period.end {
                return Err(EngineError::BadPeriod(format!(
                    "parameter segment {stretch} runs past the end of {period}"
                )));
            }

            built.push(Segment {
                label,
                days: stretch.days(),
                packs,
            });

            expected = crate::Date::from_days(stretch.end.to_days() + 1);
        }

        let covered: i64 = built.iter().map(|s| s.days).sum();
        if covered != period.days() {
            return Err(EngineError::BadPeriod(format!(
                "parameter segments for {period} cover {covered} of its {} days",
                period.days()
            )));
        }

        Ok(PeriodPacks { period, segments: built })
    }

    /// How many stretches the period was cut into.
    ///
    /// One when nothing changes across it. More when it crosses a calendar
    /// year, *or* a date on which a rate moves part-way through one.
    pub fn segment_count(&self) -> usize {
        self.segments.len()
    }

    /// Whether this period draws on more than one set of parameters.
    pub fn straddles(&self) -> bool {
        self.segments.len() > 1
    }

    /// The packs for the year the period ends in.
    ///
    /// Amounts that are *not* apportioned — the ones the Act fixes by
    /// year-end rather than by days — resolve from here.
    pub fn at_year_end(&self) -> &PackSet {
        &self
            .segments
            .last()
            .expect("a period has at least one segment")
            .packs
    }

    /// Every unverified parameter across every year the period touches.
    ///
    /// The union, not one year's. A fiscal period drawing on two years is only
    /// as trustworthy as the worse of them, so a return that straddles an
    /// unverified year must not be filable merely because the other year is
    /// clean.
    pub fn unverified(&self) -> Vec<String> {
        let mut all: Vec<String> = self
            .segments
            .iter()
            .flat_map(|segment| {
                let label = segment.label.clone();
                segment
                    .packs
                    .unverified()
                    .into_iter()
                    .map(move |k| format!("{label} {k}"))
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

        for segment in &self.segments {
            weighted += Decimal::from(segment.days) * segment.packs.scalar(key)?;
        }

        Ok(weighted / Decimal::from(self.period.days()))
    }
}
