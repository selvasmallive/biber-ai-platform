//! Tests for coupled returns.
//!
//! The interesting cases are the ones where the rule of thumb is wrong. Those
//! are what justify searching the allocation space instead of hard-coding
//! "medical goes to the lower earner" or "split 50%".

use std::collections::BTreeMap;

use freshet_couple::{evaluate, optimize, Allocation, Claimant, Household, Spouse};
use freshet_engine::{Decimal, FormSet, PackSet};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn forms_and_packs() -> (FormSet, PackSet) {
    (
        freshet_taxdata::t1_forms(2025, "on").unwrap(),
        freshet_taxdata::packs(2025, "on").unwrap(),
    )
}

fn person(label: &str, fields: &[(&str, &str)]) -> Spouse {
    let mut facts = BTreeMap::new();
    for (k, v) in fields {
        facts.insert(k.to_string(), v.to_string());
    }
    Spouse {
        label: label.to_string(),
        facts,
    }
}

fn employed(label: &str, income: &str) -> Spouse {
    person(label, &[("t4.employment_income", income)])
}

fn couple(a: Spouse, b: Spouse, medical: &str, donations: &str) -> Household {
    Household {
        a,
        b,
        medical_expenses: d(medical),
        donations: d(donations),
        childcare: Decimal::ZERO,
        dependants: BTreeMap::new(),
    }
}

/// Add children and child care spending to a household.
fn with_children(mut hh: Household, childcare: &str, kids: &[(&str, &str)]) -> Household {
    hh.childcare = d(childcare);
    hh.dependants = kids
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
    hh
}

/// An allocation with no pension split, for the cases that do not involve one.
fn plain(medical: Claimant, donations: Claimant) -> Allocation {
    Allocation {
        medical,
        donations,
        pension_from: Claimant::A,
        pension_split_rate: Decimal::ZERO,
    }
}

// -- the spousal amount ---------------------------------------------------

#[test]
fn a_low_income_partner_creates_a_spousal_amount() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(employed("Avery", "85000"), employed("Blake", "5000"), "0", "0");

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // 16,129 less the partner's own $5,000 of net income.
    assert_eq!(got.a.get("fed.30300").unwrap(), d("11129.00"));
    // Ontario works differently: an 11,905 base less the same 5,000, then
    // capped at 10,823. The cap does not bite here, so 6,905 survives.
    assert_eq!(got.a.get("on.58120").unwrap(), d("6905.00"));
    assert_eq!(got.b.get("fed.30300").unwrap(), Decimal::ZERO);
}

#[test]
fn two_earners_give_each_other_no_spousal_amount() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(employed("Avery", "85000"), employed("Blake", "85000"), "0", "0");

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    assert_eq!(got.a.get("fed.30300").unwrap(), Decimal::ZERO);
    assert_eq!(got.b.get("fed.30300").unwrap(), Decimal::ZERO);
}

// -- age, pension and disability amounts ----------------------------------

#[test]
fn the_age_amount_is_clawed_back_above_the_threshold() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "60000")]),
        employed("Blake", "0"),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // 9,028 less 15% of the 14,478 above the 45,522 threshold.
    assert_eq!(got.a.get("fed.30100").unwrap(), d("6856.30"));
    // The partner is under 65, so no age amount at all.
    assert_eq!(got.b.get("fed.30100").unwrap(), Decimal::ZERO);
}

#[test]
fn eligible_pension_income_earns_the_pension_amount() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "60000")]),
        employed("Blake", "40000"),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // Capped at $2,000 no matter how large the pension.
    assert_eq!(got.a.get("fed.31400").unwrap(), d("2000.00"));
    // Employment income is not pension income.
    assert_eq!(got.b.get("fed.31400").unwrap(), Decimal::ZERO);
}

#[test]
fn the_disability_amount_is_claimed_when_flagged() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        employed("Avery", "85000"),
        person("Blake", &[("disability.claimed", "1")]),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    assert_eq!(got.b.get("fed.31600").unwrap(), d("10138.00"));
    assert_eq!(got.b.get("on.58440").unwrap(), d("10298.00"));
}

// -- Schedule 2 transfers -------------------------------------------------

#[test]
fn a_partner_with_no_income_transfers_their_age_amount() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        employed("Avery", "85000"),
        person("Blake", &[("taxpayer.age", "68")]),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // Blake has no taxable income, so the whole age amount is unusable and
    // moves across.
    assert_eq!(got.b.get("fed.unused_transferable").unwrap(), d("9028.00"));
    assert_eq!(got.a.get("fed.32600").unwrap(), d("9028.00"));
}

#[test]
fn an_unusable_disability_amount_transfers_too() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        employed("Avery", "85000"),
        person("Blake", &[("disability.claimed", "1")]),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    assert_eq!(got.a.get("fed.32600").unwrap(), d("10138.00"));
}

#[test]
fn a_partner_who_can_use_their_own_amounts_transfers_nothing() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        employed("Avery", "85000"),
        person("Blake", &[("taxpayer.age", "68"), ("pension.own_eligible", "55000")]),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    assert_eq!(got.b.get("fed.unused_transferable").unwrap(), Decimal::ZERO);
    assert_eq!(got.a.get("fed.32600").unwrap(), Decimal::ZERO);
}

#[test]
fn tuition_is_used_then_transferred_then_carried_forward() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        employed("Avery", "85000"),
        person(
            "Blake",
            &[("t4.employment_income", "5000"), ("tuition.fees", "8000")],
        ),
        "0",
        "0",
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // Blake's own credits already cover their $5,000 of income, so none of the
    // tuition is needed on their return.
    assert_eq!(got.b.get("fed.32300").unwrap(), Decimal::ZERO);
    // $5,000 is the federal transfer cap.
    assert_eq!(got.b.get("fed.tuition_transferable").unwrap(), d("5000.00"));
    assert_eq!(got.a.get("fed.32600").unwrap(), d("5000.00"));
    // The rest is not lost — it is reported so a later year can use it.
    assert_eq!(got.b.get("fed.tuition_carryforward").unwrap(), d("3000.00"));
}

// -- pension income splitting --------------------------------------------

#[test]
fn splitting_a_pension_moves_income_and_deducts_it_from_the_sender() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "60000")]),
        person("Blake", &[("taxpayer.age", "68")]),
        "0",
        "0",
    );

    let got = evaluate(
        &forms,
        &packs,
        &hh,
        Allocation {
            pension_split_rate: d("0.50"),
            ..plain(Claimant::A, Claimant::A)
        },
    )
    .unwrap();

    assert_eq!(got.pension_split_amount, d("30000.00"));
    assert_eq!(got.a.get("fed.21000").unwrap(), d("30000.00"));
    assert_eq!(got.b.get("fed.11600").unwrap(), d("30000.00"));
    // The income really moved: both net incomes land on the same figure.
    assert_eq!(got.a.get("fed.23600").unwrap(), d("30000.00"));
    assert_eq!(got.b.get("fed.23600").unwrap(), d("30000.00"));
}

#[test]
fn a_split_can_create_a_second_pension_amount() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "60000")]),
        person("Blake", &[("taxpayer.age", "68")]),
        "0",
        "0",
    );

    let split = evaluate(
        &forms,
        &packs,
        &hh,
        Allocation {
            pension_split_rate: d("0.50"),
            ..plain(Claimant::A, Claimant::A)
        },
    )
    .unwrap();

    // Avery keeps theirs, and Blake gains one on the income received.
    assert_eq!(split.a.get("fed.31400").unwrap(), d("2000.00"));
    assert_eq!(split.b.get("fed.31400").unwrap(), d("2000.00"));
}

#[test]
fn split_income_from_a_younger_spouse_does_not_earn_a_pension_amount() {
    // The receiving spouse only gets a pension income amount on split income if
    // the spouse who sent it was old enough for it to be eligible pension
    // income in the first place.
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "58"), ("pension.own_eligible", "60000")]),
        person("Blake", &[("taxpayer.age", "56")]),
        "0",
        "0",
    );

    let got = evaluate(
        &forms,
        &packs,
        &hh,
        Allocation {
            pension_split_rate: d("0.50"),
            ..plain(Claimant::A, Claimant::A)
        },
    )
    .unwrap();

    assert_eq!(got.b.get("fed.11600").unwrap(), d("30000.00"));
    assert_eq!(got.b.get("fed.31400").unwrap(), Decimal::ZERO);
}

#[test]
fn splitting_saves_a_single_pension_couple_real_money() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "60000")]),
        person("Blake", &[("taxpayer.age", "68")]),
        "0",
        "0",
    );

    let none = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();
    let best = optimize(&forms, &packs, &hh).unwrap();

    assert!(
        best.best.allocation.splits(),
        "the optimizer declined to split"
    );
    assert!(
        best.best.combined_tax < none.combined_tax,
        "splitting did not help: {} vs {}",
        best.best.combined_tax,
        none.combined_tax
    );

    let decision = best
        .decisions
        .iter()
        .find(|d| d.item == "Pension income splitting")
        .unwrap();
    assert!(decision.saved > Decimal::ZERO);
}

#[test]
fn the_best_split_is_not_always_the_maximum() {
    // Avery has $60,000 of pension, Blake $20,000 of employment income. Moving
    // the full 50% would overshoot and leave Blake the higher earner; the
    // optimum equalises them, at roughly a third.
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "60000")]),
        employed("Blake", "20000"),
        "0",
        "0",
    );

    let got = optimize(&forms, &packs, &hh).unwrap();
    let rate = got.best.allocation.pension_split_rate;

    assert!(rate > Decimal::ZERO, "declined to split at all");
    assert!(
        rate < d("0.50"),
        "chose the maximum split when a smaller one is better: {rate}"
    );
}

#[test]
fn the_chosen_split_really_is_the_cheapest_of_those_tried() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(
        person("Avery", &[("taxpayer.age", "70"), ("pension.own_eligible", "48000")]),
        employed("Blake", "26000"),
        "3000",
        "1200",
    );

    let got = optimize(&forms, &packs, &hh).unwrap();

    for step in 0..=10i64 {
        let rate = Decimal::new(step * 5, 2);
        for from in Claimant::BOTH {
            let alt = evaluate(
                &forms,
                &packs,
                &hh,
                Allocation {
                    pension_from: from,
                    pension_split_rate: rate,
                    ..got.best.allocation
                },
            )
            .unwrap();

            assert!(
                got.best.combined_tax <= alt.combined_tax,
                "{from:?} at {rate} beat the chosen allocation"
            );
        }
    }
}

#[test]
fn a_couple_with_no_pension_is_told_nothing_about_splitting() {
    let (forms, packs) = forms_and_packs();
    let got = optimize(
        &forms,
        &packs,
        &couple(employed("Avery", "85000"), employed("Blake", "45000"), "0", "0"),
    )
    .unwrap();

    assert!(!got
        .decisions
        .iter()
        .any(|d| d.item == "Pension income splitting"));
    // Without pension income the search collapses back to four allocations.
    assert_eq!(got.considered, 4);
}

// -- pooling decisions ----------------------------------------------------

#[test]
fn medical_goes_to_the_lower_earner_when_they_have_tax_to_absorb_it() {
    let (forms, packs) = forms_and_packs();
    let got = optimize(
        &forms,
        &packs,
        &couple(employed("Avery", "85000"), employed("Blake", "45000"), "5000", "0"),
    )
    .unwrap();

    assert_eq!(got.best.allocation.medical, Claimant::B);
    let decision = got
        .decisions
        .iter()
        .find(|d| d.item == "Medical expenses")
        .unwrap();
    assert_eq!(decision.chose, "Blake");
    assert!(decision.saved > Decimal::ZERO);
}

#[test]
fn medical_goes_to_the_higher_earner_when_the_lower_one_pays_no_tax() {
    // The rule of thumb inverts: a spouse earning $5,000 owes nothing, so a
    // non-refundable credit on their return is worth exactly zero.
    let (forms, packs) = forms_and_packs();
    let got = optimize(
        &forms,
        &packs,
        &couple(employed("Avery", "85000"), employed("Blake", "5000"), "5000", "0"),
    )
    .unwrap();

    assert_eq!(got.best.allocation.medical, Claimant::A);
}

#[test]
fn donations_land_where_the_ontario_surtax_makes_them_worth_more() {
    let (forms, packs) = forms_and_packs();
    let got = optimize(
        &forms,
        &packs,
        &couple(employed("Avery", "200000"), employed("Blake", "45000"), "0", "3000"),
    )
    .unwrap();

    assert_eq!(got.best.allocation.donations, Claimant::A);
    assert!(got
        .decisions
        .iter()
        .find(|d| d.item == "Donations")
        .unwrap()
        .saved
        > Decimal::ZERO);
}

// -- child care and dependants -------------------------------------------

#[test]
fn child_care_falls_to_the_lower_earner_because_the_rules_say_so() {
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "85000"), employed("Blake", "30000"), "0", "0"),
        "10000",
        &[("dependants.count_under_7", "1")],
    );

    let got = optimize(&forms, &packs, &hh).unwrap();

    assert_eq!(got.best.childcare_claimed_by, Claimant::B);
    // Capped by the one child's $8,000 limit.
    assert_eq!(got.best.b.get("fed.21400").unwrap(), d("8000.00"));
    assert_eq!(got.best.a.get("fed.21400").unwrap(), Decimal::ZERO);
}

#[test]
fn child_care_is_reported_as_a_rule_not_an_optimization() {
    // A deduction is worth more against the higher earner's marginal rate, so a
    // naive optimizer would put it there. The rules do not allow it, and the
    // explanation has to say that rather than claim credit for a choice.
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "150000"), employed("Blake", "40000"), "0", "0"),
        "9000",
        &[("dependants.count_under_7", "1"), ("dependants.count_7_to_16", "1")],
    );

    let got = optimize(&forms, &packs, &hh).unwrap();
    let decision = got.decisions.iter().find(|x| x.item == "Child care").unwrap();

    assert_eq!(got.best.childcare_claimed_by, Claimant::B);
    assert!(decision.mandatory);
    assert_eq!(decision.saved, Decimal::ZERO);
    assert_eq!(decision.chose, "Blake");
}

#[test]
fn each_child_carries_their_own_annual_limit() {
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "120000"), employed("Blake", "90000"), "0", "0"),
        "40000",
        &[
            ("dependants.count_under_7", "2"),
            ("dependants.count_7_to_16", "1"),
        ],
    );

    let got = optimize(&forms, &packs, &hh).unwrap();

    // 8,000 + 8,000 + 5,000, well under two thirds of Blake's income.
    assert_eq!(got.best.b.get("fed.21400").unwrap(), d("21000.00"));
}

#[test]
fn the_disability_limit_applies_at_any_age() {
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "120000"), employed("Blake", "90000"), "0", "0"),
        "40000",
        &[("dependants.count_disabled", "1")],
    );

    let got = optimize(&forms, &packs, &hh).unwrap();
    assert_eq!(got.best.b.get("fed.21400").unwrap(), d("11000.00"));
}

#[test]
fn two_thirds_of_earned_income_caps_the_claim() {
    // The bite that surprises people: the spouse forced to claim is the one
    // with the least income to measure two thirds against.
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "150000"), employed("Blake", "9000"), "0", "0"),
        "10000",
        &[("dependants.count_under_7", "1")],
    );

    let got = optimize(&forms, &packs, &hh).unwrap();

    assert_eq!(got.best.childcare_claimed_by, Claimant::B);
    // Two thirds of $9,000, not the $8,000 child limit and not the $10,000 paid.
    assert_eq!(got.best.b.get("fed.21400").unwrap(), d("6000.00"));
}

#[test]
fn an_infirm_child_earns_the_caregiver_amount_on_both_returns_worth_of_rules() {
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "85000"), employed("Blake", "45000"), "0", "0"),
        "0",
        &[("dependants.count_infirm_minor", "2")],
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // The amount is per infirm child.
    assert_eq!(got.a.get("fed.30500").unwrap(), d("5374.00"));
}

#[test]
fn the_eligible_dependant_amount_is_blocked_by_having_a_spouse() {
    let (forms, packs) = forms_and_packs();
    let hh = with_children(
        couple(employed("Avery", "85000"), employed("Blake", "45000"), "0", "0"),
        "0",
        &[
            ("dependants.eligible_dependant_claimed", "1"),
            ("dependants.eligible_dependant_net_income", "0"),
        ],
    );

    let got = evaluate(&forms, &packs, &hh, plain(Claimant::A, Claimant::A)).unwrap();

    // The spouse amount is claimed instead; the two are mutually exclusive.
    assert_eq!(got.a.get("fed.30400").unwrap(), Decimal::ZERO);
    assert!(got
        .a
        .diagnostics
        .iter()
        .any(|x| x.id == "dependant.claim_ignored_with_spouse"));
}

// -- the optimizer itself -------------------------------------------------

#[test]
fn nothing_is_explained_that_the_couple_does_not_have() {
    let (forms, packs) = forms_and_packs();
    let got = optimize(
        &forms,
        &packs,
        &couple(employed("Avery", "85000"), employed("Blake", "45000"), "0", "0"),
    )
    .unwrap();

    assert!(got.decisions.is_empty());
    assert_eq!(got.saving_vs_worst, Decimal::ZERO);
}

#[test]
fn the_same_household_always_gets_the_same_answer() {
    let (forms, packs) = forms_and_packs();
    let hh = couple(employed("Avery", "95000"), employed("Blake", "95000"), "4000", "1000");

    let first = optimize(&forms, &packs, &hh).unwrap();
    let second = optimize(&forms, &packs, &hh).unwrap();

    assert_eq!(first.best.allocation, second.best.allocation);
    assert_eq!(first.best.combined_tax, second.best.combined_tax);
}

#[test]
fn pooled_amounts_are_claimed_once_not_twice() {
    let (forms, packs) = forms_and_packs();
    let got = optimize(
        &forms,
        &packs,
        &couple(employed("Avery", "85000"), employed("Blake", "45000"), "5000", "3000"),
    )
    .unwrap();

    let claimed = got.best.a.get("fed.33099").unwrap() + got.best.b.get("fed.33099").unwrap();
    assert_eq!(claimed, d("5000.00"), "medical was double-claimed or lost");
}
