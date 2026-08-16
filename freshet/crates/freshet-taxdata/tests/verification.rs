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
        "scalars.age_amount_clawback_rate",
        "scalars.cca_first_year_adjustment",
        "scalars.cca_rate_class10",
        "scalars.cca_rate_class10_1",
        "scalars.cca_rate_class12",
        "scalars.cca_rate_class50",
        "scalars.cca_rate_class8",
        "scalars.childcare_earned_income_den",
        "scalars.childcare_earned_income_num",
        "scalars.childcare_limit_7_to_16",
        "scalars.childcare_limit_disabled",
        "scalars.childcare_limit_under_7",
        "scalars.cpp2_max_contribution",
        "scalars.cpp_basic_exemption",
        "scalars.cpp_max_contribution",
        "scalars.cpp_rate_base",
        "scalars.cpp_rate_enhanced",
        "scalars.cpp_rate_total",
        "scalars.cpp_self_employed_multiple",
        "scalars.cpp_ympe",
        "scalars.credit_rate",
        "scalars.cwb_minimum_age",
        "scalars.cwb_rate",
        "scalars.cwb_reduction_rate",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.ei_max_premium",
        "scalars.ei_min_insurable",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.pension_split_max_rate",
        "scalars.rrsp_annual_limit",
        "scalars.rrsp_rate",
        "scalars.tuition_transfer_max",
        "scalars.vehicle_cost_limit",
    ];
    assert_residual(2025, "fed", &expected);
}

#[test]
fn fed_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.age_amount_clawback_rate",
        "scalars.cca_first_year_adjustment",
        "scalars.cca_rate_class10",
        "scalars.cca_rate_class10_1",
        "scalars.cca_rate_class12",
        "scalars.cca_rate_class50",
        "scalars.cca_rate_class8",
        "scalars.childcare_earned_income_den",
        "scalars.childcare_earned_income_num",
        "scalars.childcare_limit_7_to_16",
        "scalars.childcare_limit_disabled",
        "scalars.childcare_limit_under_7",
        "scalars.cpp_rate_base",
        "scalars.cpp_rate_enhanced",
        "scalars.cpp_self_employed_multiple",
        "scalars.credit_rate",
        "scalars.cwb_minimum_age",
        "scalars.cwb_rate",
        "scalars.cwb_reduction_rate",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.ei_min_insurable",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.pension_split_max_rate",
        "scalars.rrsp_annual_limit",
        "scalars.rrsp_rate",
        "scalars.tuition_transfer_max",
        "scalars.vehicle_cost_limit",
    ];
    assert_residual(2026, "fed", &expected);
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
        // Ontario tax reduction amounts: verified for 2025, estimated for 2026
        // until Ontario publishes.
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
