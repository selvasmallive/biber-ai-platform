//! The T2 core return, structure-first.
//!
//! Every corporate rate here is an unverified placeholder, so these assert
//! shape and arithmetic relationships rather than amounts. Proration is the
//! exception: the *ratio* is checkable without knowing whether the underlying
//! limit is right.

use freshet_engine::{
    compute_across, compute_for_period, Assessment, Date, Decimal, FactSet, Period, Severity,
};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn period(a: (i32, u32, u32), b: (i32, u32, u32)) -> Period {
    Period::new(
        Date::new(a.0, a.1, a.2).unwrap(),
        Date::new(b.0, b.1, b.2).unwrap(),
    )
    .unwrap()
}

fn assess(p: Period, facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t2_forms("on").unwrap();
    // Parameters come from the year the fiscal period ends.
    let packs = freshet_taxdata::t2_packs(p.end.year as u16, "on").unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute_for_period(&forms, &packs, &facts, p).unwrap()
}

/// A period crossing a calendar boundary, computed from both years.
fn assess_across(p: Period, facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t2_forms("on").unwrap();
    let packs = freshet_taxdata::t2_period_packs(p, "on").unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute_across(&forms, &packs, &facts).unwrap()
}

fn fired(got: &Assessment) -> Vec<&str> {
    got.diagnostics.iter().map(|x| x.id.as_str()).collect()
}

/// The question this exercise was meant to answer: does the federal/provincial
/// split built for personal tax carry over to corporate tax, or was it shaped
/// around the T1?
///
/// It carries. The federal T2 knows nothing about Ontario, Ontario supplies
/// `prov.tax`, and `FormSet::compose` joins them exactly as for a T1.
#[test]
fn the_federal_provincial_contract_carries_over_from_t1() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "300000"), ("t2.active_business_income", "300000")],
    );

    assert!(got.get("t2.700").is_some(), "no federal Part I tax line");
    assert_eq!(got.get("prov.tax"), got.get("on_t2.tax"));
    assert_eq!(got.get("prov.refundable_credits"), Some(d("0.00")));

    // The summary adds the two halves without naming Ontario.
    assert_eq!(
        got.get("summary.total_tax").unwrap(),
        got.get("t2.700").unwrap() + got.get("prov.tax").unwrap()
    );
}

// -- proration, which is why T2 needed a period at all --------------------

/// A corporation incorporated in September gets a fraction of the business
/// limit. The ratio is checkable even though the limit is a placeholder.
#[test]
fn a_short_first_year_prorates_the_business_limit() {
    let short = assess(
        period((2025, 9, 15), (2025, 12, 31)),
        &[("t2.accounting_income", "600000"), ("t2.active_business_income", "600000")],
    );
    let full = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "600000"), ("t2.active_business_income", "600000")],
    );

    let short_limit = short.get("t2.business_limit").unwrap();
    let full_limit = full.get("t2.business_limit").unwrap();

    assert!(short_limit < full_limit);

    // 108 days of 365, to the cent the engine rounds to.
    assert_eq!(short_limit, (full_limit * d("108") / d("365")).round_dp(2));
}

/// The deduction follows the limit down, which is the consequence that costs a
/// corporation money.
#[test]
fn a_short_year_reduces_the_small_business_deduction_too() {
    let short = assess(
        period((2025, 9, 15), (2025, 12, 31)),
        &[("t2.accounting_income", "600000"), ("t2.active_business_income", "600000")],
    );
    let full = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "600000"), ("t2.active_business_income", "600000")],
    );

    assert!(short.get("t2.430").unwrap() < full.get("t2.430").unwrap());

    // Less deduction means more tax, on identical income.
    assert!(short.get("t2.700").unwrap() > full.get("t2.700").unwrap());
}

#[test]
fn a_short_year_says_that_it_prorated() {
    let short = assess(
        period((2025, 9, 15), (2025, 12, 31)),
        &[("t2.accounting_income", "300000")],
    );
    let full = assess(Period::calendar(2025), &[("t2.accounting_income", "300000")]);

    assert!(fired(&short).contains(&"t2.short_year_prorated"));
    assert!(!fired(&full).contains(&"t2.short_year_prorated"));
}

/// A single year of parameters cannot express a rate change inside the period,
/// so asking for one is refused rather than answered with the closing year's
/// rate applied to the whole year.
#[test]
fn a_straddling_year_refuses_a_single_years_parameters() {
    let forms = freshet_taxdata::t2_forms("on").unwrap();
    let packs = freshet_taxdata::t2_packs(2026, "on").unwrap();

    let e = compute_for_period(
        &forms,
        &packs,
        &FactSet::new(),
        period((2025, 7, 1), (2026, 6, 30)),
    )
    .unwrap_err();

    assert!(e.to_string().contains("compute_across"), "{e}");
}

#[test]
fn a_straddling_year_computes_from_both_years_and_says_so() {
    let got = assess_across(
        period((2025, 7, 1), (2026, 6, 30)),
        &[("t2.accounting_income", "300000"), ("t2.active_business_income", "300000")],
    );

    assert!(got.get("t2.700").is_some());
    assert!(fired(&got).contains(&"t2.rates_apportioned"));
}

/// The property blending exists for: with the two years' rates identical, a
/// straddling period must produce exactly what a full year inside one of them
/// produces. If apportioning moved the answer here, it would be moving every
/// answer.
#[test]
fn identical_rates_across_the_boundary_change_nothing() {
    let facts = [("t2.accounting_income", "300000"), ("t2.active_business_income", "300000")];

    let straddling = assess_across(period((2025, 7, 1), (2026, 6, 30)), &facts);
    let inside = assess(Period::calendar(2025), &facts);

    // Both periods are 365 days and the packs carry the same placeholder
    // rates, so every apportioned line must agree exactly.
    assert_eq!(straddling.get("t2.550"), inside.get("t2.550"));
    assert_eq!(straddling.get("t2.430"), inside.get("t2.430"));
    assert_eq!(straddling.get("t2.700"), inside.get("t2.700"));
}

/// A straddling return is only as trustworthy as the worse of its two years, so
/// the unverified set is the union rather than one year's.
#[test]
fn a_straddling_return_reports_both_years_as_unverified() {
    let got = assess_across(
        period((2025, 7, 1), (2026, 6, 30)),
        &[("t2.accounting_income", "300000")],
    );

    assert!(!got.is_filable());
    assert!(
        got.warnings.iter().any(|w| w.contains("2025")),
        "the opening year was not reported: {:?}",
        got.warnings
    );
    assert!(
        got.warnings.iter().any(|w| w.contains("2026")),
        "the closing year was not reported: {:?}",
        got.warnings
    );
}

// -- the shape of corporate tax -------------------------------------------

/// Active business income within the limit is taxed far more lightly than
/// income above it. Whatever the placeholder rates turn out to be, that
/// ordering is the entire point of the small business deduction.
#[test]
fn income_within_the_limit_is_taxed_more_lightly_than_income_above_it() {
    let small = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "400000"), ("t2.active_business_income", "400000")],
    );
    let large = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "2000000"), ("t2.active_business_income", "2000000")],
    );

    let rate = |a: &Assessment, income: &str| {
        (a.get("t2.700").unwrap() + a.get("prov.tax").unwrap()) / d(income)
    };

    assert!(
        rate(&small, "400000") < rate(&large, "2000000"),
        "the small business deduction is not reducing the effective rate"
    );
}

/// Investment income does not qualify for the deduction. Two corporations with
/// identical taxable income pay different tax depending on how they earned it —
/// a shape personal tax has no equivalent of.
#[test]
fn investment_income_does_not_earn_the_small_business_deduction() {
    let active = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "300000"), ("t2.active_business_income", "300000")],
    );
    let passive = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "300000"), ("t2.active_business_income", "0")],
    );

    assert_eq!(active.get("t2.360"), passive.get("t2.360"), "same taxable income");
    assert_eq!(passive.get("t2.430").unwrap(), d("0.00"));
    assert!(passive.get("t2.700").unwrap() > active.get("t2.700").unwrap());
}

/// The general reduction applies only to income that did not already get the
/// small business deduction, so the two must not stack.
#[test]
fn the_general_reduction_and_the_small_business_deduction_do_not_stack() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "400000"), ("t2.active_business_income", "400000")],
    );

    // All of it is within the limit, so there is nothing left to reduce.
    assert_eq!(got.get("t2.638").unwrap(), d("0.00"));
    assert!(got.get("t2.430").unwrap() > d("0.00"));
}

#[test]
fn a_nil_return_owes_nothing() {
    let got = assess(Period::calendar(2025), &[]);

    assert_eq!(got.get("t2.700").unwrap(), d("0.00"));
    assert_eq!(got.get("prov.tax").unwrap(), d("0.00"));
    assert_eq!(got.get("summary.balance").unwrap(), d("0.00"));
}

#[test]
fn tax_never_goes_negative() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "50000"), ("t2.deductions", "500000")],
    );

    assert_eq!(got.get("t2.360").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.700").unwrap(), d("0.00"));
    assert_eq!(got.get("prov.tax").unwrap(), d("0.00"));
}

// -- and the thing that must stay true ------------------------------------

#[test]
fn no_t2_return_can_be_filed_on_placeholder_rates() {
    let got = assess(Period::calendar(2025), &[("t2.accounting_income", "300000")]);

    assert!(!got.is_filable(), "T2 claims to be filable on placeholder rates");
    assert!(got.warnings.iter().all(|w| w.contains("unverified")));
}

#[test]
fn only_ontario_has_a_t2_supplement_so_far() {
    assert!(freshet_taxdata::t2_forms("ab").is_err());
    assert!(freshet_taxdata::t2_packs(2025, "bc").is_err());
    assert!(freshet_taxdata::t2_packs(2099, "on").is_err());
}

// -- Schedule 1: reconciling the accounts to taxable income ---------------

/// The reconciliation is the whole point of Schedule 1: accounting profit and
/// income for tax purposes are different numbers, and a corporation that
/// reported nil profit can still owe tax.
#[test]
fn a_corporation_reporting_no_profit_can_still_have_taxable_income() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("t2.accounting_income", "0"),
            ("t2.income_tax_provision", "40000"),
            ("t2.amortization", "60000"),
        ],
    );

    // Neither item is deductible, so both come back.
    assert_eq!(got.get("t2.300").unwrap(), d("100000.00"));
    assert!(got.get("t2.700").unwrap() > d("0.00"));
}

/// Accounting depreciation is added back in full and replaced by capital cost
/// allowance. The two are unrelated figures, and conflating them is the classic
/// way to get net income for tax purposes wrong.
#[test]
fn amortization_is_replaced_by_capital_cost_allowance_not_netted_against_it() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("t2.accounting_income", "200000"),
            ("t2.amortization", "50000"),
            ("t2.capital_cost_allowance", "80000"),
        ],
    );

    // 200,000 + 50,000 − 80,000. Netting the two to a difference of 30,000
    // would give the same answer here only by coincidence of the arithmetic;
    // the lines are separate so a reader can see both.
    assert_eq!(got.get("t2.300").unwrap(), d("170000.00"));
    assert_eq!(got.get("t2.sch1.amortization").unwrap(), d("50000.00"));
    assert_eq!(got.get("t2.sch1.cca").unwrap(), d("80000.00"));
}

/// Half of meals and entertainment is disallowed. The parameter is the
/// deductible share, so the addback is the remainder.
#[test]
fn half_of_meals_and_entertainment_is_added_back() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "100000"), ("t2.meals_and_entertainment", "20000")],
    );

    assert_eq!(got.get("t2.sch1.meals_addback").unwrap(), d("10000.00"));
    assert_eq!(got.get("t2.300").unwrap(), d("110000.00"));
}

#[test]
fn fines_and_club_dues_are_added_back_in_full() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("t2.accounting_income", "100000"),
            ("t2.fines_and_penalties", "5000"),
            ("t2.club_dues", "3000"),
        ],
    );

    assert_eq!(got.get("t2.sch1.non_deductible").unwrap(), d("8000.00"));
    assert_eq!(got.get("t2.300").unwrap(), d("108000.00"));
}

/// A loss is a real outcome. Net income for tax purposes is not floored at
/// nil — flooring it would hide the loss and quietly overstate taxable income
/// in the years either side of it.
#[test]
fn a_loss_year_reports_the_loss_rather_than_flooring_it() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "-150000"), ("t2.amortization", "20000")],
    );

    assert_eq!(got.get("t2.300").unwrap(), d("-130000.00"));

    // Taxable income floors at nil, and no tax is payable.
    assert_eq!(got.get("t2.360").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.700").unwrap(), d("0.00"));
    assert!(fired(&got).contains(&"t2.loss_year"));
}

// -- donations, which move twice ------------------------------------------

/// Donations are added back on Schedule 1 and deducted from taxable income
/// instead. For a corporation well under the limit the two cancel, which is
/// worth asserting because it looks like a no-op and is not.
#[test]
fn donations_are_added_back_then_deducted_again() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "200000"), ("t2.charitable_donations", "10000")],
    );

    assert_eq!(got.get("t2.sch1.donations_addback").unwrap(), d("10000.00"));
    assert_eq!(got.get("t2.311").unwrap(), d("10000.00"));

    // Net income is higher by the addback; taxable income is back where the
    // accounts had it.
    assert_eq!(got.get("t2.300").unwrap(), d("210000.00"));
    assert_eq!(got.get("t2.360").unwrap(), d("200000.00"));
}

/// A corporation that gave away most of what it earned cannot deduct all of it.
/// The excess carries forward, and the return says so rather than silently
/// dropping it.
///
/// The threshold is further out than it looks. Donations are added back before
/// the limit is applied, so net income rises with them: at a 75% cap the
/// deduction only binds once donations exceed *three times* accounting income.
/// An earlier version of this test used 90,000 against 50,000 and nothing was
/// capped, because the limit had risen to 105,000 along with the addback.
#[test]
fn donations_above_the_limit_are_capped_and_reported() {
    let got = assess(
        Period::calendar(2025),
        &[("t2.accounting_income", "20000"), ("t2.charitable_donations", "100000")],
    );

    // 20,000 + 100,000 addback = 120,000 of net income, capped at 90,000.
    assert_eq!(got.get("t2.300").unwrap(), d("120000.00"));
    assert_eq!(got.get("t2.311").unwrap(), d("90000.00"));

    assert!(fired(&got).contains(&"t2.sch1.donations_limited"));
}

/// What is not modelled is declared, the same way BC479 is on the T1.
#[test]
fn the_missing_reconciling_items_are_declared() {
    let got = assess(Period::calendar(2025), &[("t2.accounting_income", "100000")]);

    let warned = got
        .diagnostics
        .iter()
        .find(|x| x.id == "t2.sch1.common_addbacks_only")
        .expect("Schedule 1 did not admit what it leaves out");

    assert_eq!(warned.severity, Severity::Warning);
    assert!(warned.help.as_deref().unwrap().contains("other addition"));
}
