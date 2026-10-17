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
    // The same call the desktop, the browser and the filing service all make.
    // This used to fetch one year's pack and call `compute_for_period`, which
    // no caller does any more — and which would have quietly skipped the
    // 1 July 2026 rate change that half these tests now turn on.
    let forms = freshet_taxdata::t2_forms("on").unwrap();
    let packs = freshet_taxdata::t2_period_packs(p, "on").unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute_across(&forms, &packs, &facts).unwrap()
}

/// Retained as a name for periods that cross a calendar boundary. It does
/// exactly what `assess` does now, which is the point: there is one path.
fn assess_across(p: Period, facts: &[(&str, &str)]) -> Assessment {
    assess(p, facts)
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
        &[("gifi.8000", "300000"), ("t2.active_business_income", "300000")],
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
        &[("gifi.8000", "600000"), ("t2.active_business_income", "600000")],
    );
    let full = assess(
        Period::calendar(2025),
        &[("gifi.8000", "600000"), ("t2.active_business_income", "600000")],
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
        &[("gifi.8000", "600000"), ("t2.active_business_income", "600000")],
    );
    let full = assess(
        Period::calendar(2025),
        &[("gifi.8000", "600000"), ("t2.active_business_income", "600000")],
    );

    assert!(short.get("t2.430").unwrap() < full.get("t2.430").unwrap());

    // Less deduction means more tax, on identical income.
    assert!(short.get("t2.700").unwrap() > full.get("t2.700").unwrap());
}

#[test]
fn a_short_year_says_that_it_prorated() {
    let short = assess(
        period((2025, 9, 15), (2025, 12, 31)),
        &[("gifi.8000", "300000")],
    );
    let full = assess(Period::calendar(2025), &[("gifi.8000", "300000")]);

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
        &[("gifi.8000", "300000"), ("t2.active_business_income", "300000")],
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
    let facts = [("gifi.8000", "300000"), ("t2.active_business_income", "300000")];

    let straddling = assess_across(period((2025, 7, 1), (2026, 6, 30)), &facts);
    let inside = assess(Period::calendar(2025), &facts);

    // Both periods are 365 days and the federal rates did not move between
    // 2025 and 2026, so every apportioned line must agree exactly.
    assert_eq!(straddling.get("t2.550"), inside.get("t2.550"));
    assert_eq!(straddling.get("t2.430"), inside.get("t2.430"));
    assert_eq!(straddling.get("t2.700"), inside.get("t2.700"));
}

/// A straddling return draws cleanly on both years now that both are cited.
///
/// This test has changed its meaning twice, which is worth recording. It began
/// as "both years are placeholders", became "the 2026 rate holds the gate
/// shut", and is now "neither does" — each time because the data underneath it
/// improved, never because the assertion was wrong. What survives across all
/// three is the property actually being protected: the unverified set is the
/// union over everything the period touches, so it is empty only when every
/// segment is clean.
#[test]
fn a_straddling_return_reports_the_union_of_its_segments() {
    let got = assess_across(
        period((2025, 7, 1), (2026, 6, 30)),
        &[("gifi.8000", "300000")],
    );

    assert!(
        got.warnings.is_empty(),
        "every segment is cited, so nothing should be reported: {:?}",
        got.warnings
    );
    assert!(got.is_filable());
}

// -- the shape of corporate tax -------------------------------------------

/// Active business income within the limit is taxed far more lightly than
/// income above it. Whatever the placeholder rates turn out to be, that
/// ordering is the entire point of the small business deduction.
#[test]
fn income_within_the_limit_is_taxed_more_lightly_than_income_above_it() {
    let small = assess(
        Period::calendar(2025),
        &[("gifi.8000", "400000"), ("t2.active_business_income", "400000")],
    );
    let large = assess(
        Period::calendar(2025),
        &[("gifi.8000", "2000000"), ("t2.active_business_income", "2000000")],
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
        &[("gifi.8000", "300000"), ("t2.active_business_income", "300000")],
    );
    let passive = assess(
        Period::calendar(2025),
        &[("gifi.8000", "300000"), ("t2.active_business_income", "0")],
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
        &[("gifi.8000", "400000"), ("t2.active_business_income", "400000")],
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
        &[("gifi.8000", "50000"), ("t2.deductions", "500000")],
    );

    assert_eq!(got.get("t2.360").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.700").unwrap(), d("0.00"));
    assert_eq!(got.get("prov.tax").unwrap(), d("0.00"));
}

// -- and the thing that must stay true ------------------------------------

/// Computing a year is not permission to transmit it.
///
/// Every parameter behind a 2025 Ontario corporate return has now been read
/// from the Act or the T2 guide, so the engine no longer objects to it — which
/// is the point of the provenance gate, and also the moment it stops being the
/// thing that protects a customer. Nothing is certified, and certification is
/// a separate gate that this test exists to keep separate.
#[test]
fn a_fully_verified_return_is_still_not_certified() {
    let got = assess(Period::calendar(2025), &[("gifi.8000", "300000")]);

    assert!(
        got.warnings.is_empty(),
        "2025 is fully cited and should raise nothing: {:?}",
        got.warnings
    );
    assert!(got.is_filable(), "the data gate should be open for 2025");

    // And the transmission gate is shut regardless.
    assert!(
        !freshet_taxdata::is_certified(
            freshet_taxdata::Filing::T2 {
                year_end: freshet_engine::Date::new(2025, 12, 31).unwrap()
            },
            "on"
        ),
        "nothing may be transmitted until CRA certifies this build"
    );
}

// -- Ontario's rate change on 1 July 2026 ---------------------------------
//
// The lower rate falls from 3.2% to 2.2%, prorated for a taxation year
// straddling the date. A calendar 2026 year end does not straddle a *calendar*
// boundary and is affected all the same, which is why the parameters are cut
// by date rather than by year.

/// A tax year wholly before the change is taxed at the old rate, exactly.
#[test]
fn a_year_ending_before_july_2026_pays_the_old_ontario_rate() {
    let got = assess(
        period((2025, 7, 1), (2026, 6, 30)),
        &[("gifi.8000", "400000"), ("t2.active_business_income", "400000")],
    );

    // 400,000 of active business income, all within the business limit.
    assert_eq!(got.get("prov.tax").unwrap(), d("12800.00"));
}

/// A tax year wholly after it is taxed at the new rate, exactly.
///
/// A half year, because 2027 parameters do not exist yet — which is the right
/// answer for a build targeting 2026 and is why the income here stays under
/// the prorated business limit of 500,000 × 184 ÷ 365.
#[test]
fn a_year_beginning_after_july_2026_pays_the_new_ontario_rate() {
    let got = assess(
        period((2026, 7, 1), (2026, 12, 31)),
        &[("gifi.8000", "200000"), ("t2.active_business_income", "200000")],
    );

    assert_eq!(got.get("prov.tax").unwrap(), d("4400.00"));
}

/// A tax year straddling it pays both, apportioned by day.
///
/// Calendar 2026 is 181 days at 3.2% and 184 at 2.2%, so the rate is
/// (181 × 0.032 + 184 × 0.022) ÷ 365 = 9.84 ÷ 365. On 400,000 that is
/// 10,783.56, and the important part is that it lies strictly between the two
/// flat answers — a build that ignored the change would return one of them.
#[test]
fn a_year_straddling_july_2026_pays_a_blend_of_both_ontario_rates() {
    let got = assess(
        Period::calendar(2026),
        &[("gifi.8000", "400000"), ("t2.active_business_income", "400000")],
    );

    let tax = got.get("prov.tax").unwrap();

    assert!(
        tax > d("8800.00") && tax < d("12800.00"),
        "expected a blend of the two Ontario rates, got {tax}"
    );
    assert_eq!(tax, d("10783.56"));
}

/// The change reaches a corporation that never crosses a calendar year.
///
/// This is the case the old code got wrong. A December 2026 year end sits
/// inside one calendar year, so the "does this period straddle?" test said no
/// and a single pack was used for the whole year.
#[test]
fn the_mid_year_change_reaches_a_period_inside_one_calendar_year() {
    let packs = freshet_taxdata::t2_period_packs(Period::calendar(2026), "on").unwrap();

    assert!(
        packs.straddles(),
        "calendar 2026 crosses Ontario's rate change and must be segmented"
    );
}

/// And 2025, which crosses nothing, is still a single segment.
#[test]
fn a_year_crossing_nothing_is_one_segment() {
    let packs = freshet_taxdata::t2_period_packs(Period::calendar(2025), "on").unwrap();
    assert!(!packs.straddles());
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
    // Revenue 100,000, amortization 60,000, tax provision 40,000 — so the
    // accounts report nil and the tax return does not.
    let got = assess(
        Period::calendar(2025),
        &[("gifi.8000", "100000"), ("gifi.8670", "60000"), ("gifi.9990", "40000")],
    );

    assert_eq!(got.get("gifi.9999").unwrap(), d("0.00"), "the accounts show nil");

    // Neither item is deductible, so both come back.
    assert_eq!(got.get("t2.300").unwrap(), d("100000.00"));
    assert!(got.get("t2.700").unwrap() > d("0.00"));
}

/// Accounting depreciation is added back in full and replaced by capital cost
/// allowance. The two are unrelated figures, and conflating them is the classic
/// way to get net income for tax purposes wrong.
#[test]
fn amortization_is_replaced_by_capital_cost_allowance_not_netted_against_it() {
    // Amortization is an expense in the accounts now, so it reduces the
    // accounting result and is then added back. Capital cost allowance is
    // computed from the pools: 400,000 of class 8 at 20% gives 80,000.
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "200000"),
            ("gifi.8670", "50000"),
            ("cca.class8.opening_ucc", "400000"),
        ],
    );

    assert_eq!(got.get("gifi.9999").unwrap(), d("150000.00"));

    // 150,000 + 50,000 back − 80,000 of allowance. The two depreciation
    // figures stay on separate lines so a reader can see what replaced what.
    assert_eq!(got.get("t2.300").unwrap(), d("120000.00"));
    assert_eq!(got.get("t2.sch1.amortization").unwrap(), d("50000.00"));
    assert_eq!(got.get("t2.sch1.cca").unwrap(), d("80000.00"));
}

/// Half of meals and entertainment is disallowed. The parameter is the
/// deductible share, so the addback is the remainder.
#[test]
fn half_of_meals_and_entertainment_is_added_back() {
    let got = assess(
        Period::calendar(2025),
        &[("gifi.8000", "100000"), ("gifi.8523", "20000")],
    );

    // The accounts expensed all 20,000; half of it is disallowed.
    assert_eq!(got.get("gifi.9999").unwrap(), d("80000.00"));
    assert_eq!(got.get("t2.sch1.meals_addback").unwrap(), d("10000.00"));
    assert_eq!(got.get("t2.300").unwrap(), d("90000.00"));
}

#[test]
fn fines_and_club_dues_are_added_back_in_full() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "100000"),
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
        // Expenses exceeding revenue: a real loss year.
        &[("gifi.8000", "50000"), ("gifi.9270", "200000"), ("gifi.8670", "20000")],
    );

    assert_eq!(got.get("gifi.9999").unwrap(), d("-170000.00"));
    assert_eq!(got.get("t2.300").unwrap(), d("-150000.00"));

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
        &[("gifi.8000", "200000"), ("t2.charitable_donations", "10000")],
    );

    assert_eq!(got.get("t2.sch1.donations_addback").unwrap(), d("10000.00"));
    assert_eq!(got.get("t2.311").unwrap(), d("10000.00"));

    // Net income is higher by the addback; taxable income is back where it
    // would have been had the donation simply been deducted.
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
        &[("gifi.8000", "20000"), ("t2.charitable_donations", "100000")],
    );

    // 20,000 + 100,000 addback = 120,000 of net income, capped at 90,000.
    assert_eq!(got.get("t2.300").unwrap(), d("120000.00"));
    assert_eq!(got.get("t2.311").unwrap(), d("90000.00"));

    assert!(fired(&got).contains(&"t2.sch1.donations_limited"));
}

/// What is not modelled is declared, the same way BC479 is on the T1.
#[test]
fn the_missing_reconciling_items_are_declared() {
    let got = assess(Period::calendar(2025), &[("gifi.8000", "100000")]);

    let warned = got
        .diagnostics
        .iter()
        .find(|x| x.id == "t2.sch1.common_addbacks_only")
        .expect("Schedule 1 did not admit what it leaves out");

    assert_eq!(warned.severity, Severity::Warning);
    assert!(warned.help.as_deref().unwrap().contains("other addition"));
}

// -- capital cost allowance, shared with the T1 ---------------------------

/// The pool arithmetic is the same statute for a corporation as for a sole
/// proprietor, so it lives in one fragment merged into both federal forms.
/// This asserts the T2 actually computes it rather than merely compiling.
#[test]
fn the_corporation_computes_capital_cost_allowance_from_its_own_pools() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "300000"),
            ("gifi.8670", "50000"),
            ("cca.class8.opening_ucc", "100000"),
            ("cca.class50.opening_ucc", "40000"),
        ],
    );

    // Class 8 at 20% and class 50 at 55%, both on the opening balance.
    assert_eq!(got.get("fed.cca_class8").unwrap(), d("20000.00"));
    assert_eq!(got.get("fed.cca_class50").unwrap(), d("22000.00"));
    assert_eq!(got.get("t2.sch1.cca").unwrap(), d("42000.00"));

    // Revenue 300,000 less 50,000 of amortization gives 250,000 in the
    // accounts; the amortization comes back and 42,000 of allowance replaces it.
    assert_eq!(got.get("gifi.9999").unwrap(), d("250000.00"));
    assert_eq!(got.get("t2.300").unwrap(), d("258000.00"));
}

/// The half-year rule applies to a corporation exactly as it does to a sole
/// proprietor: only half of a year's additions enter the pool.
#[test]
fn the_half_year_rule_applies_to_a_corporation_too() {
    let bought = assess(
        Period::calendar(2025),
        &[("gifi.8000", "300000"), ("cca.class8.additions", "100000")],
    );

    // 20% of half of 100,000, not 20% of all of it.
    assert_eq!(bought.get("fed.cca_class8").unwrap(), d("10000.00"));
}

/// Selling an asset for more than its remaining undepreciated cost means past
/// allowance was too generous. The excess comes back into income, and for a
/// corporation that happens on Schedule 1.
#[test]
fn recapture_is_added_back_on_schedule_1() {
    let plain = assess(Period::calendar(2025), &[("gifi.8000", "200000")]);
    let recaptured = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "200000"),
            ("cca.class8.opening_ucc", "10000"),
            ("cca.class8.dispositions", "30000"),
        ],
    );

    assert!(recaptured.get("fed.recapture_total").unwrap() > d("0.00"));
    assert!(
        recaptured.get("t2.300").unwrap() > plain.get("t2.300").unwrap(),
        "recapture did not reach net income for tax purposes"
    );
}

/// Retiring the last asset in a class for less than its remaining cost is the
/// mirror image: past allowance was too stingy, and the shortfall is deducted.
#[test]
fn a_terminal_loss_is_deducted_on_schedule_1() {
    let plain = assess(Period::calendar(2025), &[("gifi.8000", "200000")]);
    let terminal = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "200000"),
            ("cca.class8.opening_ucc", "40000"),
            ("cca.class8.dispositions", "5000"),
            ("cca.class8.all_disposed", "1"),
        ],
    );

    assert!(terminal.get("fed.terminal_loss_total").unwrap() > d("0.00"));
    assert!(
        terminal.get("t2.300").unwrap() < plain.get("t2.300").unwrap(),
        "the terminal loss did not reduce net income for tax purposes"
    );
}

/// The rates come from the federal pack the T1 already verified, layered under
/// the T2 parameters rather than copied into them. A second copy would be free
/// to drift out of step with the first and nothing would notice.
#[test]
fn the_cca_rates_are_the_verified_federal_ones_not_a_second_copy() {
    let t1 = freshet_taxdata::packs(2025, "on").unwrap();
    let t2 = freshet_taxdata::t2_packs(2025, "on").unwrap();

    for key in ["fed:cca_rate_class8", "fed:cca_rate_class50", "fed:cca_first_year_adjustment"] {
        assert_eq!(
            t2.scalar(key).unwrap(),
            t1.scalar(key).unwrap(),
            "{key} differs between the T1 and T2 packs"
        );
    }
}

// -- GIFI: the financial statements the return starts from ----------------

/// The return starts from the accounts rather than from a figure somebody
/// typed, which is the point of filing the statements with it.
#[test]
fn the_return_starts_from_the_income_statement() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("gifi.8300", "200000"),
            ("gifi.9060", "120000"),
            ("gifi.9990", "30000"),
        ],
    );

    assert_eq!(got.get("gifi.8299").unwrap(), d("500000.00"));
    assert_eq!(got.get("gifi.9368").unwrap(), d("320000.00"));
    assert_eq!(got.get("gifi.9970").unwrap(), d("180000.00"));
    assert_eq!(got.get("gifi.9999").unwrap(), d("150000.00"));

    // And Schedule 1 picks that up, adding the tax provision back.
    assert_eq!(got.get("t2.sch1.accounting_income").unwrap(), d("150000.00"));
    assert_eq!(got.get("t2.300").unwrap(), d("180000.00"));
}

/// A balance sheet that does not balance is an error, not a warning. It means
/// something is missing or mistyped, and no amount of tax arithmetic on top of
/// it is worth anything.
#[test]
fn a_balance_sheet_that_does_not_balance_blocks_the_return() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "100000"),
            ("gifi.1000", "250000"),
            ("gifi.2600", "80000"),
            ("gifi.3500", "100000"),
            // Retained earnings short by 70,000.
        ],
    );

    assert_eq!(got.get("gifi.balance_difference").unwrap(), d("70000.00"));

    let problem = got
        .diagnostics
        .iter()
        .find(|x| x.id == "gifi.does_not_balance")
        .expect("an unbalanced balance sheet passed unnoticed");

    assert_eq!(problem.severity, Severity::Error);
    assert!(got.has_errors());
}

#[test]
fn a_balanced_balance_sheet_raises_nothing() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "100000"),
            ("gifi.1000", "250000"),
            ("gifi.2600", "80000"),
            ("gifi.3500", "100000"),
            ("gifi.3600", "70000"),
        ],
    );

    assert_eq!(got.get("gifi.balance_difference").unwrap(), d("0.00"));
    assert!(!fired(&got).contains(&"gifi.does_not_balance"));
    assert!(!got.has_errors());
}

/// Accumulated amortization is entered as a positive figure and subtracted,
/// the way it appears on a balance sheet, rather than expecting a negative.
///
/// This test used to assert that 1740 reduced total assets, because the data
/// had 1740 labelled as accumulated amortization. It is not: CRA 1740 is
/// **machinery and equipment**, an asset, and the contra account is 1741. The
/// old arrangement understated total assets by twice whatever was entered,
/// and then reported a balance-sheet difference the user could not explain.
#[test]
fn accumulated_amortization_reduces_total_assets() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.1600", "400000"),
            ("gifi.1740", "150000"),
            ("gifi.1741", "60000"),
        ],
    );

    // Land 400,000 + machinery 150,000 - accumulated amortization 60,000.
    assert_eq!(got.get("gifi.2599").unwrap(), d("490000.00"));
}

/// An asset code is not a contra account, whatever it was once called here.
#[test]
fn machinery_adds_to_total_assets_rather_than_reducing_them() {
    let bare = assess(Period::calendar(2025), &[("gifi.1600", "400000")]);
    let with_machines = assess(
        Period::calendar(2025),
        &[("gifi.1600", "400000"), ("gifi.1740", "150000")],
    );

    assert!(
        with_machines.get("gifi.2599").unwrap() > bare.get("gifi.2599").unwrap(),
        "machinery must increase total assets"
    );
}

/// The code set is a subset, and says so rather than letting a corporation
/// assume its accounts mapped cleanly.
#[test]
fn the_partial_code_set_is_declared() {
    let got = assess(Period::calendar(2025), &[("gifi.8000", "100000")]);

    let warned = got
        .diagnostics
        .iter()
        .find(|x| x.id == "gifi.subset_only")
        .expect("the return did not admit its code set is partial");

    assert_eq!(warned.severity, Severity::Warning);
}

#[test]
fn a_return_with_no_statements_at_all_says_so() {
    let empty = assess(Period::calendar(2025), &[]);
    let with_figures = assess(Period::calendar(2025), &[("gifi.8000", "100000")]);

    assert!(fired(&empty).contains(&"gifi.no_statements"));
    assert!(!fired(&with_figures).contains(&"gifi.no_statements"));
}

/// Active business income is a fact, and a fact nobody enters is nil.
///
/// Nil means no small business deduction, which for a CCPC at the business
/// limit is the most valuable figure on the return. Nothing errors: the return
/// simply comes out with thousands of dollars more tax than it should, looking
/// complete. The form cannot know whether a corporation is a CCPC, so this is
/// a warning rather than an error — but it must not be silent.
#[test]
fn a_profitable_return_claiming_no_small_business_deduction_says_so() {
    let got = assess(
        period((2026, 1, 1), (2026, 12, 31)),
        &[("gifi.8000", "500000"), ("gifi.9060", "200000")],
    );

    assert!(
        fired(&got).contains(&"t2.no_active_business_income"),
        "a corporation with taxable income and no active business income \
         should be told it is claiming no deduction, got {:?}",
        fired(&got)
    );
}

/// And it stays quiet once the income is entered, or it would be noise on
/// every correctly prepared return.
#[test]
fn entering_active_business_income_silences_the_warning() {
    let got = assess(
        period((2026, 1, 1), (2026, 12, 31)),
        &[
            ("gifi.8000", "500000"),
            ("gifi.9060", "200000"),
            ("t2.active_business_income", "300000"),
        ],
    );

    assert!(!fired(&got).contains(&"t2.no_active_business_income"));
    assert!(got.get("t2.430").unwrap() > d("0"));
}

/// A corporation whose rates were blended is told so.
///
/// The disclosure used to fire on `period.straddles` — crossing a calendar
/// year — because that was once the only reason rates got apportioned. A
/// calendar 2026 Ontario year end crosses no calendar boundary and is blended
/// all the same, and was being told nothing. A notice hung on a proxy for the
/// thing goes quiet the moment the proxy stops holding.
#[test]
fn a_year_blended_inside_one_calendar_year_still_says_so() {
    let got = assess(
        Period::calendar(2026),
        &[("gifi.8000", "400000"), ("t2.active_business_income", "400000")],
    );

    assert!(
        fired(&got).contains(&"t2.rates_apportioned"),
        "the rate change was applied but not disclosed: {:?}",
        fired(&got)
    );
}

/// And a year whose rates did not move is not told they were.
#[test]
fn a_year_with_no_rate_change_is_not_told_anything_was_apportioned() {
    let got = assess(Period::calendar(2025), &[("gifi.8000", "400000")]);

    assert!(!fired(&got).contains(&"t2.rates_apportioned"));
}

/// Crossing a calendar year still triggers it, which is the original case.
#[test]
fn a_year_crossing_a_calendar_boundary_still_says_so() {
    let got = assess_across(
        period((2025, 7, 1), (2026, 6, 30)),
        &[("gifi.8000", "400000")],
    );

    assert!(fired(&got).contains(&"t2.rates_apportioned"));
}

/// Both halves of the income tax provision come back on Schedule 1.
///
/// Income tax is not deductible in computing income for tax purposes, and that
/// is as true of the deferred provision as the current one. Reading only 9990
/// would have let a corporation with a deferred charge understate its income
/// by exactly that amount.
#[test]
fn schedule_one_adds_back_the_deferred_provision_as_well_as_the_current_one() {
    let current_only = assess(
        Period::calendar(2025),
        &[("gifi.8000", "500000"), ("gifi.9990", "40000")],
    );
    let both = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("gifi.9990", "40000"),
            ("gifi.9995", "15000"),
        ],
    );

    // Net income after taxes falls by the deferred charge...
    assert_eq!(
        both.get("gifi.9999").unwrap(),
        current_only.get("gifi.9999").unwrap() - d("15000.00")
    );

    // ...and income for tax purposes does not, because it is added back.
    assert_eq!(
        both.get("t2.300").unwrap(),
        current_only.get("t2.300").unwrap()
    );
}

/// Cost of sales is computed from inventories and purchases, not entered.
///
/// 8300 is opening inventory. It was labelled "Cost of sales" here, which put
/// a whole year of purchases under a code CRA reads as an inventory balance.
#[test]
fn cost_of_sales_is_opening_plus_purchases_less_closing() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("gifi.8300", "80000"),
            ("gifi.8320", "300000"),
            ("gifi.8500", "60000"),
        ],
    );

    assert_eq!(got.get("gifi.8518").unwrap(), d("320000.00"));
    assert_eq!(got.get("gifi.8519").unwrap(), d("180000.00"));
}

/// A certification for one return is not a certification for another, and a
/// T2 certification is a window of year ends rather than a tax year.
///
/// Both halves were wrong at different times today. `is_certified` first took
/// only year and province, so a T2 letter would have opened T1 filing. It then
/// took a return type and a *tax year* — but CRA's Corporation Internet Filing
/// list carries no tax year at all, and what a T2 grant actually covers is a
/// product version good for corporate year ends up to a date. Checked against
/// CRA's published pages on 2026-10-17.
#[test]
fn a_t2_certification_covers_year_ends_not_a_tax_year() {
    use freshet_engine::Date;
    use freshet_taxdata::{Certification, Filing};

    // The spring 2027 round, as vendors are certified for it: year ends
    // through 31 October 2027.
    let granted = Certification::T2 {
        year_ends_through: Date::new(2027, 10, 31).unwrap(),
        province: "on",
    };

    let covers = |filing, province| match (granted, filing) {
        (
            Certification::T2 {
                year_ends_through,
                province: p,
            },
            Filing::T2 { year_end },
        ) => p == province && year_end.to_days() <= year_ends_through.to_days(),
        _ => false,
    };

    // Inside the window, including the last day of it.
    assert!(covers(
        Filing::T2 {
            year_end: Date::new(2027, 6, 30).unwrap()
        },
        "on"
    ));
    assert!(covers(
        Filing::T2 {
            year_end: Date::new(2027, 10, 31).unwrap()
        },
        "on"
    ));

    // One day past it is the next round's business, not ours.
    assert!(!covers(
        Filing::T2 {
            year_end: Date::new(2027, 11, 1).unwrap()
        },
        "on"
    ));

    // Another province, and a personal return, are not covered at all.
    assert!(!covers(
        Filing::T2 {
            year_end: Date::new(2027, 6, 30).unwrap()
        },
        "bc"
    ));
    assert!(!covers(Filing::T1 { year: 2027 }, "on"));
}

/// And nothing is certified today, on any axis.
#[test]
fn the_certified_list_is_empty() {
    assert!(
        freshet_taxdata::CERTIFIED.is_empty(),
        "adding an entry here permits transmission; it must be deliberate"
    );
    assert!(freshet_taxdata::certified_years().is_empty());
}

// -- the business limit reductions, ITA 125(5.1) ---------------------------
//
// Written from the Act and the T2 guide rather than from the form. The two
// operative sentences:
//
//   125(5.1)  the business limit is what the limit otherwise determined
//             "exceeds the greater of" paragraph (a), "A x B / $90,000" where
//             B is "0.225% x (C - $10 million)", and paragraph (b),
//             "D/$500,000 x 5(E - $50,000)".
//
//   T4012 ch 4  "The reduction in a CCPC's business limit is the greater of
//               its taxable capital business limit reduction and its passive
//               income business limit reduction for the year."
//
// Every expected figure below was worked out by hand from those two and the
// arithmetic is shown in the comment, so a test cannot agree with the form
// merely by having been read off it.

/// A corporation with $500,000 of active business income and $12,000,000 of
/// taxable capital employed in Canada last year.
///
/// By hand, from 125(5.1)(a):
///   B = 0.225% x ($12,000,000 - $10,000,000) = 0.00225 x 2,000,000 = 4,500
///   reduction = A x B / 90,000 = 500,000 x 4,500 / 90,000 = 25,000
/// which is the straight line the guide describes:
///   500,000 x (2,000,000 / 40,000,000) = 25,000.
/// Reduced limit = 500,000 - 25,000 = 475,000.
#[test]
fn taxable_capital_over_ten_million_grinds_the_business_limit() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.taxable_capital_employed_in_canada", "12000000"),
        ],
    );

    assert_eq!(got.get("t2.410").unwrap(), d("500000.00"));
    assert_eq!(got.get("t2.taxable_capital_reduction").unwrap(), d("25000.00"));
    assert_eq!(got.get("t2.passive_income_reduction").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.422").unwrap(), d("25000.00"));
    assert_eq!(got.get("t2.business_limit").unwrap(), d("475000.00"));

    // 125(1) at 19% of the least of 500,000, 500,000 and 475,000.
    assert_eq!(got.get("t2.430").unwrap(), d("90250.00"));
}

/// The regression this change fixes, in dollars.
///
/// Until the grinds were modelled the limit stayed at $500,000 and the
/// deduction at 19% x 500,000 = $95,000. The Act gives this corporation
/// 19% x 475,000 = $90,250, so the build was claiming $4,750 of deduction it
/// was not entitled to.
///
/// The cost to the corporation is not the whole $4,750, because the $25,000 of
/// income that falls out of the small business deduction picks up the 13%
/// general rate reduction under 123.4 instead:
///   federal tax before: 190,000 - 50,000 - 95,000 - 0     = 45,000
///   federal tax now:    190,000 - 50,000 - 90,250 - 3,250 = 46,500
/// a difference of 1,500, which is 6% of the 25,000 of limit lost. Both
/// figures are asserted so neither half can drift unnoticed.
#[test]
fn the_taxable_capital_grind_is_worth_1500_of_federal_tax_on_this_return() {
    let facts: &[(&str, &str)] = &[
        ("gifi.8000", "500000"),
        ("t2.active_business_income", "500000"),
    ];

    let unground = assess(Period::calendar(2025), facts);

    let mut with_capital: Vec<(&str, &str)> = facts.to_vec();
    with_capital.push(("t2.taxable_capital_employed_in_canada", "12000000"));
    let ground = assess(Period::calendar(2025), &with_capital);

    // What the build computed for every corporation, whatever its size.
    assert_eq!(unground.get("t2.430").unwrap(), d("95000.00"));
    assert_eq!(unground.get("t2.700").unwrap(), d("45000.00"));

    assert_eq!(ground.get("t2.430").unwrap(), d("90250.00"));
    assert_eq!(ground.get("t2.700").unwrap(), d("46500.00"));

    assert_eq!(
        unground.get("t2.430").unwrap() - ground.get("t2.430").unwrap(),
        d("4750.00"),
        "the deduction overstated by the missing grind"
    );
    assert_eq!(
        ground.get("t2.700").unwrap() - unground.get("t2.700").unwrap(),
        d("1500.00"),
        "the federal tax the grind costs, net of the 123.4 reduction"
    );
}

/// $100,000 of adjusted aggregate investment income last calendar year.
///
/// By hand, from 125(5.1)(b):
///   reduction = D/$500,000 x 5(E - $50,000)
///             = 500,000/500,000 x 5 x (100,000 - 50,000) = 250,000
/// Five dollars of limit per dollar of investment income over the threshold.
/// Reduced limit = 500,000 - 250,000 = 250,000 and the deduction
/// 19% x 250,000 = 47,500 against 95,000 before: half the deduction gone on
/// account of income that has nothing to do with the active business.
#[test]
fn adjusted_aggregate_investment_income_grinds_the_business_limit() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.adjusted_aggregate_investment_income", "100000"),
        ],
    );

    assert_eq!(got.get("t2.taxable_capital_reduction").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.passive_income_reduction").unwrap(), d("250000.00"));
    assert_eq!(got.get("t2.business_limit").unwrap(), d("250000.00"));
    assert_eq!(got.get("t2.430").unwrap(), d("47500.00"));

    // 123.4 picks up what 125 dropped: 13% x 250,000 = 32,500, so
    // 190,000 - 50,000 - 47,500 - 32,500 = 60,000.
    assert_eq!(got.get("t2.638").unwrap(), d("32500.00"));
    assert_eq!(got.get("t2.700").unwrap(), d("60000.00"));
}

/// The two boundaries the guide states in words.
///
/// "The business limit is nil once the combined income from passive
/// investments is more than $150,000": 5 x (150,000 - 50,000) = 500,000, the
/// whole limit. At exactly $50,000 the formula gives 5 x 0 = 0 and the limit
/// is untouched, because the threshold is where the grind starts rather than
/// where it has already taken something.
#[test]
fn the_passive_income_grind_runs_from_fifty_to_a_hundred_and_fifty_thousand() {
    let at_threshold = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.adjusted_aggregate_investment_income", "50000"),
        ],
    );
    assert_eq!(at_threshold.get("t2.business_limit").unwrap(), d("500000.00"));
    assert_eq!(at_threshold.get("t2.430").unwrap(), d("95000.00"));

    let exhausted = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.adjusted_aggregate_investment_income", "150000"),
        ],
    );
    assert_eq!(
        exhausted.get("t2.passive_income_reduction").unwrap(),
        d("500000.00")
    );
    assert_eq!(exhausted.get("t2.business_limit").unwrap(), d("0.00"));
    assert_eq!(exhausted.get("t2.430").unwrap(), d("0.00"));

    // Past it the formula overshoots and "the amount, if any, by which" holds
    // the answer at nil instead of turning the limit negative.
    let beyond = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.adjusted_aggregate_investment_income", "400000"),
        ],
    );
    assert_eq!(
        beyond.get("t2.passive_income_reduction").unwrap(),
        d("1750000.00")
    );
    assert_eq!(beyond.get("t2.business_limit").unwrap(), d("0.00"));
    assert_eq!(beyond.get("t2.430").unwrap(), d("0.00"));
}

/// Investment income under the threshold must not *enlarge* the limit.
///
/// 5 x (10,000 - 50,000) = -200,000, and a reduction of minus 200,000
/// subtracted would hand this corporation a $700,000 business limit. The same
/// trap sits in paragraph (a): 0.225% x (1,000,000 - 10,000,000) is negative.
#[test]
fn a_reduction_below_its_threshold_is_nil_rather_than_negative() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "600000"),
            ("t2.active_business_income", "600000"),
            ("t2.adjusted_aggregate_investment_income", "10000"),
            ("t2.taxable_capital_employed_in_canada", "1000000"),
        ],
    );

    assert_eq!(got.get("t2.taxable_capital_reduction").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.passive_income_reduction").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.422").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.business_limit").unwrap(), d("500000.00"));
    assert_eq!(got.get("t2.430").unwrap(), d("95000.00"));
}

/// $50 million of taxable capital, where the guide says the deduction is gone.
///
/// B = 0.225% x (50,000,000 - 10,000,000) = 0.00225 x 40,000,000 = 90,000, and
/// A x 90,000 / 90,000 = A. That divisor is the whole reason the phase-out ends
/// at $50 million, so this is the figure that would be wrong if the pack still
/// held the pre-2022 $11,250.
#[test]
fn fifty_million_of_taxable_capital_removes_the_deduction_entirely() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.taxable_capital_employed_in_canada", "50000000"),
        ],
    );

    assert_eq!(
        got.get("t2.taxable_capital_reduction").unwrap(),
        d("500000.00")
    );
    assert_eq!(got.get("t2.business_limit").unwrap(), d("0.00"));
    assert_eq!(got.get("t2.430").unwrap(), d("0.00"));

    // Had the pre-2022 $15,000,000 top survived, $12,000,000 of taxable
    // capital would already have cost 0.225% x 2,000,000 / 11,250 = 0.4 of the
    // limit, which is 200,000 and not the 25,000 the current Act gives.
    let twelve = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.taxable_capital_employed_in_canada", "12000000"),
        ],
    );
    assert_eq!(
        twelve.get("t2.taxable_capital_reduction").unwrap(),
        d("25000.00")
    );
}

/// The interaction, which is the part that looks right either way.
///
/// 125(5.1) subtracts "the greater of" paragraphs (a) and (b), and D in
/// paragraph (b) is "the amount determined for A in paragraph (a)" - the limit
/// before either reduction. So both are measured from $500,000 and only the
/// larger is taken.
///
/// By hand, for $12,000,000 of taxable capital and $100,000 of adjusted
/// aggregate investment income:
///   (a) 500,000 x 0.00225 x 2,000,000 / 90,000 =  25,000
///   (b) 500,000/500,000 x 5 x 50,000           = 250,000
///   greater of the two                         = 250,000
///   reduced limit                              = 250,000
/// Applying them one after the other would give 500,000 - 25,000 - 250,000 =
/// 225,000 and a deduction of 42,750 rather than 47,500: $4,750 of deduction
/// denied to a corporation the Act does not deny it to.
#[test]
fn the_greater_of_the_two_reductions_applies_not_both() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.taxable_capital_employed_in_canada", "12000000"),
            ("t2.adjusted_aggregate_investment_income", "100000"),
        ],
    );

    assert_eq!(got.get("t2.taxable_capital_reduction").unwrap(), d("25000.00"));
    assert_eq!(
        got.get("t2.passive_income_reduction").unwrap(),
        d("250000.00")
    );

    assert_eq!(
        got.get("t2.422").unwrap(),
        d("250000.00"),
        "the greater of the two, not the sum of 275,000"
    );
    assert_eq!(
        got.get("t2.business_limit").unwrap(),
        d("250000.00"),
        "sequential application would wrongly give 225,000"
    );
    assert_eq!(got.get("t2.430").unwrap(), d("47500.00"));
}

/// The grind bites on the prorated limit, and the thresholds are not prorated.
///
/// A is "the amount that would, but for this subsection, be the corporation's
/// business limit", which is the limit after 125(5) has prorated it, and the
/// guide tells you to prorate "before you enter it on line 410". Nothing in
/// 125(5.1) prorates the $10 million.
///
/// By hand, for 1 July to 31 December 2025, which is 184 days:
///   line 410  = 500,000 x 184 / 365          = 252,054.79
///   B         = 0.00225 x 2,000,000          =   4,500
///   reduction = 252,054.79 x 4,500 / 90,000  =  12,602.74
///   limit     = 252,054.79 - 12,602.74       = 239,452.05
///   deduction = 19% x 239,452.05             =  45,495.89
/// Prorating the threshold as well, to 10,000,000 x 184/365 = 5,041,095.89,
/// would have made the reduction over three times as large.
#[test]
fn a_short_year_prorates_the_limit_before_the_grind_and_not_the_threshold() {
    let got = assess(
        period((2025, 7, 1), (2025, 12, 31)),
        &[
            ("gifi.8000", "300000"),
            ("t2.active_business_income", "300000"),
            ("t2.taxable_capital_employed_in_canada", "12000000"),
        ],
    );

    assert_eq!(got.get("t2.410").unwrap(), d("252054.79"));
    assert_eq!(
        got.get("t2.taxable_capital_reduction").unwrap(),
        d("12602.74")
    );
    assert_eq!(got.get("t2.business_limit").unwrap(), d("239452.05"));
    assert_eq!(got.get("t2.430").unwrap(), d("45495.89"));
}

/// ITA 125(5)(b) prorates only a year that is "less than 51 weeks".
///
/// 51 weeks is 357 days. A 360-day tax year - a corporation that changed its
/// year end by a few days, say - is not less than 51 weeks and keeps the whole
/// $500,000. The build used to prorate every year that was short of the
/// calendar, which took 500,000 x 5 / 365 = $6,849.32 off this limit. At
/// Ontario rates that is 6% federal plus 8.3% provincial on the lost limit:
/// 410.96 + 568.49 = $979.45 of tax this corporation never owed.
#[test]
fn a_year_of_360_days_is_not_short_enough_to_prorate() {
    let three_sixty = assess(
        period((2025, 1, 6), (2025, 12, 31)),
        &[
            ("gifi.8000", "600000"),
            ("t2.active_business_income", "600000"),
        ],
    );
    let full = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "600000"),
            ("t2.active_business_income", "600000"),
        ],
    );

    assert_eq!(three_sixty.get("t2.410").unwrap(), d("500000.00"));
    assert_eq!(
        three_sixty.get("t2.business_limit").unwrap(),
        full.get("t2.business_limit").unwrap()
    );

    // The limit the old unconditional proration produced, for contrast.
    assert_ne!(three_sixty.get("t2.410").unwrap(), d("493150.68"));

    // And the notice is keyed to the proration, not to the calendar.
    assert!(!fired(&three_sixty).contains(&"t2.short_year_prorated"));
}

/// Exactly 51 weeks is not less than 51 weeks.
///
/// 9 January to 31 December 2025 is 357 days, so the limit is untouched. One
/// day shorter is 356 days, which is less than 51 weeks, and the limit becomes
/// 500,000 x 356 / 365 = 487,671.23. The step is the point: this is a gate in
/// the Act, not a taper, and a build that interpolated across it would be
/// wrong on both sides.
#[test]
fn the_fifty_one_week_gate_is_a_step_at_357_days() {
    let facts: &[(&str, &str)] = &[
        ("gifi.8000", "600000"),
        ("t2.active_business_income", "600000"),
    ];

    let exactly = assess(period((2025, 1, 9), (2025, 12, 31)), facts);
    let one_day_shorter = assess(period((2025, 1, 10), (2025, 12, 31)), facts);

    assert_eq!(exactly.get("t2.410").unwrap(), d("500000.00"));
    assert!(!fired(&exactly).contains(&"t2.short_year_prorated"));

    assert_eq!(one_day_shorter.get("t2.410").unwrap(), d("487671.23"));
    assert!(fired(&one_day_shorter).contains(&"t2.short_year_prorated"));
}

/// A reduction a corporation cannot see is one it cannot check.
#[test]
fn each_grind_says_which_one_it_was() {
    let clean = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
        ],
    );
    assert!(!fired(&clean).contains(&"t2.business_limit_reduced_taxable_capital"));
    assert!(!fired(&clean).contains(&"t2.business_limit_reduced_passive_income"));
    assert!(!fired(&clean).contains(&"t2.business_limit_eliminated"));

    let capital = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.taxable_capital_employed_in_canada", "12000000"),
        ],
    );
    assert!(fired(&capital).contains(&"t2.business_limit_reduced_taxable_capital"));
    assert!(!fired(&capital).contains(&"t2.business_limit_reduced_passive_income"));

    let passive = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.adjusted_aggregate_investment_income", "100000"),
        ],
    );
    assert!(fired(&passive).contains(&"t2.business_limit_reduced_passive_income"));
    assert!(!fired(&passive).contains(&"t2.business_limit_reduced_taxable_capital"));

    // Nil limit is a warning, not a note: a corporation expecting a $95,000
    // deduction and getting none should be told why.
    let gone = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
            ("t2.adjusted_aggregate_investment_income", "200000"),
        ],
    );
    assert_eq!(gone.get("t2.business_limit").unwrap(), d("0.00"));
    assert!(fired(&gone).contains(&"t2.business_limit_eliminated"));
}

/// What the build does not model, said out loud on every return.
///
/// 125(3) shares the limit among associated corporations on Schedule 23,
/// 125(5.1) aggregates taxable capital and investment income across the group,
/// and 125(3.2) lets one corporation assign limit to another. None of the
/// three is computed here, and a corporation with associates would otherwise
/// have no way to know that.
#[test]
fn the_associated_corporation_rules_are_declared_as_unmodelled() {
    let got = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "500000"),
            ("t2.active_business_income", "500000"),
        ],
    );

    assert!(fired(&got).contains(&"t2.sbd.associated_corporations_not_modelled"));
}

/// Ontario did not parallel the passive income reduction, so its limit must
/// not quietly inherit the federal one.
///
/// Ontario's 2018 Fall Economic Statement declined to match the federal
/// measure. on_t2.small_business_income therefore reads line 410 rather than
/// the reduced limit on line 426, and Ontario tax is unchanged by a federal
/// grind: 500,000 at the 3.2% lower rate is 16,000 either way. Whether
/// Ontario parallels the *taxable capital* reduction is unverified for this
/// build, which is why the warning fires rather than nothing happening.
#[test]
fn a_federal_grind_does_not_reduce_the_ontario_business_limit() {
    let facts: &[(&str, &str)] = &[
        ("gifi.8000", "500000"),
        ("t2.active_business_income", "500000"),
    ];

    let unground = assess(Period::calendar(2025), facts);

    let mut ground: Vec<(&str, &str)> = facts.to_vec();
    ground.push(("t2.adjusted_aggregate_investment_income", "100000"));
    let ground = assess(Period::calendar(2025), &ground);

    assert_eq!(unground.get("prov.tax").unwrap(), d("16000.00"));
    assert_eq!(
        ground.get("prov.tax").unwrap(),
        d("16000.00"),
        "Ontario does not parallel the federal passive income reduction"
    );
    assert_eq!(ground.get("on_t2.small_business_income").unwrap(), d("500000.00"));

    // But the federal deduction did fall, and Ontario's divergence is
    // disclosed rather than left for the reader to notice.
    assert_eq!(ground.get("t2.430").unwrap(), d("47500.00"));
    assert!(fired(&ground).contains(&"on_t2.business_limit_not_reduced"));
    assert!(!fired(&unground).contains(&"on_t2.business_limit_not_reduced"));
}

/// The other short-year rule, which this build does not compute.
///
/// Regulation 1100(3): "Where a taxation year is less than 12 months", capital
/// cost allowance "shall not exceed that proportion of the maximum amount
/// otherwise allowable ... that the number of days in the taxation year is of
/// 365". Schedule 8 claims the full-year amount, so a short year over-claims
/// and the tax comes out too low. The desktop used to tell the user capital
/// cost allowance *was* prorated, which was worse than saying nothing.
///
/// A different trigger from the business limit, deliberately: 12 months rather
/// than 51 weeks, so a 360-day year is capped for this and not for that.
#[test]
fn a_short_year_says_capital_cost_allowance_was_not_capped() {
    let short = assess(
        period((2025, 1, 6), (2025, 12, 31)),
        &[
            ("gifi.8000", "600000"),
            ("t2.active_business_income", "600000"),
            ("cca.class8.opening_ucc", "100000"),
        ],
    );

    // 360 days: too long to prorate the business limit, short enough for
    // Regulation 1100(3) to cap the capital cost allowance.
    assert_eq!(short.get("t2.410").unwrap(), d("500000.00"));
    assert!(short.get("t2.sch1.cca").unwrap() > d("0"));
    assert!(fired(&short).contains(&"t2.cca.short_year_cap_not_modelled"));
    assert!(!fired(&short).contains(&"t2.short_year_prorated"));

    let full = assess(
        Period::calendar(2025),
        &[
            ("gifi.8000", "600000"),
            ("t2.active_business_income", "600000"),
            ("cca.class8.opening_ucc", "100000"),
        ],
    );
    assert!(!fired(&full).contains(&"t2.cca.short_year_cap_not_modelled"));

    // And it stays quiet when there is no capital cost allowance to cap.
    let no_cca = assess(
        period((2025, 1, 6), (2025, 12, 31)),
        &[("gifi.8000", "600000"), ("t2.active_business_income", "600000")],
    );
    assert!(!fired(&no_cca).contains(&"t2.cca.short_year_cap_not_modelled"));
}
