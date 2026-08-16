//! Properties that must hold for every province and territory.
//!
//! Ontario, Alberta and BC have their own suites. This one runs across all
//! thirteen, so a jurisdiction added later cannot quietly skip the rules —
//! which is the failure mode of per-province test files.

use freshet_engine::{compute, Assessment, Decimal, FactSet, Severity};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

fn assess(year: u16, province: &str, facts: &[(&str, &str)]) -> Assessment {
    let forms = freshet_taxdata::t1_forms(year, province).unwrap();
    let packs = freshet_taxdata::packs(year, province).unwrap();
    let facts: FactSet = facts.iter().map(|(k, v)| (*k, d(v))).collect();

    compute(&forms, &packs, &facts).unwrap()
}

fn all() -> Vec<&'static str> {
    freshet_taxdata::supported_provinces()
}

#[test]
fn every_province_and_territory_is_present() {
    let mut got = all();
    got.sort();

    // Thirteen: ten provinces and three territories.
    assert_eq!(
        got,
        vec!["ab", "bc", "mb", "nb", "nl", "ns", "nt", "nu", "on", "pe", "qc", "sk", "yt"],
    );
}

#[test]
fn every_jurisdiction_composes_and_computes_for_every_year() {
    for &year in freshet_taxdata::SUPPORTED_YEARS {
        for province in all() {
            let got = assess(year, province, &[("t4.employment_income", "70000")]);

            assert!(
                got.get("prov.tax").is_some(),
                "{province}/{year} produced no provincial tax line"
            );
            assert!(
                got.get("summary.balance").is_some(),
                "{province}/{year} produced no balance"
            );
        }
    }
}

/// The single most important property while the data is placeholder: nothing
/// anywhere can be filed.
#[test]
fn nothing_can_be_filed_anywhere_yet() {
    for &year in freshet_taxdata::SUPPORTED_YEARS {
        for province in all() {
            let got = assess(year, province, &[("t4.employment_income", "70000")]);

            // Ontario 2025 is fully verified, so it is the one pack whose data
            // gate legitimately opens. Everything else must be shut.
            if (province, year) == ("on", 2025) {
                assert!(got.is_filable(), "Ontario 2025 lost its verified status");
                continue;
            }

            assert!(
                !got.is_filable(),
                "{province}/{year} claims to be filable on unverified data"
            );
        }
    }
}

/// The federal half of the return cannot depend on where someone lives. This is
/// the assertion that keeps the shared federal form genuinely shared.
#[test]
fn the_federal_return_is_identical_in_every_jurisdiction() {
    let facts = [
        ("t4.employment_income", "95000"),
        ("rrsp.deduction_claimed", "5000"),
        ("donations.claimed", "1000"),
    ];

    let reference = assess(2025, "on", &facts);

    for province in all() {
        let got = assess(2025, province, &facts);

        for line in [
            "fed.15000", "fed.23600", "fed.26000", "fed.30000", "fed.33500", "fed.42000",
        ] {
            assert_eq!(
                got.get(line),
                reference.get(line),
                "{line} differed in {province}"
            );
        }
    }
}

#[test]
fn provincial_tax_is_never_negative() {
    // Credits far exceeding tax must floor at nil rather than become a refund.
    for province in all() {
        let got = assess(
            2025,
            province,
            &[("t4.employment_income", "14000"), ("donations.claimed", "4000")],
        );

        assert!(
            got.get("prov.tax").unwrap() >= d("0.00"),
            "{province} produced negative provincial tax"
        );
    }
}

#[test]
fn a_nil_return_owes_nothing_anywhere() {
    for province in all() {
        let got = assess(2025, province, &[]);

        assert_eq!(got.get("prov.tax"), Some(d("0.00")), "{province}");
        assert_eq!(got.get("summary.balance"), Some(d("0.00")), "{province}");
    }
}

#[test]
fn provincial_tax_rises_with_income_everywhere() {
    for province in all() {
        let low = assess(2025, province, &[("t4.employment_income", "40000")]);
        let high = assess(2025, province, &[("t4.employment_income", "200000")]);

        // Quebec is the exception, and deliberately so: it levies no tax
        // through the federal return at all.
        if province == "qc" {
            assert_eq!(high.get("prov.tax"), Some(d("0.00")));
            continue;
        }

        assert!(
            high.get("prov.tax").unwrap() > low.get("prov.tax").unwrap(),
            "{province} did not tax more income more heavily"
        );
    }
}

/// Whatever is not modelled has to say so. A silent zero on a refundable credit
/// reads to a person as "you get nothing" rather than "we did not compute it".
#[test]
fn unmodelled_credits_are_declared_wherever_they_exist() {
    // Ontario is complete enough to have nothing to declare; every other
    // jurisdiction was built structure-first and does.
    for province in all() {
        if province == "on" {
            continue;
        }

        let got = assess(2025, province, &[("t4.employment_income", "45000")]);
        let declared: Vec<&str> = got
            .diagnostics
            .iter()
            .filter(|x| x.severity == Severity::Warning)
            .map(|x| x.id.as_str())
            .collect();

        assert!(
            !declared.is_empty(),
            "{province} models an incomplete return without declaring a single gap"
        );
    }
}

// -- the two jurisdictions that break the mould ---------------------------

/// Quebec assesses its own income tax on TP1, so the federal return carries no
/// Quebec tax and pays a refundable abatement instead. It is the inverse of
/// every other jurisdiction, and the reason the federal form talks to a
/// province through a contract rather than by name.
#[test]
fn quebec_levies_no_tax_here_and_pays_an_abatement_instead() {
    let got = assess(2025, "qc", &[("t4.employment_income", "90000")]);

    assert_eq!(got.get("prov.tax"), Some(d("0.00")));
    assert!(
        got.get("prov.refundable_credits").unwrap() > d("0.00"),
        "the Quebec abatement did not pay out"
    );

    // The abatement is a share of federal tax, so it must move with it.
    let bigger = assess(2025, "qc", &[("t4.employment_income", "200000")]);
    assert!(
        bigger.get("prov.refundable_credits").unwrap()
            > got.get("prov.refundable_credits").unwrap()
    );
}

#[test]
fn a_quebec_return_says_it_is_only_half_the_job() {
    let got = assess(2025, "qc", &[("t4.employment_income", "90000")]);

    let said = got
        .diagnostics
        .iter()
        .find(|x| x.id == "qc.tp1_not_included")
        .expect("a Quebec return did not mention TP1");

    assert_eq!(said.severity, Severity::Warning);
    assert!(said.help.as_deref().unwrap().contains("Revenu Quebec"));
}

/// Ontario and Prince Edward Island are the only jurisdictions left charging a
/// surtax, and it applies to tax payable rather than to income.
#[test]
fn only_ontario_and_pei_charge_a_surtax() {
    for province in all() {
        let got = assess(2025, province, &[("t4.employment_income", "250000")]);
        let surtax = got.get(&format!("{province}.surtax"));

        match province {
            "on" | "pe" => assert!(
                surtax.unwrap() > d("0.00"),
                "{province} charged no surtax on a large income"
            ),
            _ => assert_eq!(surtax, None, "{province} invented a surtax"),
        }
    }
}

/// Tuition is the rule that cannot be inherited from the federal return:
/// Ontario abolished its credit in 2017, Saskatchewan in 2018 and Alberta in
/// 2020, while everyone else kept one. Assuming either way is wrong somewhere.
#[test]
fn tuition_follows_each_jurisdiction_rather_than_the_federal_rule() {
    const ABOLISHED: [&str; 3] = ["on", "sk", "ab"];

    for province in all() {
        // Quebec has no provincial credits on this return at all.
        if province == "qc" {
            continue;
        }

        let with_fees = assess(
            2025,
            province,
            &[("t4.employment_income", "60000"), ("tuition.fees", "9000")],
        );
        let without = assess(2025, province, &[("t4.employment_income", "60000")]);

        let moved = with_fees.get("prov.tax").unwrap() < without.get("prov.tax").unwrap();

        if ABOLISHED.contains(&province) {
            assert!(!moved, "{province} granted a tuition credit it abolished");
        } else {
            assert!(moved, "{province} denied a tuition credit it offers");
        }
    }
}
