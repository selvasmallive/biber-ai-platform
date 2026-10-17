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
    // Down from sixteen on 2026-09-15. Ontario published its 2026 amounts and
    // five could be checked: the basic personal amount, both surtax
    // thresholds, and the two tax reduction amounts. The eleven below are
    // still the verified 2025 figures indexed at Ontario's confirmed 1.9%
    // factor, and stay unverified because indexing is a method rather than a
    // source — which the tax reduction per dependant proved, coming in at
    // 575 against an indexed 554.
    let expected: Vec<&str> = vec![
        "scalars.age_amount_max",
        "scalars.age_amount_threshold",
        "scalars.caregiver_base",
        "scalars.caregiver_max",
        "scalars.disability_amount",
        "scalars.eligible_dependant_base",
        "scalars.eligible_dependant_max",
        "scalars.medical_threshold_cap",
        "scalars.pension_income_max",
        "scalars.spouse_base",
        "scalars.spouse_max",
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

/// T2 is structure-first: the return computes, every corporate rate is a
/// placeholder. Pinned here so verifying one becomes a deliberate deletion.
#[test]
fn t2_fed_2025_residual_is_exactly_this() {
    let packs = freshet_taxdata::t2_packs(2025, "on").unwrap();
    let pack = if "fed" == "fed" { &packs.federal } else { &packs.provincial };

    let mut actual = pack.unverified();
    actual.sort();

    // Empty, as of 2026-10-17: every federal corporate rate and every figure
    // in the ITA 125(5.1) business limit reduction formulas has been read from
    // the Act or the T2 guide and cited in the pack. The six reduction figures
    // are pinned by value as well, below, because this list would not notice
    // one of them being edited.
    let expected: Vec<&str> = vec![];
    let want: Vec<String> = expected.iter().map(|s| s.to_string()).collect();

    assert_eq!(actual, want, "the T2 residual moved without being recorded");
}

/// T2 is structure-first: the return computes, every corporate rate is a
/// placeholder. Pinned here so verifying one becomes a deliberate deletion.
#[test]
fn t2_fed_2026_residual_is_exactly_this() {
    let packs = freshet_taxdata::t2_packs(2026, "on").unwrap();
    let pack = if "fed" == "fed" { &packs.federal } else { &packs.provincial };

    let mut actual = pack.unverified();
    actual.sort();

    // Empty, as of 2026-10-17: every federal corporate rate and every figure
    // in the ITA 125(5.1) business limit reduction formulas has been read from
    // the Act or the T2 guide and cited in the pack. The six reduction figures
    // are pinned by value as well, below, because this list would not notice
    // one of them being edited.
    let expected: Vec<&str> = vec![];
    let want: Vec<String> = expected.iter().map(|s| s.to_string()).collect();

    assert_eq!(actual, want, "the T2 residual moved without being recorded");
}

/// T2 is structure-first: the return computes, every corporate rate is a
/// placeholder. Pinned here so verifying one becomes a deliberate deletion.
#[test]
fn t2_on_2025_residual_is_exactly_this() {
    let packs = freshet_taxdata::t2_packs(2025, "on").unwrap();
    let pack = if "on" == "fed" { &packs.federal } else { &packs.provincial };

    let mut actual = pack.unverified();
    actual.sort();

    // Empty: both Ontario rates are settled for a 2025 tax year. The lower
    // rate falls on 1 July 2026, which cannot reach one.
    let expected: Vec<&str> = vec![];
    let want: Vec<String> = expected.iter().map(|s| s.to_string()).collect();

    assert_eq!(actual, want, "the T2 residual moved without being recorded");
}

/// T2 is structure-first: the return computes, every corporate rate is a
/// placeholder. Pinned here so verifying one becomes a deliberate deletion.
#[test]
fn t2_on_2026_residual_is_exactly_this() {
    let packs = freshet_taxdata::t2_packs(2026, "on").unwrap();
    let pack = if "on" == "fed" { &packs.federal } else { &packs.provincial };

    let mut actual = pack.unverified();
    actual.sort();

    // Empty. Ontario's lower rate changes on 1 July 2026, which a pack keyed
    // by calendar year could not express — so the year was cut in two and
    // both halves cited. `t2_packs(2026, "on")` returns the first of them;
    // the pair is assembled by `t2_period_packs`, which is what every caller
    // now uses.
    let expected: Vec<&str> = vec![];
    let want: Vec<String> = expected.iter().map(|s| s.to_string()).collect();

    assert_eq!(actual, want, "the T2 residual moved without being recorded");
}

/// The ITA 125(5.1) business limit reduction figures, pinned to the Act.
///
/// `unverified()` only answers "is the flag set", and the flag is set by hand.
/// These six parameters are the ones that decide whether a corporation keeps
/// its small business deduction, so the ledger records their *values* as well:
/// a figure edited without re-reading the Act fails here, in either direction,
/// which is the same contract the residual lists carry.
///
/// Each expected value, and where it was read:
///   t2_taxable_capital_threshold  10,000,000  125(5.1)(a), B is
///                                             "0.225% x (C - $10 million)"
///   t2_taxable_capital_rate            0.00225 the 0.225% in the same formula
///   t2_taxable_capital_divisor          90,000 125(5.1)(a), "A x B / $90,000";
///                                             0.225% of $40 million exactly,
///                                             which puts the top of the
///                                             phase-out at $50 million
///   t2_aaii_threshold                   50,000 125(5.1)(b),
///                                             "D/$500,000 x 5(E - $50,000)"
///   t2_aaii_multiplier                       5 the 5 in the same formula, so
///                                             $150,000 removes the limit
///   t2_aaii_limit_divisor              500,000 the $500,000 divisor in it,
///                                             which is not prorated
///
/// Read from https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-125.html
/// on 2026-10-17 and cross-checked against T4012 chapter 4 and CRA's Budget
/// 2018 small business deduction page; the citations are in the packs.
#[test]
fn the_business_limit_reduction_figures_are_cited_and_unchanged() {
    let expected = [
        ("t2_taxable_capital_threshold", "10000000"),
        ("t2_taxable_capital_rate", "0.00225"),
        ("t2_taxable_capital_divisor", "90000"),
        ("t2_aaii_threshold", "50000"),
        ("t2_aaii_multiplier", "5"),
        ("t2_aaii_limit_divisor", "500000"),
    ];

    for year in [2025u16, 2026] {
        let packs = freshet_taxdata::t2_packs(year, "on").unwrap();

        for (key, value) in expected {
            let param = packs
                .federal
                .scalars
                .get(key)
                .unwrap_or_else(|| panic!("{year}: {key} is missing from the T2 federal pack"));

            assert_eq!(
                param.value,
                freshet_engine::Decimal::from_str_exact(value).unwrap(),
                "{year}: {key} moved; re-read ITA 125(5.1) before changing it"
            );

            // The filing gate reads this flag, so an unverified figure here
            // would block a return rather than quietly produce a wrong one.
            assert!(
                param.verified,
                "{year}: {key} is not verified, so nothing can be filed"
            );

            assert!(
                param.source.contains("125(5.1)"),
                "{year}: {key} must cite the subsection it comes from, not just a value"
            );
        }
    }
}
