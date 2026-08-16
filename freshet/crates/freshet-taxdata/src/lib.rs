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
pub const AB_2025: &str = include_str!("../data/ab-2025.json");
pub const AB_2026: &str = include_str!("../data/ab-2026.json");

/// The federal T1, shared by every province.
///
/// Kept separate from the provincial forms because it is roughly three quarters
/// of the return. Holding a copy per jurisdiction would mean a federal
/// correction had to be made thirteen times identically — and the federal data
/// in this repository has already needed four corrections.
pub const T1_FEDERAL: &str = include_str!("../data/t1-federal.json");

/// One form definition serves every year whose *structure* is unchanged; only
/// the parameter pack differs. This is the payoff from keeping the tax rules as
/// data — a new year is a pack, not a fork. It splits into per-year files the
/// first time a line is added or removed.
pub const T1_ON: &str = include_str!("../data/t1-on.json");

/// Alberta. Eighteen lines to Ontario's thirty: no surtax, no health premium,
/// no low-income reduction, no CARE credit, and no tuition credit — Alberta
/// abolished that one in 2020, as Ontario did in 2017.
pub const T1_AB: &str = include_str!("../data/t1-ab.json");

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
pub const SUPPORTED_PROVINCES: &[&str] = &["ab", "on"];

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
        (2025, "ab") => (FED_2025, AB_2025),
        (2026, "ab") => (FED_2026, AB_2026),
        _ => return Err(unsupported(year, province)),
    };

    Ok(PackSet {
        federal: ParamPack::from_json(fed)?,
        provincial: ParamPack::from_json(prov)?,
    })
}

/// T1 form definitions for a return: the federal form with one province
/// composed into it.
///
/// The engine resolves lines as a DAG keyed by id, so composition is a
/// concatenation — provincial lines reference `fed.*` ids and are resolved in
/// dependency order regardless of which file they arrived in.
pub fn t1_forms(year: u16, province: &str) -> Result<FormSet, EngineError> {
    let provincial = match (year, province) {
        (2025 | 2026, "on") => T1_ON,
        (2025 | 2026, "ab") => T1_AB,
        _ => return Err(unsupported(year, province)),
    };

    let mut forms = FormSet::compose(
        FormSet::from_json(T1_FEDERAL)?,
        FormSet::from_json(provincial)?,
    )?;

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

    /// The federal return is stored once. If a future province were to be
    /// pasted in whole rather than written as a provincial supplement, this is
    /// what would catch it.
    #[test]
    fn the_federal_form_is_not_duplicated_per_province() {
        let federal = FormSet::from_json(T1_FEDERAL).unwrap();
        let ontario = FormSet::from_json(T1_ON).unwrap();

        // A provincial form owns its own namespace plus the two `prov.*` lines
        // that are its contract with the federal return.
        assert!(
            ontario
                .lines
                .iter()
                .all(|l| l.id.starts_with("on.") || l.id.starts_with("prov.")),
            "a provincial form defined a line outside its namespace"
        );
        assert!(
            federal.lines.iter().any(|l| l.id.starts_with("fed.")),
            "the federal form lost its federal lines"
        );

        // Composing them is what the loader does, and the result is the whole
        // return.
        let composed = t1_forms(2026, "on").unwrap();
        assert_eq!(composed.lines.len(), federal.lines.len() + ontario.lines.len());
    }

    /// A province that redefines a federal line must be rejected, not silently
    /// allowed to shadow it. With one province this is theoretical; with
    /// thirteen it is the mistake someone will actually make.
    #[test]
    fn a_province_cannot_override_a_federal_line() {
        let federal = FormSet::from_json(T1_FEDERAL).unwrap();
        let mut rogue = FormSet::from_json(T1_ON).unwrap();

        let stolen = federal.lines[0].clone();
        let stolen_id = stolen.id.clone();
        rogue.lines.push(stolen);

        match FormSet::compose(federal, rogue) {
            Err(EngineError::DuplicateLine(id)) => assert_eq!(id, stolen_id),
            other => panic!("a province overrode {stolen_id}: {other:?}"),
        }
    }

    #[test]
    fn unsupported_combinations_are_rejected() {
        assert!(packs(2024, "on").is_err());
        assert!(t1_forms(2025, "bc").is_err());
    }
}
