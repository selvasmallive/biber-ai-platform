//! Embedded tax-year data.
//!
//! Packs and form definitions are compiled into the binary rather than read
//! from disk. A desktop tax product must produce identical results on every
//! machine, and a user-editable data directory is both a support nightmare and
//! a tampering surface on a return that gets transmitted to CRA.

use freshet_engine::{EngineError, FormSet, PackSet, ParamPack};

pub const FED_2025: &str = include_str!("../data/fed-2025.json");
pub const FED_2026: &str = include_str!("../data/fed-2026.json");

/// The federal T1, shared by every jurisdiction.
///
/// Kept separate from the provincial forms because it is roughly three quarters
/// of the return. Holding a copy per jurisdiction would mean a federal
/// correction had to be made fourteen times identically — and the federal data
/// in this repository has already needed four corrections.
pub const T1_FEDERAL: &str = include_str!("../data/t1-federal.json");

/// One row per jurisdiction: code, form definition, and a pack per tax year.
///
/// A table rather than match arms. With one province the arms were clearer;
/// with fourteen they were three places to forget to edit, and the compiler
/// could not tell you that a jurisdiction had a form but no pack for a year.
///
/// Years are a list rather than named fields. An earlier version had
/// `pack_2025` and `pack_2026`, which made adding a tax year a change to the
/// struct and the macro — structural work for what is only ever new data.
struct Jurisdiction {
    code: &'static str,
    form: &'static str,
    packs: &'static [(u16, &'static str)],
}

/// The pack list for one jurisdiction across every year.
///
/// Split out because `macro_rules!` cannot nest two independent repetitions —
/// expanding thirteen codes against two years in one macro is rejected with
/// "meta-variable `code` repeats 13 times, but `year` repeats 2 times". Passing
/// the year list through as a single token tree puts its repetition inside this
/// macro, where it is the only one.
macro_rules! packs_for {
    ($code:literal, [$($year:literal),+ $(,)?]) => {
        &[$(($year, include_str!(concat!("../data/", $code, "-", $year, ".json")))),+]
    };
}

macro_rules! jurisdictions {
    (years: $years:tt, codes: [$($code:literal),+ $(,)?] $(,)?) => {
        &[$(Jurisdiction {
            code: $code,
            form: include_str!(concat!("../data/t1-", $code, ".json")),
            packs: packs_for!($code, $years),
        }),+]
    };
}

/// Every province and territory, for every tax year with data.
///
/// Quebec is here because a Quebec resident still files a federal T1 — they
/// simply pay no provincial tax through it. Adding a tax year means adding it
/// to `years` and dropping the pack files in; the compiler will name any
/// jurisdiction whose file is missing.
const JURISDICTIONS: &[Jurisdiction] = jurisdictions![
    years: [2025, 2026],
    codes: [
        "ab", "bc", "mb", "nb", "nl", "ns", "nt", "nu", "on", "pe", "qc", "sk", "yt",
    ],
];

fn find(province: &str) -> Option<&'static Jurisdiction> {
    JURISDICTIONS.iter().find(|j| j.code == province)
}

/// Tax years this build can compute — the years it has data for.
///
/// Distinct from [`CERTIFICATION_TARGET_YEAR`], and they currently diverge:
/// the target is 2027, whose amounts have not been published yet, so there is
/// nothing to compute for it.
pub const SUPPORTED_YEARS: &[u16] = &[2025, 2026];

/// The tax year the certification application is for.
///
/// **2027, not 2026.** CRA's application window for the 2026 T1 closed before
/// this product applied, so the first year it can be certified to file is 2027,
/// which is filed in early 2028.
///
/// This is deliberately its own constant rather than "the newest supported
/// year". The two are different things and right now they disagree: 2027 has no
/// parameter pack because its indexed amounts are not published until late
/// 2026. Conflating them would make the product look ready for a year it cannot
/// yet compute a single line of.
pub const CERTIFICATION_TARGET_YEAR: u16 = 2027;

/// Whether the target year's data exists yet.
///
/// False until the 2027 amounts are published and verified. Worth asking rather
/// than assuming: a build that supports the target year is a different thing
/// from one that merely aims at it.
pub fn target_year_is_buildable() -> bool {
    SUPPORTED_YEARS.contains(&CERTIFICATION_TARGET_YEAR)
}

/// Tax years CRA has actually certified this product to **file**.
///
/// Deliberately separate from [`SUPPORTED_YEARS`]. Being able to compute a year
/// is not permission to transmit it: CRA certifies per tax year, and a return
/// must be filed with software certified for that year. A build that can model
/// 2025 while holding only a 2026 certification is fine — one that offers to
/// *file* 2025 on a 2026 certification is not.
///
/// Empty until a certification letter exists. Do not add a year here on the
/// strength of having asked, and note that the first year that could ever
/// appear here is [`CERTIFICATION_TARGET_YEAR`].
pub const CERTIFIED_YEARS: &[u16] = &[];

/// The jurisdictions the certification application covers.
///
/// Ontario only, deliberately. The engine computes all thirteen, but a
/// jurisdiction may only be *filed* once its tax data has been checked against
/// the published form for that year — and only Ontario's has been. Applying for
/// thirteen while nine carry placeholder parameters would be asking CRA to
/// certify arithmetic nobody has verified.
///
/// Widening this is a data problem, not a code one: source the forms, clear the
/// jurisdiction's residual in the verification ledger, then add it here.
pub const CERTIFICATION_SCOPE: &[&str] = &["on"];

/// The jurisdictions CRA has actually certified, as distinct from those applied
/// for. Empty until a confirmation letter exists.
pub const CERTIFIED_PROVINCES: &[&str] = &[];

/// Whether a return for this year and jurisdiction may be transmitted to CRA.
///
/// Both halves must hold. CRA certifies per tax year, and the product declares
/// which jurisdictions it supports — so a 2026 certification covering Ontario
/// says nothing about filing an Alberta return, and the gate must not treat it
/// as though it did.
pub fn is_certified(year: u16, province: &str) -> bool {
    CERTIFIED_YEARS.contains(&year) && CERTIFIED_PROVINCES.contains(&province)
}

/// Whether a jurisdiction is inside the scope being applied for.
///
/// Separate from [`is_certified`] so the app can distinguish "not certified
/// yet" from "never going to be, in this release" — those deserve different
/// wording on screen.
pub fn in_certification_scope(province: &str) -> bool {
    CERTIFICATION_SCOPE.contains(&province)
}

/// Provinces and territories implemented so far.
pub fn supported_provinces() -> Vec<&'static str> {
    JURISDICTIONS.iter().map(|j| j.code).collect()
}

fn unsupported(year: u16, province: &str) -> EngineError {
    EngineError::Unsupported(format!(
        "no tax data for {province}/{year}; this build supports {:?} for {SUPPORTED_YEARS:?}",
        supported_provinces()
    ))
}

/// Federal + provincial parameter packs for a return.
pub fn packs(year: u16, province: &str) -> Result<PackSet, EngineError> {
    let j = find(province).ok_or_else(|| unsupported(year, province))?;

    let fed = match year {
        2025 => FED_2025,
        2026 => FED_2026,
        _ => return Err(unsupported(year, province)),
    };

    let prov = j
        .packs
        .iter()
        .find(|(y, _)| *y == year)
        .map(|(_, pack)| *pack)
        .ok_or_else(|| unsupported(year, province))?;

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
    if !SUPPORTED_YEARS.contains(&year) {
        return Err(unsupported(year, province));
    }
    let j = find(province).ok_or_else(|| unsupported(year, province))?;

    let mut forms = FormSet::compose(
        FormSet::from_json(T1_FEDERAL)?,
        FormSet::from_json(j.form)?,
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
            for prov in supported_provinces() {
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
        let ontario = FormSet::from_json(find("on").unwrap().form).unwrap();

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
        let mut rogue = FormSet::from_json(find("on").unwrap().form).unwrap();

        let stolen = federal.lines[0].clone();
        let stolen_id = stolen.id.clone();
        rogue.lines.push(stolen);

        match FormSet::compose(federal, rogue) {
            Err(EngineError::DuplicateLine(id)) => assert_eq!(id, stolen_id),
            other => panic!("a province overrode {stolen_id}: {other:?}"),
        }
    }

    /// The target year and the years with data are different things, and right
    /// now they disagree. This test exists so that stays visible: when 2027
    /// data lands it will fail, which is the prompt to check that the year is
    /// genuinely complete rather than merely present.
    #[test]
    fn the_certification_target_is_2027_and_has_no_data_yet() {
        assert_eq!(CERTIFICATION_TARGET_YEAR, 2027);
        assert!(
            !target_year_is_buildable(),
            "2027 data has appeared — verify it, then update this test"
        );

        // And nothing is certified for it, or for anything else.
        assert!(!is_certified(CERTIFICATION_TARGET_YEAR, "on"));
    }

    #[test]
    fn unsupported_combinations_are_rejected() {
        assert!(packs(2024, "on").is_err(), "an uncomputable year was accepted");
        assert!(t1_forms(2024, "on").is_err());
        // Not a jurisdiction. Every real one is now implemented.
        assert!(t1_forms(2025, "zz").is_err());
        assert!(packs(2025, "zz").is_err());
    }
}
