//! Golden vectors for the T1 2025 Ontario return.
//!
//! Expected values here are hand-computed from the form logic and checked line
//! by line, so a change in engine behaviour shows up as a failing line rather
//! than a plausible-looking wrong refund. These are *not* CRA certification
//! vectors -- those arrive from CRA each November under NDA and get added as a
//! separate, authoritative suite.

use freshet_engine::{compute, Assessment, Decimal, FactSet};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn assess(facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t1_forms(2025, "on").unwrap();
    let packs = freshet_taxdata::packs(2025, "on").unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute(&forms, &packs, &facts).unwrap()
}

/// Assert a set of lines at once so a failure reports every wrong line, not
/// just the first.
fn assert_lines(got: &Assessment, want: &[(&str, &str)]) {
    let mut wrong = Vec::new();

    for (id, expected) in want {
        match got.get(id) {
            Some(actual) if actual == d(expected) => {}
            Some(actual) => wrong.push(format!("  {id}: want {expected}, got {actual}")),
            None => wrong.push(format!("  {id}: line not computed")),
        }
    }

    assert!(wrong.is_empty(), "wrong lines:\n{}", wrong.join("\n"));
}

/// Employment income of $85,000 in Ontario, CPP/CPP2/EI all at the 2025
/// maximum, $5,000 into an RRSP, $16,000 withheld at source.
#[test]
fn salaried_ontario_filer_with_an_rrsp_contribution() {
    let got = assess(&[
        ("t4.employment_income", "85000"),
        ("t4.cpp_contributions", "4034.10"),
        ("t4.cpp2_contributions", "396.00"),
        ("t4.ei_premiums", "1077.48"),
        ("t4.income_tax_deducted", "16000"),
        ("rrsp.deduction_claimed", "5000"),
    ]);

    assert_lines(
        &got,
        &[
            ("fed.15000", "85000.00"),
            // Enhanced CPP is deducted, not credited: 4034.10 * (1.00/5.95) + 396.00.
            ("fed.22215", "1074.00"),
            ("fed.23300", "6074.00"),
            ("fed.23600", "78926.00"),
            ("fed.26000", "78926.00"),
            // Well below the phase-out, so the full BPA applies.
            ("fed.30000", "16129.00"),
            // Base CPP is credited: 4034.10 * (4.95/5.95).
            ("fed.30800", "3356.10"),
            ("fed.31260", "1471.00"),
            ("fed.33500", "22033.58"),
            ("fed.35000", "3194.87"),
            // 57375 @ 14.5% + 21551 @ 20.5%.
            ("fed.40400", "12737.33"),
            ("fed.42000", "9542.46"),
            ("on.61500", "867.62"),
            ("on.tax_before_surtax", "4185.78"),
            // Ontario tax is under the first surtax threshold.
            ("on.surtax", "0.00"),
            ("on.tax_after_reduction", "4185.78"),
            // Taxable income of 78,926 sits on the $750 plateau of the health
            // premium chart, and the premium is added after every credit.
            ("on.health_premium", "750.00"),
            ("on.42800", "4935.78"),
            ("summary.total_tax", "14478.24"),
            // Negative balance is a refund.
            ("summary.balance", "-1521.76"),
        ],
    );
}

/// The basic personal amount phases down on a straight line between the 29% and
/// 33% bracket thresholds. $215,648 of net income sits exactly halfway.
#[test]
fn basic_personal_amount_phases_out_across_the_top_brackets() {
    let bpa_at = |income: &str| {
        assess(&[("t4.employment_income", income)])
            .get("fed.30000")
            .unwrap()
    };

    // Below the phase-out: full amount.
    assert_eq!(bpa_at("50000"), d("16129.00"));
    assert_eq!(bpa_at("177882"), d("16129.00"));

    // Exactly halfway: 16129 - (16129 - 14538) * 0.5.
    assert_eq!(bpa_at("215648"), d("15333.50"));

    // At and above the top threshold: floor amount, and it stops falling.
    assert_eq!(bpa_at("253414"), d("14538.00"));
    assert_eq!(bpa_at("400000"), d("14538.00"));
}

/// Ontario levies a surtax on its own tax. This exercises both tiers.
#[test]
fn ontario_surtax_applies_at_both_thresholds() {
    let got = assess(&[("t4.employment_income", "150000")]);

    assert_lines(
        &got,
        &[
            ("on.61500", "643.72"),
            ("on.tax_before_surtax", "11801.88"),
            // 20% above 5710, plus a further 36% above 7307.
            ("on.surtax", "2836.53"),
            ("on.tax_after_surtax", "14638.41"),
            ("on.health_premium", "750.00"),
            ("on.42800", "15388.41"),
        ],
    );
}

/// A return with no income owes nothing and is not pushed negative by credits.
#[test]
fn a_nil_return_owes_nothing() {
    let got = assess(&[]);

    assert_lines(
        &got,
        &[
            ("fed.15000", "0.00"),
            ("fed.23600", "0.00"),
            ("fed.42000", "0.00"),
            ("on.42800", "0.00"),
            ("summary.total_tax", "0.00"),
            ("summary.balance", "0.00"),
        ],
    );
}

/// Withholding above the amount payable comes back as a refund, dollar for
/// dollar.
#[test]
fn overwithholding_becomes_a_refund() {
    let base = assess(&[("t4.employment_income", "60000")]);
    let withheld = assess(&[
        ("t4.employment_income", "60000"),
        ("t4.income_tax_deducted", "9000"),
    ]);

    let payable = base.get("summary.total_tax").unwrap();
    assert_eq!(
        withheld.get("summary.balance").unwrap(),
        payable - d("9000")
    );
}

// -- dependants on a single return ----------------------------------------

/// A single parent claims the eligible dependant amount, which is the same size
/// as the spousal amount and takes its place.
#[test]
fn a_single_parent_claims_the_eligible_dependant_amount() {
    let got = assess(&[
        ("t4.employment_income", "50000"),
        ("dependants.eligible_dependant_claimed", "1"),
    ]);

    assert_eq!(got.get("fed.30400").unwrap(), d("16129.00"));
    assert_eq!(got.get("on.58160").unwrap(), d("10823.00"));
}

/// Ontario reduces a base amount by the dependant's income and *then* caps the
/// result. The base exceeds the maximum by $1,082, so that much of a
/// dependant's income costs the claim nothing — a shape the federal amount does
/// not share, and one the model originally missed entirely.
#[test]
fn the_ontario_dependant_amounts_are_a_capped_base_not_a_flat_reduction() {
    let claim_at = |income: &str| {
        assess(&[
            ("t4.employment_income", "50000"),
            ("dependants.eligible_dependant_claimed", "1"),
            ("dependants.eligible_dependant_net_income", income),
        ])
        .get("on.58160")
        .unwrap()
    };

    // Inside the gap between the 11,905 base and the 10,823 cap, the claim is
    // pinned at the maximum rather than falling.
    assert_eq!(claim_at("0"), d("10823.00"));
    assert_eq!(claim_at("1082"), d("10823.00"));

    // Past it, every further dollar reduces the claim one for one.
    assert_eq!(claim_at("2082"), d("9823.00"));
    assert_eq!(claim_at("5000"), d("6905.00"));

    // And it runs out at the base, not at the maximum.
    assert_eq!(claim_at("11905"), d("0.00"));
}

#[test]
fn the_eligible_dependant_amount_is_reduced_by_that_dependants_income() {
    let got = assess(&[
        ("t4.employment_income", "50000"),
        ("dependants.eligible_dependant_claimed", "1"),
        ("dependants.eligible_dependant_net_income", "4000"),
    ]);

    assert_eq!(got.get("fed.30400").unwrap(), d("12129.00"));
}

#[test]
fn a_single_filer_deducts_their_own_child_care() {
    let got = assess(&[
        ("t4.employment_income", "50000"),
        ("childcare.expenses_claimed", "5000"),
        ("dependants.count_under_7", "1"),
    ]);

    // Under both the $8,000 child limit and two thirds of income.
    assert_eq!(got.get("fed.21400").unwrap(), d("5000.00"));
    assert_eq!(got.get("fed.23600").unwrap(), d("45000.00"));
}

#[test]
fn child_care_with_no_children_listed_is_an_error() {
    let got = assess(&[
        ("t4.employment_income", "50000"),
        ("childcare.expenses_claimed", "5000"),
    ]);

    assert!(fired(&got).contains(&"childcare.no_dependants"));
    assert!(got.has_errors());
}

#[test]
fn hitting_the_earned_income_cap_is_explained_rather_than_silently_applied() {
    let got = assess(&[
        ("t4.employment_income", "9000"),
        ("childcare.expenses_claimed", "10000"),
        ("dependants.count_under_7", "1"),
    ]);

    assert_eq!(got.get("fed.21400").unwrap(), d("6000.00"));
    assert!(fired(&got).contains(&"childcare.capped_by_earned_income"));
    assert!(!got.has_errors());
}

// -- tax year 2026 --------------------------------------------------------

fn assess_2026(facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t1_forms(2026, "on").unwrap();
    let packs = freshet_taxdata::packs(2026, "on").unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute(&forms, &packs, &facts).unwrap()
}

/// The certification target. One form definition serves both years — only the
/// parameter pack differs — which is the whole point of keeping tax rules as
/// data rather than code.
#[test]
fn the_same_form_computes_2026_with_its_own_pack() {
    let got = assess_2026(&[("t4.employment_income", "50000")]);

    assert_eq!(got.tax_year, 2026);
    assert_eq!(got.get("fed.30000").unwrap(), d("16452.00"));
    // 14% flat for 2026, against 14.5% blended for 2025.
    assert_eq!(got.get("fed.40400").unwrap(), d("7000.00"));
}

#[test]
fn the_2026_lowest_rate_is_a_full_year_fourteen_percent() {
    let a = assess(&[("t4.employment_income", "50000")]);
    let b = assess_2026(&[("t4.employment_income", "50000")]);

    // 2025 carried the 14.5% blend from the mid-year rate cut; 2026 does not.
    assert_eq!(a.get("fed.40400").unwrap(), d("7250.00"));
    assert!(b.get("fed.40400").unwrap() < a.get("fed.40400").unwrap());
}

#[test]
fn the_2026_bracket_thresholds_moved_with_indexation() {
    // The first bracket ends at $58,523 in 2026 against $57,375 in 2025, so an
    // income between the two is taxed entirely at the lowest rate in 2026 only.
    let got = assess_2026(&[("t4.employment_income", "58523")]);
    let expected = d("58523") * d("0.14");

    assert_eq!(got.get("fed.40400").unwrap(), expected.round_dp(2));
}

#[test]
fn both_supported_years_refuse_to_file_on_unverified_data() {
    assert!(!assess(&[("t4.employment_income", "50000")]).is_filable());
    assert!(!assess_2026(&[("t4.employment_income", "50000")]).is_filable());
}

// -- refundable credits ---------------------------------------------------

/// Two employers each withhold up to their own maximum. The excess is not an
/// error on the slips — it comes back as a refundable credit.
#[test]
fn over_contributed_cpp_and_ei_are_refunded() {
    let got = assess(&[
        ("t4.employment_income", "85000"),
        ("t4.cpp_contributions", "4554.10"),
        ("t4.cpp2_contributions", "396.00"),
        ("t4.ei_premiums", "1282.48"),
    ]);

    assert_eq!(got.get("fed.44800").unwrap(), d("520.00"));
    assert_eq!(got.get("fed.45000").unwrap(), d("205.00"));
    assert_eq!(got.get("summary.refundable_credits").unwrap(), d("725.00"));
}

#[test]
fn contributions_at_the_maximum_produce_no_overpayment() {
    let got = assess(&[
        ("t4.employment_income", "85000"),
        ("t4.cpp_contributions", "4034.10"),
        ("t4.cpp2_contributions", "396.00"),
        ("t4.ei_premiums", "1077.48"),
    ]);

    assert_eq!(got.get("summary.refundable_credits").unwrap(), d("0.00"));
}

/// Reproduces Ontario's own worked example: $51,000 of income against $8,000 of
/// allowable expenses gives a 53% rate and a $4,240 credit.
#[test]
fn the_care_credit_matches_ontarios_published_example() {
    let got = assess(&[
        ("t4.employment_income", "59000"),
        ("childcare.expenses_claimed", "8000"),
        ("dependants.count_under_7", "1"),
    ]);

    assert_eq!(got.get("fed.21400").unwrap(), d("8000.00"));
    assert_eq!(got.get("on.care_income").unwrap(), d("51000.00"));
    assert_eq!(got.get("on.care_rate").unwrap(), d("0.53"));
    assert_eq!(got.get("on.47900").unwrap(), d("4240.00"));
}

#[test]
fn the_care_rate_steps_rather_than_sliding() {
    // "2% for each $2,500 or portion" means a single dollar over a boundary
    // costs a full two points. Interpolating would understate the drop.
    let rate_at = |income: &str| {
        assess(&[
            ("t4.employment_income", income),
            ("childcare.expenses_claimed", "8000"),
            ("dependants.count_under_7", "1"),
        ])
        .get("on.care_rate")
        .unwrap()
    };

    // Net income lands $8,000 below employment income once the deduction runs.
    assert_eq!(rate_at("28000"), d("0.75")); // exactly at the 20,000 ceiling
    assert_eq!(rate_at("28001"), d("0.73")); // one dollar over costs two points
    assert_eq!(rate_at("48000"), d("0.59")); // the 40,000 boundary
    assert_eq!(rate_at("68000"), d("0.51")); // the 60,000 boundary
}

#[test]
fn the_care_credit_disappears_above_the_family_income_ceiling() {
    let got = assess(&[
        ("t4.employment_income", "160000"),
        ("childcare.expenses_claimed", "8000"),
        ("dependants.count_under_7", "1"),
    ]);

    assert_eq!(got.get("on.care_rate").unwrap(), Decimal::ZERO);
    assert_eq!(got.get("on.47900").unwrap(), d("0.00"));
}

/// The point of a refundable credit: it is paid even when there is no tax to
/// reduce. A non-refundable credit would simply be wasted here.
#[test]
fn a_refundable_credit_is_paid_when_no_tax_is_owing() {
    let got = assess(&[
        ("t4.employment_income", "20000"),
        ("childcare.expenses_claimed", "8000"),
        ("dependants.count_under_7", "1"),
    ]);

    // The personal amounts already cover this income, so there is no tax for a
    // non-refundable credit to reduce.
    assert_eq!(got.get("summary.total_tax").unwrap(), d("0.00"));

    // The CARE credit is paid anyway: 75% of the $8,000 deduction.
    assert_eq!(got.get("on.47900").unwrap(), d("6000.00"));
    // Nothing was withheld, so the whole credit comes back as a refund.
    assert_eq!(got.get("summary.balance").unwrap(), d("-6000.00"));
}

// -- self-employment ------------------------------------------------------

/// A self-employed person is both employee and employer, so they pay both CPP
/// halves. One half is a deduction, the other a credit — which is what keeps
/// them level with an employee whose employer paid the second half.
#[test]
fn self_employment_pays_both_halves_of_cpp_and_splits_the_relief() {
    let got = assess(&[
        ("self_employment.gross", "60000"),
        ("self_employment.expenses", "20000"),
    ]);

    assert_eq!(got.get("fed.13500").unwrap(), d("40000.00"));

    // $36,500 pensionable after the basic exemption, at 4.95% x 2.
    assert_eq!(got.get("fed.cpp_se_pensionable").unwrap(), d("36500.00"));
    assert_eq!(got.get("fed.cpp_se_base").unwrap(), d("3613.50"));

    // Half deducted, half credited.
    assert_eq!(got.get("fed.22200").unwrap(), d("1806.75"));
    assert_eq!(got.get("fed.31000").unwrap(), d("1806.75"));

    // The enhanced portion is deducted in full, both halves.
    assert_eq!(got.get("fed.22215").unwrap(), d("730.00"));
    assert_eq!(got.get("fed.23600").unwrap(), d("37463.25"));
}

#[test]
fn a_business_loss_reduces_other_income_and_attracts_no_cpp() {
    let got = assess(&[
        ("t4.employment_income", "50000"),
        ("t4.cpp_contributions", "2500"),
        ("self_employment.gross", "10000"),
        ("self_employment.expenses", "25000"),
    ]);

    // The line is deliberately not floored: a loss is legitimate.
    assert_eq!(got.get("fed.13500").unwrap(), d("-15000.00"));
    assert_eq!(got.get("fed.15000").unwrap(), d("35000.00"));

    assert_eq!(got.get("fed.cpp_se_pensionable").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.22200").unwrap(), d("0.00"));
}

#[test]
fn a_job_that_already_maxed_cpp_leaves_nothing_for_self_employment() {
    let got = assess(&[
        ("t4.employment_income", "80000"),
        ("t4.cpp_contributions", "4034.10"),
        ("self_employment.gross", "40000"),
    ]);

    // The T4 already covers the whole ceiling, so the side business owes no
    // further base CPP.
    assert_eq!(got.get("fed.cpp_se_pensionable").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.31000").unwrap(), d("0.00"));
}

#[test]
fn self_employment_counts_toward_the_child_care_earned_income_cap() {
    // Without it the cap would be two thirds of nothing, and the whole child
    // care claim would vanish for a self-employed parent.
    let got = assess(&[
        ("self_employment.gross", "30000"),
        ("childcare.expenses_claimed", "8000"),
        ("dependants.count_under_7", "1"),
    ]);

    assert_eq!(got.get("fed.childcare_income_limit").unwrap(), d("20000.00"));
    assert_eq!(got.get("fed.21400").unwrap(), d("8000.00"));
}

#[test]
fn self_employment_counts_as_working_income_for_the_workers_benefit() {
    let got = assess(&[
        ("taxpayer.age", "30"),
        ("self_employment.gross", "15000"),
    ]);

    assert_eq!(got.get("fed.cwb_working_income").unwrap(), d("15000.00"));
    assert_eq!(got.get("fed.45300").unwrap(), d("1633.00"));
}

#[test]
fn every_kind_of_self_employment_reaches_total_income() {
    let got = assess(&[
        ("self_employment.gross", "20000"),
        ("self_employment.expenses", "5000"),
        ("professional.gross", "30000"),
        ("professional.expenses", "8000"),
        ("farming.gross", "12000"),
        ("farming.expenses", "4000"),
        ("fishing.gross", "9000"),
        ("fishing.expenses", "3000"),
    ]);

    assert_eq!(got.get("fed.13500").unwrap(), d("15000.00"));
    assert_eq!(got.get("fed.13700").unwrap(), d("22000.00"));
    assert_eq!(got.get("fed.14100").unwrap(), d("8000.00"));
    assert_eq!(got.get("fed.14300").unwrap(), d("6000.00"));

    assert_eq!(got.get("fed.total_self_employment").unwrap(), d("51000.00"));
    assert_eq!(got.get("fed.15000").unwrap(), d("51000.00"));
}

/// CPP is charged on every kind of self-employment, not only on a business.
/// Keying it to line 13500 alone would let a professional or a fisher escape
/// contributions entirely.
#[test]
fn cpp_is_charged_on_professional_and_fishing_income_too() {
    let got = assess(&[
        ("professional.gross", "40000"),
        ("fishing.gross", "10000"),
    ]);

    assert_eq!(got.get("fed.total_self_employment").unwrap(), d("50000.00"));
    // The whole $50,000 less the basic exemption, capped by the ceiling.
    assert_eq!(got.get("fed.cpp_se_pensionable").unwrap(), d("46500.00"));
    assert!(got.get("fed.22200").unwrap() > Decimal::ZERO);
}

#[test]
fn a_farmer_gets_the_workers_benefit_and_the_child_care_cap() {
    let got = assess(&[
        ("taxpayer.age", "30"),
        ("farming.gross", "30000"),
        ("childcare.expenses_claimed", "8000"),
        ("dependants.count_under_7", "1"),
    ]);

    // Two thirds of farming income, not of zero employment income.
    assert_eq!(got.get("fed.childcare_income_limit").unwrap(), d("20000.00"));
    assert_eq!(got.get("fed.21400").unwrap(), d("8000.00"));
    assert_eq!(got.get("fed.cwb_working_income").unwrap(), d("30000.00"));
}

// -- capital cost allowance -----------------------------------------------

#[test]
fn the_half_year_rule_applies_only_to_new_additions() {
    // $10,000 carried forward plus $5,000 bought this year: only half the new
    // spend enters the base, so the base is $12,500 and not $15,000.
    let bought = assess(&[
        ("self_employment.gross", "60000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.class8.additions", "5000"),
    ]);
    assert_eq!(bought.get("fed.cca_class8_base").unwrap(), d("12500.00"));
    assert_eq!(bought.get("fed.cca_class8").unwrap(), d("2500.00"));

    // Nothing bought this year, so the whole balance is available.
    let quiet = assess(&[
        ("self_employment.gross", "60000"),
        ("cca.class8.opening_ucc", "10000"),
    ]);
    assert_eq!(quiet.get("fed.cca_class8_base").unwrap(), d("10000.00"));
    assert_eq!(quiet.get("fed.cca_class8").unwrap(), d("2000.00"));
}

#[test]
fn a_disposition_reduces_the_pool_without_triggering_the_half_year_rule() {
    let got = assess(&[
        ("self_employment.gross", "60000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.class8.dispositions", "3000"),
    ]);

    // Net additions are negative, so there is no first-year adjustment at all.
    assert_eq!(got.get("fed.cca_class8_base").unwrap(), d("7000.00"));
    assert_eq!(got.get("fed.cca_class8").unwrap(), d("1400.00"));
}

#[test]
fn each_class_depreciates_at_its_own_rate_and_they_total() {
    let got = assess(&[
        ("self_employment.gross", "60000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.class50.additions", "4000"),
    ]);

    assert_eq!(got.get("fed.cca_class8").unwrap(), d("2000.00"));
    // Computers at 55%, on half of a first-year purchase.
    assert_eq!(got.get("fed.cca_class50").unwrap(), d("1100.00"));
    assert_eq!(got.get("fed.cca_total").unwrap(), d("3100.00"));
}

#[test]
fn capital_cost_allowance_reduces_net_business_income() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("self_employment.expenses", "10000"),
        ("cca.class8.opening_ucc", "10000"),
    ]);

    assert_eq!(got.get("fed.13500").unwrap(), d("38000.00"));
}

#[test]
fn selling_for_more_than_the_pool_is_worth_produces_recapture() {
    // $10,000 of tax value left, sold for $15,000: the $5,000 of depreciation
    // already deducted comes back as income.
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.class8.dispositions", "15000"),
    ]);

    assert_eq!(got.get("fed.cca_class8_raw").unwrap(), d("-5000.00"));
    assert_eq!(got.get("fed.cca_class8_recapture").unwrap(), d("5000.00"));
    // A pool in recapture has nothing left to depreciate.
    assert_eq!(got.get("fed.cca_class8").unwrap(), d("0.00"));

    // Recapture is income, so business income goes *up*.
    assert_eq!(got.get("fed.se_before_home_office").unwrap(), d("55000.00"));
    assert!(fired(&got).contains(&"cca.recapture"));
}

#[test]
fn emptying_a_class_with_value_left_gives_a_terminal_loss() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.class8.dispositions", "3000"),
        ("cca.class8.all_disposed", "1"),
    ]);

    assert_eq!(got.get("fed.cca_class8_terminal").unwrap(), d("7000.00"));
    // Taken in full, so no ordinary CCA on the same pool.
    assert_eq!(got.get("fed.cca_class8").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.se_before_home_office").unwrap(), d("43000.00"));
    assert!(fired(&got).contains(&"cca.terminal_loss"));
}

#[test]
fn a_terminal_loss_needs_the_class_to_be_empty() {
    // Same disposition, but assets remain: ordinary CCA continues instead.
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.class8.dispositions", "3000"),
    ]);

    assert_eq!(got.get("fed.cca_class8_terminal").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.cca_class8").unwrap(), d("1400.00"));
}

#[test]
fn an_expensive_car_is_depreciated_only_up_to_the_prescribed_limit() {
    let got = assess(&[
        ("self_employment.gross", "80000"),
        ("cca.class10_1.additions", "60000"),
    ]);

    // The cost above the limit is simply not depreciable.
    assert_eq!(got.get("fed.cca_class10_1_capped_cost").unwrap(), d("38000.00"));
    // Half-year rule on the capped cost, then 30%.
    assert_eq!(got.get("fed.cca_class10_1_base").unwrap(), d("19000.00"));
    assert_eq!(got.get("fed.cca_class10_1").unwrap(), d("5700.00"));
}

/// The defining feature of class 10.1: however the vehicle is sold, there is
/// never recapture and never a terminal loss. A pool that would produce either
/// in class 10 produces neither here.
#[test]
fn class_ten_point_one_never_recaptures() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class10_1.opening_ucc", "20000"),
        ("cca.class10_1.dispositions", "30000"),
    ]);

    assert_eq!(got.get("fed.recapture_total").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.terminal_loss_total").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.cca_class10_1").unwrap(), d("0.00"));
    // Business income is untouched by the sale.
    assert_eq!(got.get("fed.se_before_home_office").unwrap(), d("50000.00"));
}

// -- claiming less than the maximum CCA -----------------------------------

#[test]
fn capital_cost_allowance_defaults_to_the_maximum() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
    ]);

    assert_eq!(got.get("fed.cca_maximum").unwrap(), d("2000.00"));
    assert_eq!(got.get("fed.cca_total").unwrap(), d("2000.00"));
}

/// CCA is discretionary. Claiming less leaves the balance in the pool for a
/// later year, which is worth doing when this year's income is already covered
/// by personal amounts.
#[test]
fn a_smaller_claim_is_honoured_and_flagged() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.limit_claim", "1"),
        ("cca.claimed", "1200"),
    ]);

    assert_eq!(got.get("fed.cca_maximum").unwrap(), d("2000.00"));
    assert_eq!(got.get("fed.cca_total").unwrap(), d("1200.00"));
    // The $800 left unclaimed still reduces income by less, so income is higher.
    assert_eq!(got.get("fed.13500").unwrap(), d("48800.00"));

    assert!(fired(&got).contains(&"cca.claimed_below_maximum"));
}

#[test]
fn claiming_nothing_is_allowed() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.limit_claim", "1"),
        ("cca.claimed", "0"),
    ]);

    assert_eq!(got.get("fed.cca_total").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.13500").unwrap(), d("50000.00"));
}

#[test]
fn a_claim_above_the_maximum_is_capped_rather_than_accepted() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("cca.class8.opening_ucc", "10000"),
        ("cca.limit_claim", "1"),
        ("cca.claimed", "9999"),
    ]);

    assert_eq!(got.get("fed.cca_total").unwrap(), d("2000.00"));
    // Capped, so nothing is left unclaimed and there is nothing to flag.
    assert!(!fired(&got).contains(&"cca.claimed_below_maximum"));
}

// -- business use of home -------------------------------------------------

#[test]
fn the_home_office_share_follows_the_floor_area() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("self_employment.expenses", "20000"),
        ("home_office.expenses", "12000"),
        ("home_office.area_business", "200"),
        ("home_office.area_total", "1000"),
    ]);

    assert_eq!(got.get("fed.home_office_fraction").unwrap(), d("0.20"));
    assert_eq!(got.get("fed.home_office_eligible").unwrap(), d("2400.00"));
    assert_eq!(got.get("fed.home_office_claimed").unwrap(), d("2400.00"));
    assert_eq!(got.get("fed.13500").unwrap(), d("27600.00"));
}

/// The rule people get wrong: business-use-of-home cannot create or deepen a
/// loss. It is capped at the income left after every other expense, and the
/// remainder carries forward rather than being lost.
#[test]
fn the_home_office_deduction_cannot_create_a_loss() {
    let got = assess(&[
        ("self_employment.gross", "20000"),
        ("self_employment.expenses", "19000"),
        ("home_office.expenses", "12000"),
        ("home_office.area_business", "200"),
        ("home_office.area_total", "1000"),
    ]);

    assert_eq!(got.get("fed.se_before_home_office").unwrap(), d("1000.00"));
    // Only the $1,000 that exists can be used.
    assert_eq!(got.get("fed.home_office_claimed").unwrap(), d("1000.00"));
    assert_eq!(got.get("fed.home_office_carryforward").unwrap(), d("1400.00"));
    assert_eq!(got.get("fed.13500").unwrap(), d("0.00"));

    assert!(fired(&got).contains(&"home_office.carried_forward"));
}

#[test]
fn a_business_already_in_a_loss_claims_no_home_office_at_all() {
    let got = assess(&[
        ("self_employment.gross", "10000"),
        ("self_employment.expenses", "15000"),
        ("home_office.expenses", "12000"),
        ("home_office.area_business", "200"),
        ("home_office.area_total", "1000"),
    ]);

    assert_eq!(got.get("fed.home_office_claimed").unwrap(), d("0.00"));
    assert_eq!(got.get("fed.home_office_carryforward").unwrap(), d("2400.00"));
    // The loss is unchanged — home office did not deepen it.
    assert_eq!(got.get("fed.13500").unwrap(), d("-5000.00"));
}

#[test]
fn a_missing_floor_area_does_not_divide_by_zero() {
    let got = assess(&[
        ("self_employment.gross", "50000"),
        ("home_office.expenses", "12000"),
    ]);

    assert_eq!(got.get("fed.home_office_fraction").unwrap(), Decimal::ZERO);
    assert_eq!(got.get("fed.home_office_claimed").unwrap(), d("0.00"));
}

// -- Canada Workers Benefit -----------------------------------------------

#[test]
fn the_workers_benefit_builds_on_working_income_then_caps() {
    // 27% of income above the $3,000 floor, up to the single maximum.
    let low = assess(&[("taxpayer.age", "30"), ("t4.employment_income", "5000")]);
    assert_eq!(low.get("fed.45300").unwrap(), d("540.00"));

    let capped = assess(&[("taxpayer.age", "30"), ("t4.employment_income", "15000")]);
    assert_eq!(capped.get("fed.45300").unwrap(), d("1633.00"));
}

#[test]
fn the_workers_benefit_phases_out_and_reaches_zero() {
    let partial = assess(&[("taxpayer.age", "30"), ("t4.employment_income", "30000")]);
    // 1,633 less 15% of the 3,145 above the $26,855 threshold.
    assert_eq!(partial.get("fed.45300").unwrap(), d("1161.25"));

    let gone = assess(&[("taxpayer.age", "30"), ("t4.employment_income", "40000")]);
    assert_eq!(gone.get("fed.45300").unwrap(), d("0.00"));
}

#[test]
fn a_dependant_moves_the_workers_benefit_onto_the_family_bands() {
    let single = assess(&[("taxpayer.age", "30"), ("t4.employment_income", "30000")]);
    let family = assess(&[
        ("taxpayer.age", "30"),
        ("t4.employment_income", "30000"),
        ("dependants.count", "1"),
    ]);

    // Same income, but the family maximum is higher and its phase-out starts
    // later — at $30,000 the family amount is not reduced at all.
    assert_eq!(family.get("fed.45300").unwrap(), d("2813.00"));
    assert!(family.get("fed.45300").unwrap() > single.get("fed.45300").unwrap());
}

#[test]
fn the_workers_benefit_needs_age_nineteen_unless_there_is_a_family() {
    let too_young = assess(&[("taxpayer.age", "17"), ("t4.employment_income", "15000")]);
    assert_eq!(too_young.get("fed.45300").unwrap(), d("0.00"));

    // A dependant child qualifies a younger claimant.
    let with_child = assess(&[
        ("taxpayer.age", "17"),
        ("t4.employment_income", "15000"),
        ("dependants.count", "1"),
    ]);
    assert!(with_child.get("fed.45300").unwrap() > Decimal::ZERO);
}

#[test]
fn the_disability_supplement_survives_further_up_the_income_scale() {
    let got = assess(&[
        ("taxpayer.age", "30"),
        ("t4.employment_income", "15000"),
        ("disability.claimed", "1"),
    ]);

    assert_eq!(got.get("fed.cwb_basic").unwrap(), d("1633.00"));
    assert_eq!(got.get("fed.cwb_disability").unwrap(), d("843.00"));
    assert_eq!(got.get("fed.45300").unwrap(), d("2476.00"));

    // At $40,000 the basic amount is gone but the supplement is not: its
    // phase-out only starts at $37,740.
    let higher = assess(&[
        ("taxpayer.age", "30"),
        ("t4.employment_income", "40000"),
        ("disability.claimed", "1"),
    ]);
    assert_eq!(higher.get("fed.cwb_basic").unwrap(), d("0.00"));
    assert!(higher.get("fed.cwb_disability").unwrap() > Decimal::ZERO);
}

#[test]
fn a_full_time_student_can_be_marked_ineligible() {
    let got = assess(&[
        ("taxpayer.age", "22"),
        ("t4.employment_income", "15000"),
        ("cwb.ineligible", "1"),
    ]);

    assert_eq!(got.get("fed.45300").unwrap(), d("0.00"));
}

// -- caregiver amount for an adult dependant ------------------------------

#[test]
fn an_infirm_adult_dependant_earns_the_caregiver_amount() {
    let got = assess(&[
        ("t4.employment_income", "60000"),
        ("dependants.infirm_adult_claimed", "1"),
    ]);

    assert_eq!(got.get("fed.30450").unwrap(), d("8601.00"));
    assert_eq!(got.get("on.58185").unwrap(), d("6008.00"));
}

#[test]
fn the_caregiver_amount_is_reduced_by_the_dependants_own_income() {
    let got = assess(&[
        ("t4.employment_income", "60000"),
        ("dependants.infirm_adult_claimed", "1"),
        ("dependants.infirm_adult_net_income", "25000"),
    ]);

    // 8,601 less the 4,803 of income above the $20,197 threshold.
    assert_eq!(got.get("fed.30450").unwrap(), d("3798.00"));
}

// -- review rules ---------------------------------------------------------

fn fired(got: &Assessment) -> Vec<&str> {
    got.diagnostics.iter().map(|d| d.id.as_str()).collect()
}

#[test]
fn a_clean_return_raises_nothing_beyond_the_expected() {
    let got = assess(&[
        ("t4.employment_income", "85000"),
        ("t4.cpp_contributions", "4034.10"),
        ("t4.cpp2_contributions", "396.00"),
        ("t4.ei_premiums", "1077.48"),
        ("t4.income_tax_deducted", "16000"),
        ("rrsp.deduction_claimed", "5000"),
    ]);

    // The health premium notice is expected on any return above $20,000 of
    // taxable income; nothing else should fire.
    assert_eq!(fired(&got), vec!["on.health_premium_charged"]);
    assert!(!got.has_errors());
}

#[test]
fn contributions_larger_than_the_income_they_came_from_are_an_error() {
    let got = assess(&[
        ("t4.employment_income", "5000"),
        ("t4.cpp_contributions", "40000"),
    ]);

    assert!(fired(&got).contains(&"cpp.exceeds_employment_income"));
    assert!(got.has_errors());
    // An error must stop the return being filed, independently of the
    // unverified-parameter gate.
    assert!(!got.is_filable());
}

#[test]
fn an_rrsp_deduction_larger_than_total_income_is_an_error() {
    let got = assess(&[
        ("t4.employment_income", "40000"),
        ("t4.cpp_contributions", "2200"),
        ("t4.ei_premiums", "656"),
        ("rrsp.deduction_claimed", "50000"),
    ]);

    assert!(fired(&got).contains(&"rrsp.exceeds_total_income"));
    assert!(got.has_errors());
}

#[test]
fn over_the_annual_maximum_is_a_warning_not_an_error() {
    // Two employers legitimately push contributions over the single-employer
    // maximum, and the excess is recovered on the return. Blocking a correct
    // return would be worse than nagging about a suspicious one.
    let got = assess(&[
        ("t4.employment_income", "120000"),
        ("t4.cpp_contributions", "5200"),
        ("t4.ei_premiums", "1400"),
    ]);

    let ids = fired(&got);
    assert!(ids.contains(&"cpp.above_annual_maximum"));
    assert!(ids.contains(&"ei.above_annual_maximum"));
    assert!(!got.has_errors(), "a plausible return was blocked");
}

#[test]
fn missing_payroll_boxes_are_flagged() {
    let got = assess(&[("t4.employment_income", "60000")]);
    let ids = fired(&got);

    assert!(ids.contains(&"cpp.missing"));
    assert!(ids.contains(&"ei.missing"));
}

#[test]
fn an_rrsp_claim_beyond_this_years_room_is_flagged_but_allowed() {
    // 18% of 60,000 is 10,800; claiming 20,000 is legitimate on carried-forward
    // room, so this must not block.
    let got = assess(&[
        ("t4.employment_income", "60000"),
        ("t4.cpp_contributions", "3356"),
        ("t4.ei_premiums", "984"),
        ("rrsp.deduction_claimed", "20000"),
    ]);

    assert!(fired(&got).contains(&"rrsp.above_room_this_income_creates"));
    assert!(!got.has_errors());
}

#[test]
fn an_empty_return_is_noted_without_being_treated_as_broken() {
    let got = assess(&[]);

    assert!(fired(&got).contains(&"return.empty"));
    assert!(!got.has_errors());
}

#[test]
fn diagnostics_are_ordered_worst_first() {
    let got = assess(&[
        ("t4.employment_income", "5000"),
        ("t4.cpp_contributions", "40000"),
    ]);

    let severities: Vec<_> = got.diagnostics.iter().map(|d| d.severity).collect();
    let mut sorted = severities.clone();
    sorted.sort();

    assert_eq!(severities, sorted, "diagnostics were not worst-first");
}

/// The shipped 2025 pack is seeded from secondary sources. Until every value is
/// checked against its citation the engine must refuse to call a return
/// filable. This test is expected to flip once the verification pass is done.
#[test]
fn shipped_2025_data_is_not_yet_cleared_for_filing() {
    let got = assess(&[("t4.employment_income", "60000")]);

    assert!(
        !got.is_filable(),
        "2025 data claims to be filable -- if the verification pass is genuinely \
         complete, update this test; do not delete it"
    );
    assert!(
        got.warnings.iter().all(|w| w.contains("unverified")),
        "unexpected warning kind: {:?}",
        got.warnings
    );
}

// -- Ontario health premium and tax reduction -----------------------------

/// The chart is eleven rows of alternating ramps and plateaus. Modelled as five
/// clamped ramps, the plateaus fall out of the arithmetic — so these cases
/// check the published figures at both kinds of point.
#[test]
fn the_health_premium_follows_the_published_chart() {
    let premium_at = |income: &str| {
        assess(&[("t4.employment_income", income)])
            .get("on.health_premium")
            .unwrap()
    };

    assert_eq!(premium_at("20000"), d("0.00"));
    // Inside the first ramp: 6% of the excess over $20,000.
    assert_eq!(premium_at("22000"), d("120.00"));
    assert_eq!(premium_at("30000"), d("300.00"));
    assert_eq!(premium_at("40000"), d("450.00"));
    assert_eq!(premium_at("50000"), d("600.00"));
    assert_eq!(premium_at("100000"), d("750.00"));
    // The top plateau, past the last ramp.
    assert_eq!(premium_at("250000"), d("900.00"));
}

/// Order matters: the premium is added *after* the reduction rather than being
/// netted against it, so a filer whose Ontario tax has been cut still pays the
/// premium in full on top.
#[test]
fn the_health_premium_is_added_after_the_reduction_not_netted_against_it() {
    let got = assess(&[("t4.employment_income", "22000")]);

    assert_eq!(got.get("on.tax_after_surtax").unwrap(), d("467.28"));
    // Tapered to twice the excess over the $294 basic reduction.
    assert_eq!(got.get("on.tax_after_reduction").unwrap(), d("346.56"));
    // The premium lands on top of that, undiminished by any of it.
    assert_eq!(got.get("on.health_premium").unwrap(), d("120.00"));
    assert_eq!(got.get("on.42800").unwrap(), d("466.56"));
}

/// The reduction is twice the amounts less the tax, which eliminates Ontario
/// tax below the amount and tapers it to nothing at twice the amount — not a
/// flat credit.
#[test]
fn the_tax_reduction_eliminates_ontario_tax_at_low_income() {
    let got = assess(&[("t4.employment_income", "18000")]);

    assert_eq!(got.get("on.tax_after_surtax").unwrap(), d("265.28"));
    // Below the $294 basic reduction, so the whole thing goes.
    assert_eq!(got.get("on.tax_after_reduction").unwrap(), d("0.00"));
    assert_eq!(got.get("on.42800").unwrap(), d("0.00"));
}

#[test]
fn the_tax_reduction_tapers_between_the_amount_and_twice_it() {
    let got = assess(&[("t4.employment_income", "21000")]);

    let tax = got.get("on.tax_after_surtax").unwrap();
    assert_eq!(tax, d("416.78"));

    // Between $294 and $588 the result is exactly twice the excess over $294.
    assert_eq!(got.get("on.tax_reduction").unwrap(), d("171.22"));
    assert_eq!(got.get("on.tax_after_reduction").unwrap(), d("245.56"));
    assert_eq!(got.get("on.tax_after_reduction").unwrap(), (tax - d("294")) * d("2"));
}

#[test]
fn children_enlarge_the_reduction_and_shelter_more_income() {
    let bare = assess(&[("t4.employment_income", "30000")]);
    let with_kids = assess(&[
        ("t4.employment_income", "30000"),
        ("dependants.count_minor", "2"),
    ]);

    // $294 plus $544 for each of two children, doubled, is more than the tax.
    assert_eq!(with_kids.get("on.tax_reduction_amounts").unwrap(), d("1382.00"));
    assert_eq!(with_kids.get("on.tax_after_reduction").unwrap(), d("0.00"));
    assert!(bare.get("on.tax_after_reduction").unwrap() > Decimal::ZERO);

    // The health premium is untouched by the reduction.
    assert_eq!(with_kids.get("on.health_premium").unwrap(), d("300.00"));
    assert_eq!(with_kids.get("on.42800").unwrap(), d("300.00"));
}

#[test]
fn a_high_earner_gets_no_tax_reduction_at_all() {
    let got = assess(&[("t4.employment_income", "80000")]);

    assert_eq!(got.get("on.tax_reduction").unwrap(), d("0.00"));
    assert_eq!(
        got.get("on.tax_after_reduction").unwrap(),
        got.get("on.tax_after_surtax").unwrap()
    );
}
