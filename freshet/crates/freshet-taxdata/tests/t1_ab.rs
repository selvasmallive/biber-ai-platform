//! Alberta, built structure-first.
//!
//! Every Alberta parameter is an unverified placeholder, so these tests assert
//! **shape**, not amounts. They check that the province composes with the
//! federal return, that its structural differences from Ontario are real rather
//! than copied, and above all that nothing here can be filed.
//!
//! Golden vectors come later, when AB428 is in hand. Asserting a refund figure
//! against numbers nobody has checked would be worse than asserting nothing —
//! it would look like verification.

use freshet_engine::{compute, Assessment, Decimal, FactSet};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn assess_in(province: &str, facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t1_forms(2025, province).unwrap();
    let packs = freshet_taxdata::packs(2025, province).unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute(&forms, &packs, &facts).unwrap()
}

fn alberta(facts: &[(&str, &str)]) -> Assessment {
    assess_in("ab", facts)
}

// -- the thing that matters most ------------------------------------------

/// Alberta is structure only. Until AB428 is checked, the provenance gate must
/// refuse to call any Alberta return filable — otherwise this work would have
/// shipped placeholder tax rates into somebody's return.
#[test]
fn no_alberta_return_can_be_filed_on_placeholder_data() {
    let got = alberta(&[("t4.employment_income", "80000")]);

    assert!(!got.is_filable(), "Alberta claims to be filable on placeholders");
    assert!(
        !got.warnings.is_empty(),
        "placeholder data produced no warning at all"
    );
    assert!(
        got.warnings.iter().all(|w| w.contains("unverified")),
        "unexpected warning kind: {:?}",
        got.warnings
    );
}

// -- composition -----------------------------------------------------------

#[test]
fn the_federal_return_is_identical_whichever_province_is_composed_in() {
    let facts = [
        ("t4.employment_income", "80000"),
        ("rrsp.deduction_claimed", "4000"),
    ];

    let ab = alberta(&facts);
    let on = assess_in("on", &facts);

    // The federal half of the return cannot depend on where you live, and this
    // is the assertion that keeps the shared form genuinely shared.
    for line in ["fed.15000", "fed.23600", "fed.26000", "fed.30000", "fed.42000"] {
        assert_eq!(
            ab.get(line),
            on.get(line),
            "{line} differed between Alberta and Ontario"
        );
    }
}

#[test]
fn alberta_supplies_the_contract_the_federal_return_reads() {
    let got = alberta(&[("t4.employment_income", "80000")]);

    assert_eq!(got.get("prov.tax"), got.get("ab.42800"));
    assert_eq!(
        got.get("prov.refundable_credits"),
        Some(d("0.00")),
        "Alberta has no provincial refundable credit on the T1"
    );
}

// -- what Alberta does not have -------------------------------------------

/// Ontario needs a surtax, a health premium, a low-income reduction and a CARE
/// credit. Alberta has none of them, and mirroring Ontario line for line would
/// have quietly invented all four.
#[test]
fn alberta_has_none_of_ontarios_extra_machinery() {
    let got = alberta(&[("t4.employment_income", "200000")]);

    for absent in [
        "on.surtax",
        "on.health_premium",
        "on.tax_reduction",
        "on.47900",
    ] {
        assert_eq!(got.get(absent), None, "{absent} leaked into Alberta");
    }
}

/// Alberta abolished its tuition and education amounts for 2020 and later —
/// the same trap Ontario set, where copying the federal structure invents a
/// credit the province does not offer.
#[test]
fn alberta_grants_no_tuition_credit() {
    let with_fees = alberta(&[
        ("t4.employment_income", "45000"),
        ("tuition.fees", "9000"),
    ]);
    let without = alberta(&[("t4.employment_income", "45000")]);

    assert_eq!(
        with_fees.get("prov.tax"),
        without.get("prov.tax"),
        "tuition moved Alberta tax"
    );

    // The federal credit is untouched: that one is real.
    assert!(with_fees.get("fed.32300").unwrap() > d("0.00"));
}

// -- what Alberta has that Ontario does not -------------------------------

/// Alberta's 2025 rate cut values credits at 8% while income above the first
/// bracket is still taxed at 10%. The supplement returns that 2% on credit
/// amounts above the threshold, so a large claim is not worth less than the
/// tax it offsets.
#[test]
fn the_supplemental_credit_only_applies_above_the_threshold() {
    // A modest return: credit amounts nowhere near the threshold.
    let small = alberta(&[("t4.employment_income", "50000")]);
    assert_eq!(
        small.get("ab.supplemental_credit"),
        Some(d("0.00")),
        "the supplement paid out below the threshold"
    );

    // A large medical claim pushes total credit amounts past it.
    let large = alberta(&[
        ("t4.employment_income", "200000"),
        ("medical.expenses_claimed", "90000"),
    ]);

    assert!(
        large.get("ab.supplemental_credit").unwrap() > d("0.00"),
        "the supplement never engaged: credits were {:?}",
        large.get("ab.58800")
    );
}

#[test]
fn alberta_tax_never_goes_negative() {
    // Credits far exceeding the tax must floor at nil, not become a refund.
    let got = alberta(&[
        ("t4.employment_income", "15000"),
        ("donations.claimed", "5000"),
    ]);

    assert_eq!(got.get("prov.tax"), Some(d("0.00")));
}

#[test]
fn the_first_bracket_is_taxed_at_the_lower_rate() {
    // Structural, not a value check: whatever the thresholds turn out to be,
    // Alberta's first band must be cheaper per dollar than its second.
    let low = alberta(&[("t4.employment_income", "40000")]);
    let high = alberta(&[("t4.employment_income", "140000")]);

    let rate = |a: &Assessment, income: &str| {
        a.get("ab.42800").unwrap() / d(income)
    };

    assert!(
        rate(&low, "40000") < rate(&high, "140000"),
        "the graduated bracket table is not graduating"
    );
}
