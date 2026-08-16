//! Tests for the Auto-fill import path.

use std::collections::BTreeMap;

use freshet_autofill::{
    apply, reconcile, AutofillError, CraAutofill, Disposition, FixtureSource, Proposal, RoomKind,
    SlipSource,
};
use freshet_engine::{compute, Decimal, FactSet, Severity};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn imported() -> freshet_autofill::ImportedData {
    FixtureSource.fetch(2025).unwrap()
}

fn find<'a>(proposals: &'a [Proposal], key: &str) -> &'a Proposal {
    proposals
        .iter()
        .find(|p| p.fact_key == key)
        .unwrap_or_else(|| panic!("no proposal for {key}"))
}

fn current(pairs: &[(&str, &str)]) -> BTreeMap<String, String> {
    pairs
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect()
}

// -- the transport boundary ----------------------------------------------

#[test]
fn the_real_cra_transport_reports_that_it_is_not_available() {
    // It must fail loudly rather than quietly returning nothing, which would
    // look like "CRA has no slips for you".
    let err = CraAutofill { tax_year: 2025 }.fetch(2025).unwrap_err();

    assert!(matches!(err, AutofillError::TransportUnavailable));
    assert!(err.to_string().contains("registration with CRA"));
}

#[test]
fn a_year_the_build_does_not_support_is_refused() {
    assert!(matches!(
        FixtureSource.fetch(2024),
        Err(AutofillError::UnsupportedYear(2024))
    ));
}

// -- aggregation ----------------------------------------------------------

#[test]
fn two_employers_are_summed_into_one_figure() {
    // The case hand entry most often gets wrong.
    let proposals = reconcile(&imported(), &current(&[]));
    let income = find(&proposals, "t4.employment_income");

    assert_eq!(income.total, d("85000.00"));
    assert_eq!(income.from.len(), 2);
    assert_eq!(income.disposition, Disposition::New);

    // The breakdown survives, so the review screen can show its work.
    let issuers: Vec<&str> = income.from.iter().map(|c| c.issuer.as_str()).collect();
    assert!(issuers.contains(&"Northbay Logistics Ltd."));
    assert!(issuers.contains(&"Riverside College"));
}

#[test]
fn every_mapped_box_produces_a_proposal() {
    let proposals = reconcile(&imported(), &current(&[]));

    for key in [
        "t4.employment_income",
        "t4.cpp_contributions",
        "t4.cpp2_contributions",
        "t4.ei_premiums",
        "t4.income_tax_deducted",
        "investment.interest",
    ] {
        find(&proposals, key);
    }

    assert_eq!(find(&proposals, "investment.interest").total, d("842.55"));
}

#[test]
fn a_box_the_build_cannot_place_is_surfaced_rather_than_dropped() {
    // Silently discarding income CRA already knows about is the worst thing an
    // importer can do — CRA will reassess and the user will not know why.
    let data = imported();
    let unmapped = data.unmapped();

    assert_eq!(unmapped.len(), 1);
    assert_eq!(unmapped[0].box_label, "048");
    assert_eq!(unmapped[0].amount, d("3200.00"));

    // And it must not have quietly become a proposal.
    let proposals = reconcile(&data, &current(&[]));
    assert!(proposals.iter().all(|p| p.fact_key != "t4a.048"));
}

// -- reconciliation -------------------------------------------------------

#[test]
fn a_value_that_already_matches_is_not_offered_as_a_change() {
    let proposals = reconcile(&imported(), &current(&[("t4.employment_income", "85000")]));
    let income = find(&proposals, "t4.employment_income");

    assert_eq!(income.disposition, Disposition::Matches);
    assert!(!income.is_change());
}

#[test]
fn a_different_value_is_reported_as_a_conflict_not_overwritten() {
    let proposals = reconcile(&imported(), &current(&[("t4.employment_income", "72500")]));
    let income = find(&proposals, "t4.employment_income");

    assert_eq!(
        income.disposition,
        Disposition::Conflict {
            current: d("72500")
        }
    );
    assert!(income.is_change());
}

#[test]
fn amounts_already_typed_with_formatting_still_compare_equal() {
    let proposals = reconcile(
        &imported(),
        &current(&[("t4.employment_income", "$85,000.00")]),
    );

    assert_eq!(
        find(&proposals, "t4.employment_income").disposition,
        Disposition::Matches
    );
}

#[test]
fn only_accepted_proposals_are_applied() {
    let start = current(&[("rrsp.deduction_claimed", "5000")]);
    let proposals = reconcile(&imported(), &start);

    let next = apply(
        &start,
        &proposals,
        &["t4.employment_income".to_string()],
    );

    assert_eq!(next["t4.employment_income"], "85000.00");
    // Untouched: neither the user's own entry nor the proposals they declined.
    assert_eq!(next["rrsp.deduction_claimed"], "5000");
    assert!(!next.contains_key("investment.interest"));
}

// -- contribution room ----------------------------------------------------

#[test]
fn every_room_figure_carries_its_as_of_date() {
    for room in &imported().rooms {
        assert!(!room.as_of.is_empty(), "{:?} has no as-of date", room.kind);
        assert!(
            room.advisory().contains(&room.as_of),
            "advisory omits the as-of date"
        );
    }
}

#[test]
fn room_for_a_penalised_account_warns_about_over_contributing() {
    let data = imported();
    let tfsa = data
        .rooms
        .iter()
        .find(|r| r.kind == RoomKind::TfsaContributionRoom)
        .unwrap();

    let advisory = tfsa.advisory();
    assert!(advisory.contains("1% per month"));
    assert!(advisory.contains("before contributing"));

    // RRSP is not penalised the same way, so it gets the milder wording.
    let rrsp = data
        .rooms
        .iter()
        .find(|r| r.kind == RoomKind::RrspDeductionLimit)
        .unwrap();
    assert!(!rrsp.advisory().contains("1% per month"));
    assert!(rrsp.advisory().contains("notice of assessment"));
}

// -- end to end -----------------------------------------------------------

/// Import, accept everything, compute — and land on the diagnostic that the
/// two-employer case is supposed to raise.
#[test]
fn an_accepted_import_computes_and_flags_the_over_contribution() {
    let data = imported();
    let proposals = reconcile(&data, &current(&[]));
    let accept: Vec<String> = proposals.iter().map(|p| p.fact_key.clone()).collect();
    let merged = apply(&current(&[]), &proposals, &accept);

    let forms = freshet_taxdata::t1_forms(2025, "on").unwrap();
    let packs = freshet_taxdata::packs(2025, "on").unwrap();
    let facts: FactSet = merged
        .iter()
        .map(|(k, v)| (k.clone(), d(v)))
        .collect();

    let got = compute(&forms, &packs, &facts).unwrap();

    assert_eq!(got.get("fed.10100").unwrap(), d("85000.00"));
    assert_eq!(got.get("fed.12100").unwrap(), d("842.55"));

    // Two employers each withheld up to their own maximum, so the combined
    // figure exceeds it. That is correct data and must be a warning, not a
    // block.
    let ids: Vec<&str> = got.diagnostics.iter().map(|d| d.id.as_str()).collect();
    assert!(ids.contains(&"cpp.above_annual_maximum"), "got {ids:?}");
    assert!(ids.contains(&"ei.above_annual_maximum"), "got {ids:?}");
    assert!(!got.has_errors(), "a real CRA import was blocked: {ids:?}");
    assert!(got
        .diagnostics
        .iter()
        .all(|d| d.severity != Severity::Error));
}
