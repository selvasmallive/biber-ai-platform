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
        !freshet_taxdata::is_certified(2025, "on"),
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
#[test]
fn accumulated_amortization_reduces_total_assets() {
    let got = assess(
        Period::calendar(2025),
        &[("gifi.1600", "400000"), ("gifi.1740", "150000")],
    );

    assert_eq!(got.get("gifi.2599").unwrap(), d("250000.00"));
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
