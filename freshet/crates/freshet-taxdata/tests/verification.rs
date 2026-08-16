//! The verification ledger.
//!
//! Every parameter starts unverified and may only be marked verified once it
//! has been checked against a primary source named in its citation. These tests
//! pin the exact set that is *still* unverified, per pack.
//!
//! The point is that the residual cannot grow silently. Adding a parameter
//! without verifying it fails here, which forces the omission to be a conscious
//! entry on this list rather than something that slips into a filed return.
//!
//! When a value is verified, delete its line. When one is added unverified, add
//! its line and know that you have.

/// `jurisdiction` selects which pack to inspect; the pair is always loaded as a
/// province, because that is how a return is assembled.
fn assert_residual(year: u16, jurisdiction: &str, expected: &[&str]) {
    let packs = freshet_taxdata::packs(year, "on").unwrap();
    let pack = if jurisdiction == "fed" {
        &packs.federal
    } else {
        &packs.provincial
    };

    let mut actual = pack.unverified();
    actual.sort();
    let mut want: Vec<String> = expected.iter().map(|s| s.to_string()).collect();
    want.sort();

    let newly_unverified: Vec<_> = actual.iter().filter(|k| !want.contains(k)).collect();
    let newly_verified: Vec<_> = want.iter().filter(|k| !actual.contains(k)).collect();

    assert!(
        newly_unverified.is_empty(),
        "unverified parameters were added without being recorded: {newly_unverified:?}"
    );
    assert!(
        newly_verified.is_empty(),
        "these are now verified — delete them from the expected list: {newly_verified:?}"
    );
}

#[test]
fn fed_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.cpp2_max_contribution",
        "scalars.cpp_basic_exemption",
        "scalars.cpp_max_contribution",
        "scalars.cpp_rate_total",
        "scalars.cpp_ympe",
        "scalars.ei_max_premium",
    ];

    assert_residual(2025, "fed", &expected);
}

#[test]
fn fed_2026_residual_is_exactly_this() {
    // Nothing left. Every federal parameter for the certification
    // target year has been checked against a primary source.
    assert_residual(2026, "fed", &[]);
}

#[test]
fn on_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.care_rate_base_tier1",
        "scalars.care_rate_base_tier2",
        "scalars.care_rate_base_tier3",
        "scalars.care_rate_base_tier4",
        "scalars.care_step_reduction",
        "scalars.care_tier1_ceiling",
        "scalars.care_tier2_ceiling",
        "scalars.care_tier2_step",
        "scalars.care_tier3_ceiling",
        "scalars.care_tier3_step",
        "scalars.care_tier4_ceiling",
        "scalars.care_tier4_step",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "on", &expected);
}

#[test]
fn on_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.care_rate_base_tier1",
        "scalars.care_rate_base_tier2",
        "scalars.care_rate_base_tier3",
        "scalars.care_rate_base_tier4",
        "scalars.care_step_reduction",
        "scalars.care_tier1_ceiling",
        "scalars.care_tier2_ceiling",
        "scalars.care_tier2_step",
        "scalars.care_tier3_ceiling",
        "scalars.care_tier3_step",
        "scalars.care_tier4_ceiling",
        "scalars.care_tier4_step",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.disability_amount",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.surtax_threshold_1",
        "scalars.surtax_threshold_2",
        "scalars.tax_reduction_basic",
        "scalars.tax_reduction_per_dependant",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "on", &expected);
}

/// A blunt progress marker. Neither pack can be filed until this reaches zero,
/// and seeing the number move is the point of doing the pass incrementally.
#[test]
fn report_verification_progress() {
    for (year, label) in [(2025u16, "2025"), (2026, "2026")] {
        let packs = freshet_taxdata::packs(year, "on").unwrap();
        let fed = packs.federal.unverified().len();
        let on = packs.provincial.unverified().len();
        println!("{label}: {fed} federal and {on} Ontario parameters still unverified");
    }
}
