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
    let packs = freshet_taxdata::packs(year, if jurisdiction == "fed" { "on" } else { jurisdiction }).unwrap();
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
    // Nothing left: every parameter checked against a primary source.
    assert_residual(2025, "fed", &[]);
}

#[test]
fn fed_2026_residual_is_exactly_this() {
    // Nothing left: every parameter checked against a primary source.
    assert_residual(2026, "fed", &[]);
}

#[test]
fn ab_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.supplemental_rate",
        "scalars.supplemental_threshold",
    ];

    assert_residual(2025, "ab", &expected);
}

#[test]
fn ab_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.supplemental_rate",
        "scalars.supplemental_threshold",
    ];

    assert_residual(2026, "ab", &expected);
}

#[test]
fn bc_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tax_reduction_base",
        "scalars.tax_reduction_rate",
        "scalars.tax_reduction_threshold",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "bc", &expected);
}

#[test]
fn bc_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tax_reduction_base",
        "scalars.tax_reduction_rate",
        "scalars.tax_reduction_threshold",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "bc", &expected);
}

#[test]
fn mb_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "mb", &expected);
}

#[test]
fn mb_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "mb", &expected);
}

#[test]
fn nb_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "nb", &expected);
}

#[test]
fn nb_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "nb", &expected);
}

#[test]
fn nl_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "nl", &expected);
}

#[test]
fn nl_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "nl", &expected);
}

#[test]
fn ns_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "ns", &expected);
}

#[test]
fn ns_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "ns", &expected);
}

#[test]
fn nt_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "nt", &expected);
}

#[test]
fn nt_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "nt", &expected);
}

#[test]
fn nu_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "nu", &expected);
}

#[test]
fn nu_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "nu", &expected);
}

#[test]
fn on_2025_residual_is_exactly_this() {
    // Nothing left: every parameter checked against a primary source.
    assert_residual(2025, "on", &[]);
}

#[test]
fn on_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
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
    ];

    assert_residual(2026, "on", &expected);
}

#[test]
fn pe_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.surtax_rate",
        "scalars.surtax_threshold",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "pe", &expected);
}

#[test]
fn pe_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.surtax_rate",
        "scalars.surtax_threshold",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "pe", &expected);
}

#[test]
fn qc_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.abatement_rate",
    ];

    assert_residual(2025, "qc", &expected);
}

#[test]
fn qc_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "scalars.abatement_rate",
    ];

    assert_residual(2026, "qc", &expected);
}

#[test]
fn sk_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
    ];

    assert_residual(2025, "sk", &expected);
}

#[test]
fn sk_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
    ];

    assert_residual(2026, "sk", &expected);
}

#[test]
fn yt_2025_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2025, "yt", &expected);
}

#[test]
fn yt_2026_residual_is_exactly_this() {
    let expected: Vec<&str> = vec![
        "brackets.income_tax",
        "scalars.age_amount_clawback_rate",
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.bpa",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.credit_rate",
        "scalars.disability_amount",
        "scalars.donation_first_tier",
        "scalars.donation_rate_first",
        "scalars.donation_rate_rest",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.medical_threshold_rate",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
        "scalars.tuition_transfer_max",
    ];

    assert_residual(2026, "yt", &expected);
}

/// A blunt progress marker across every jurisdiction. Seeing the number move is
/// the point of doing the pass incrementally.
#[test]
fn report_verification_progress() {
    let mut total = 0usize;

    for year in freshet_taxdata::SUPPORTED_YEARS {
        for province in freshet_taxdata::supported_provinces() {
            let packs = freshet_taxdata::packs(*year, province).unwrap();
            let n = packs.provincial.unverified().len();
            total += n;
            println!("{year} {province}: {n} provincial parameters still unverified");
        }
    }

    println!("federal: {} unverified", 
        freshet_taxdata::packs(2026, "on").unwrap().federal.unverified().len());
    println!("TOTAL provincial residual: {total}");
}
