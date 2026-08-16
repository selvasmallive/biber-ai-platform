//! British Columbia, built structure-first.
//!
//! Like Alberta, every BC parameter is an unverified placeholder, so these
//! assert shape rather than amounts. BC is the interesting case because it does
//! two things neither of the other provinces does: it kept its tuition credit,
//! and its low-income reduction is clawed back rather than simply ceasing.

use freshet_engine::{compute, Assessment, Decimal, FactSet, Severity};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn assess_in(province: &str, facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t1_forms(2025, province).unwrap();
    let packs = freshet_taxdata::packs(2025, province).unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute(&forms, &packs, &facts).unwrap()
}

fn bc(facts: &[(&str, &str)]) -> Assessment {
    assess_in("bc", facts)
}

fn fired(got: &Assessment) -> Vec<&str> {
    got.diagnostics.iter().map(|x| x.id.as_str()).collect()
}

// -- the thing that matters most ------------------------------------------

#[test]
fn no_bc_return_can_be_filed_on_placeholder_data() {
    let got = bc(&[("t4.employment_income", "80000")]);

    assert!(!got.is_filable(), "BC claims to be filable on placeholders");
    assert!(got.warnings.iter().all(|w| w.contains("unverified")));
}

/// BC479 carries BC's refundable credits and is not modelled. A quiet zero
/// would read as "you get nothing"; this makes the omission visible instead.
#[test]
fn the_unmodelled_refundable_credits_are_declared_not_hidden() {
    let got = bc(&[("t4.employment_income", "30000")]);

    assert!(fired(&got).contains(&"bc.bc479_not_modelled"));

    let warned = got
        .diagnostics
        .iter()
        .find(|x| x.id == "bc.bc479_not_modelled")
        .unwrap();

    assert_eq!(warned.severity, Severity::Warning);
    assert_eq!(got.get("prov.refundable_credits"), Some(d("0.00")));
}

// -- what BC has that the others do not -----------------------------------

/// Ontario abolished its tuition credit in 2017 and Alberta in 2020. BC kept
/// one, so these lines do real work here — and a return that assumed provinces
/// follow the federal rule would be wrong in all three provinces, in two
/// different directions.
#[test]
fn bc_does_grant_a_tuition_credit() {
    let with_fees = bc(&[
        ("t4.employment_income", "60000"),
        ("tuition.fees", "9000"),
    ]);
    let without = bc(&[("t4.employment_income", "60000")]);

    assert!(
        with_fees.get("bc.58560").unwrap() > d("0.00"),
        "BC refused a tuition credit it actually offers"
    );
    assert!(
        with_fees.get("prov.tax").unwrap() < without.get("prov.tax").unwrap(),
        "tuition did not reduce BC tax"
    );
}

#[test]
fn unused_bc_tuition_is_transferable_up_to_the_cap() {
    // Income too low to use the credit, so most of it is available to transfer.
    let got = bc(&[
        ("t4.employment_income", "14000"),
        ("tuition.fees", "20000"),
    ]);

    let transferable = got.get("bc.tuition_transferable").unwrap();
    assert!(transferable > d("0.00"));
    assert!(
        transferable <= d("5000.00"),
        "the transfer cap was ignored: {transferable}"
    );
}

/// The reduction is clawed back rather than simply stopping, so over the
/// phase-out range BC's effective rate rises faster than its bracket table
/// alone would suggest. That is a real feature of BC428, not a rounding effect.
#[test]
fn the_tax_reduction_is_clawed_back_as_income_rises() {
    let reduction_at = |income: &str| {
        bc(&[("t4.employment_income", income)])
            .get("bc.tax_reduction_amount")
            .unwrap()
    };

    let low = reduction_at("20000");
    let middle = reduction_at("32000");
    let high = reduction_at("60000");

    assert!(low > middle, "the reduction did not taper");
    assert!(middle > high, "the reduction did not keep tapering");
    assert_eq!(high, d("0.00"), "the reduction survived the phase-out");
}

#[test]
fn the_reduction_cannot_exceed_the_tax_it_reduces() {
    // Low income: the computed reduction is larger than the tax owing.
    let got = bc(&[("t4.employment_income", "16000")]);

    assert!(got.get("bc.tax_reduction").unwrap() <= got.get("bc.tax_before_reduction").unwrap());
    assert_eq!(
        got.get("prov.tax"),
        Some(d("0.00")),
        "the reduction turned BC tax negative"
    );
}

#[test]
fn the_reduction_is_announced_when_it_applies() {
    let helped = bc(&[("t4.employment_income", "26000")]);
    let not_helped = bc(&[("t4.employment_income", "120000")]);

    assert!(fired(&helped).contains(&"bc.tax_reduction_applied"));
    assert!(!fired(&not_helped).contains(&"bc.tax_reduction_applied"));
}

// -- composition -----------------------------------------------------------

#[test]
fn the_federal_return_is_identical_across_all_three_provinces() {
    let facts = [
        ("t4.employment_income", "90000"),
        ("rrsp.deduction_claimed", "3000"),
    ];

    let bc_ = bc(&facts);
    let ab = assess_in("ab", &facts);
    let on = assess_in("on", &facts);

    for line in ["fed.15000", "fed.23600", "fed.26000", "fed.30000", "fed.42000"] {
        assert_eq!(bc_.get(line), ab.get(line), "{line} differed: BC vs Alberta");
        assert_eq!(bc_.get(line), on.get(line), "{line} differed: BC vs Ontario");
    }
}

#[test]
fn bc_has_none_of_ontarios_or_albertas_machinery() {
    let got = bc(&[("t4.employment_income", "200000")]);

    for absent in [
        "on.surtax",
        "on.health_premium",
        "on.47900",
        "ab.supplemental_credit",
    ] {
        assert_eq!(got.get(absent), None, "{absent} leaked into BC");
    }
}

#[test]
fn seven_bands_all_bite() {
    // Whatever the thresholds turn out to be, each step up the table must cost
    // more per dollar than the last.
    let rate_at = |income: &str| {
        bc(&[("t4.employment_income", income)])
            .get("bc.tax_before_reduction")
            .unwrap()
            / d(income)
    };

    let ladder = ["45000", "95000", "110000", "130000", "180000", "250000", "400000"];
    let rates: Vec<Decimal> = ladder.iter().map(|i| rate_at(i)).collect();

    for pair in rates.windows(2) {
        assert!(
            pair[1] > pair[0],
            "the bracket table stopped graduating: {:?}",
            rates
        );
    }
}
