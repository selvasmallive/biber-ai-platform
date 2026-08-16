//! Embedded tax-year data.
//!
//! Packs and form definitions are compiled into the binary rather than read
//! from disk. A desktop tax product must produce identical results on every
//! machine, and a user-editable data directory is both a support nightmare and
//! a tampering surface on a return that gets transmitted to CRA.

use freshet_engine::{EngineError, FormSet, PackSet, ParamPack};

pub const FED_2025: &str = include_str!("../data/fed-2025.json");
pub const ON_2025: &str = include_str!("../data/on-2025.json");
pub const FED_2026: &str = include_str!("../data/fed-2026.json");
pub const ON_2026: &str = include_str!("../data/on-2026.json");

/// One form definition serves every year whose *structure* is unchanged; only
/// the parameter pack differs. This is the payoff from keeping the tax rules as
/// data — a new year is a pack, not a fork. It splits into per-year files the
/// first time a line is added or removed.
pub const T1_ON: &str = include_str!("../data/t1-on.json");

/// Tax years this build can compute. CRA certifies per tax year, so this list
/// is also the list of years the product may claim support for.
///
/// 2026 is the certification target: test returns arrive from CRA in the
/// November before the filing season. 2025 is kept because prior-year filing is
/// a real feature and because it is the year with the better-sourced data.
pub const SUPPORTED_YEARS: &[u16] = &[2025, 2026];

/// Tax years CRA has actually certified this product to **file**.
///
/// Deliberately separate from [`SUPPORTED_YEARS`]. Being able to compute a year
/// is not permission to transmit it: CRA certifies per tax year, and a return
/// must be filed with software certified for that year. A build that can model
/// 2025 while holding only a 2026 certification is fine — one that offers to
/// *file* 2025 on a 2026 certification is not.
///
/// Empty until a certification letter exists. Do not add a year here on the
/// strength of having asked.
pub const CERTIFIED_YEARS: &[u16] = &[];

/// Whether a return for this year may be transmitted to CRA.
pub fn is_certified(year: u16) -> bool {
    CERTIFIED_YEARS.contains(&year)
}

/// Provinces implemented so far.
pub const SUPPORTED_PROVINCES: &[&str] = &["on"];

fn unsupported(year: u16, province: &str) -> EngineError {
    EngineError::Unsupported(format!(
        "no tax data for {province}/{year}; this build supports {SUPPORTED_PROVINCES:?} for {SUPPORTED_YEARS:?}"
    ))
}

/// Federal + provincial parameter packs for a return.
pub fn packs(year: u16, province: &str) -> Result<PackSet, EngineError> {
    let (fed, prov) = match (year, province) {
        (2025, "on") => (FED_2025, ON_2025),
        (2026, "on") => (FED_2026, ON_2026),
        _ => return Err(unsupported(year, province)),
    };

    Ok(PackSet {
        federal: ParamPack::from_json(fed)?,
        provincial: ParamPack::from_json(prov)?,
    })
}

/// T1 form definitions for a return.
pub fn t1_forms(year: u16, province: &str) -> Result<FormSet, EngineError> {
    let src = match (year, province) {
        (2025 | 2026, "on") => T1_ON,
        _ => return Err(unsupported(year, province)),
    };

    let mut forms = FormSet::from_json(src)?;
    forms.tax_year = year;
    Ok(forms)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_shipped_pack_parses() {
        for &year in SUPPORTED_YEARS {
            for &prov in SUPPORTED_PROVINCES {
                packs(year, prov).expect("pack parses");
                t1_forms(year, prov).expect("forms parse");
            }
        }
    }

    #[test]
    fn unsupported_combinations_are_rejected() {
        assert!(packs(2024, "on").is_err());
        assert!(t1_forms(2025, "bc").is_err());
    }
}
