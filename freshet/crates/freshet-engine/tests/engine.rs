//! Engine-level tests: arithmetic, guardrails, and failure modes.
//!
//! These use tiny hand-written packs rather than the shipped tax data, so they
//! keep passing when a tax year is re-indexed.

use freshet_engine::{compute, Decimal, EngineError, FactSet, FormSet, PackSet, ParamPack};

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).unwrap()
}

const VERIFIED_FED: &str = r#"{
  "jurisdiction": "fed",
  "tax_year": 2025,
  "scalars": {
    "rate": { "value": "0.10", "source": "test", "verified": true }
  },
  "brackets": {
    "income_tax": {
      "source": "test",
      "verified": true,
      "bands": [
        { "up_to": "10000", "rate": "0.10" },
        { "up_to": "20000", "rate": "0.20" },
        { "up_to": null,    "rate": "0.30" }
      ]
    }
  }
}"#;

const VERIFIED_PROV: &str = r#"{
  "jurisdiction": "on",
  "tax_year": 2025,
  "scalars": { "rate": { "value": "0.05", "source": "test", "verified": true } }
}"#;

fn packs() -> PackSet {
    PackSet {
        federal: ParamPack::from_json(VERIFIED_FED).unwrap(),
        provincial: ParamPack::from_json(VERIFIED_PROV).unwrap(),
    }
}

fn form(lines: &str) -> FormSet {
    FormSet::from_json(&format!(
        r#"{{ "tax_year": 2025, "province": "on", "lines": [{lines}] }}"#
    ))
    .unwrap()
}

fn eval_one(lines: &str, facts: FactSet) -> Decimal {
    let f = form(lines);
    compute(&f, &packs(), &facts).unwrap().get("x").unwrap()
}

#[test]
fn progressive_brackets_tax_each_band_separately() {
    let line = r#"{ "id": "x", "label": "x",
        "expr": { "op": "bracket", "table": "fed:income_tax",
                  "base": { "op": "fact", "key": "income" } } }"#;

    let at = |income: &str| {
        let facts: FactSet = [("income", d(income))].into_iter().collect();
        eval_one(line, facts)
    };

    // Wholly inside the first band.
    assert_eq!(at("5000"), d("500.00"));
    // Exactly at a boundary: the higher rate has not started yet.
    assert_eq!(at("10000"), d("1000.00"));
    // Straddling two bands: 1000 + 20% of 5000.
    assert_eq!(at("15000"), d("2000.00"));
    // Into the open-ended top band: 1000 + 2000 + 30% of 10000.
    assert_eq!(at("30000"), d("6000.00"));
    // Negative income cannot produce negative tax.
    assert_eq!(at("-5000"), Decimal::ZERO);
}

#[test]
fn floor_zero_implements_if_negative_enter_zero() {
    let line = r#"{ "id": "x", "label": "x",
        "expr": { "op": "floor_zero", "of": { "op": "sub",
            "from": { "op": "fact", "key": "a" },
            "minus": { "op": "fact", "key": "b" } } } }"#;

    let facts: FactSet = [("a", d("100")), ("b", d("250"))].into_iter().collect();
    assert_eq!(eval_one(line, facts), Decimal::ZERO);
}

#[test]
fn clamp_bounds_a_phaseout_ratio() {
    let line = r#"{ "id": "x", "label": "x",
        "expr": { "op": "clamp",
            "value": { "op": "fact", "key": "r" },
            "lo": { "op": "const", "value": "0" },
            "hi": { "op": "const", "value": "1" } },
        "rounding": "none" }"#;

    for (input, want) in [("-3", "0"), ("0.25", "0.25"), ("7", "1")] {
        let facts: FactSet = [("r", d(input))].into_iter().collect();
        assert_eq!(eval_one(line, facts), d(want), "clamp({input})");
    }
}

#[test]
fn lines_resolve_out_of_declaration_order() {
    // `first` depends on `second`, which is declared after it.
    let f = form(
        r#"{ "id": "first",  "label": "f", "expr": { "op": "line", "id": "second" } },
           { "id": "second", "label": "s", "expr": { "op": "const", "value": "42" } }"#,
    );

    let got = compute(&f, &packs(), &FactSet::new()).unwrap();
    assert_eq!(got.get("first").unwrap(), d("42.00"));
}

#[test]
fn circular_references_are_an_error_not_a_hang() {
    let f = form(
        r#"{ "id": "a", "label": "a", "expr": { "op": "line", "id": "b" } },
           { "id": "b", "label": "b", "expr": { "op": "line", "id": "a" } }"#,
    );

    match compute(&f, &packs(), &FactSet::new()) {
        Err(EngineError::CircularReference(path)) => {
            assert!(path.contains("a -> b -> a"), "unhelpful cycle path: {path}");
        }
        other => panic!("expected a circular reference error, got {other:?}"),
    }
}

#[test]
fn unknown_lines_and_params_are_rejected() {
    let f = form(r#"{ "id": "x", "label": "x", "expr": { "op": "line", "id": "nope" } }"#);
    assert!(matches!(
        compute(&f, &packs(), &FactSet::new()),
        Err(EngineError::UnknownLine(_))
    ));

    let f = form(r#"{ "id": "x", "label": "x", "expr": { "op": "param", "key": "fed:nope" } }"#);
    assert!(matches!(
        compute(&f, &packs(), &FactSet::new()),
        Err(EngineError::UnknownParam { .. })
    ));
}

#[test]
fn duplicate_line_ids_are_rejected_at_load() {
    let err = FormSet::from_json(
        r#"{ "tax_year": 2025, "province": "on", "lines": [
             { "id": "x", "label": "one", "expr": { "op": "const", "value": "1" } },
             { "id": "x", "label": "two", "expr": { "op": "const", "value": "2" } }
           ] }"#,
    );
    assert!(matches!(err, Err(EngineError::DuplicateLine(_))));
}

#[test]
fn a_fully_verified_pack_produces_a_filable_return() {
    let f = form(r#"{ "id": "x", "label": "x", "expr": { "op": "const", "value": "1" } }"#);
    let got = compute(&f, &packs(), &FactSet::new()).unwrap();

    assert!(got.warnings.is_empty());
    assert!(got.is_filable());
}

#[test]
fn an_unverified_parameter_blocks_filing() {
    let unverified = ParamPack::from_json(
        r#"{ "jurisdiction": "fed", "tax_year": 2025,
             "scalars": { "rate": { "value": "0.10", "source": "guessed" } } }"#,
    )
    .unwrap();

    let packs = PackSet {
        federal: unverified,
        provincial: ParamPack::from_json(VERIFIED_PROV).unwrap(),
    };

    let f = form(r#"{ "id": "x", "label": "x", "expr": { "op": "param", "key": "fed:rate" } }"#);
    let got = compute(&f, &packs, &FactSet::new()).unwrap();

    // The number is still computed -- the taxpayer can model with it --
    // but the return must not be transmittable.
    assert!(!got.is_filable());
    assert_eq!(got.warnings, vec!["unverified tax parameter: fed:scalars.rate"]);
}

#[test]
fn division_by_zero_is_caught() {
    let line = r#"{ "id": "x", "label": "x",
        "expr": { "op": "div",
            "of": { "op": "const", "value": "1" },
            "by": { "op": "const", "value": "0" } } }"#;

    assert!(matches!(
        compute(&form(line), &packs(), &FactSet::new()),
        Err(EngineError::DivideByZero)
    ));
}

#[test]
fn money_rounds_half_away_from_zero_not_to_even() {
    // 0.125 at 2dp must be 0.13, not the banker's-rounding 0.12.
    let line = r#"{ "id": "x", "label": "x",
        "expr": { "op": "mul",
            "of": { "op": "const", "value": "1.25" },
            "by": { "op": "const", "value": "0.1" } } }"#;

    assert_eq!(eval_one(line, FactSet::new()), d("0.13"));
}

// -- fiscal periods for T2 -------------------------------------------------

mod fiscal_period {
    use freshet_engine::params::PeriodPacks;
    use freshet_engine::{Date, Decimal, PackSet, ParamPack, Period};

    fn pack(jurisdiction: &str, rate: &str) -> ParamPack {
        ParamPack::from_json(&format!(
            r#"{{"jurisdiction":"{jurisdiction}","tax_year":2025,
                 "scalars":{{"corp_rate":{{"value":"{rate}","source":"test","verified":true}}}},
                 "brackets":{{}}}}"#
        ))
        .unwrap()
    }

    fn packs(rate: &str) -> PackSet {
        PackSet {
            federal: pack("fed", rate),
            provincial: pack("on", rate),
        }
    }

    fn period(a: (i32, u32, u32), b: (i32, u32, u32)) -> Period {
        Period::new(
            Date::new(a.0, a.1, a.2).unwrap(),
            Date::new(b.0, b.1, b.2).unwrap(),
        )
        .unwrap()
    }

    /// The property that decides how `blended` must be written.
    ///
    /// If the rate did not move, a corporation with an awkward year-end must
    /// get exactly that rate back — not a value that is off in the last cents
    /// because each year's share was rounded before being added.
    #[test]
    fn an_unchanged_rate_blends_back_to_itself_exactly() {
        let p = period((2025, 7, 1), (2026, 6, 30));

        let blended = PeriodPacks::new(p, vec![(2025, packs("0.09")), (2026, packs("0.09"))])
            .unwrap()
            .blended("fed:corp_rate")
            .unwrap();

        assert_eq!(
            blended,
            Decimal::from_str_exact("0.09").unwrap(),
            "an unchanged rate drifted when apportioned"
        );
    }

    /// An unchanged rate must come back exactly, whatever the day split.
    ///
    /// This is the property that matters, and it is asserted directly rather
    /// than by comparing against a rejected implementation. An earlier version
    /// of this test claimed the divide-first ordering drifts; it does not, at
    /// least not anywhere I could find under `rust_decimal`, and asserting a
    /// difference that does not exist would have been worse than asserting
    /// nothing.
    #[test]
    fn an_unchanged_rate_survives_any_day_split_exactly() {
        let rate = Decimal::from_str_exact("0.09").unwrap();

        for (a, b) in [(184i64, 181i64), (1, 364), (364, 1), (200, 165)] {
            let p = Period::calendar(2025);
            let blended = (Decimal::from(a) * rate + Decimal::from(b) * rate)
                / Decimal::from(p.days());

            assert_eq!(blended, rate, "a {a}/{b} split moved an unchanged rate");
        }
    }

    #[test]
    fn a_rate_change_is_apportioned_by_days_not_by_which_year_holds_the_majority() {
        let p = period((2025, 7, 1), (2026, 6, 30));
        assert_eq!(p.days_by_year(), vec![(2025, 184), (2026, 181)]);

        let blended = PeriodPacks::new(p, vec![(2025, packs("0.10")), (2026, packs("0.08"))])
            .unwrap()
            .blended("fed:corp_rate")
            .unwrap();

        // (184 * 0.10 + 181 * 0.08) / 365
        let expected = (Decimal::from(184) * Decimal::from_str_exact("0.10").unwrap()
            + Decimal::from(181) * Decimal::from_str_exact("0.08").unwrap())
            / Decimal::from(365);
        assert_eq!(blended, expected);

        // And it lands between the two rates, nearer the one with more days.
        assert!(blended > Decimal::from_str_exact("0.08").unwrap());
        assert!(blended < Decimal::from_str_exact("0.10").unwrap());
        assert!(blended > Decimal::from_str_exact("0.09").unwrap());
    }

    #[test]
    fn a_period_inside_one_year_uses_that_year_untouched() {
        let p = Period::calendar(2025);
        let pp = PeriodPacks::single(p, packs("0.09")).unwrap();

        assert!(!pp.straddles());
        assert_eq!(
            pp.blended("fed:corp_rate").unwrap(),
            Decimal::from_str_exact("0.09").unwrap()
        );
    }

    /// Amounts the Act fixes at year-end rather than apportioning must resolve
    /// from the closing year, not from a blend.
    #[test]
    fn year_end_parameters_come_from_the_closing_year() {
        let p = period((2025, 7, 1), (2026, 6, 30));
        let pp = PeriodPacks::new(p, vec![(2025, packs("0.10")), (2026, packs("0.08"))]).unwrap();

        assert_eq!(
            pp.at_year_end().scalar("fed:corp_rate").unwrap(),
            Decimal::from_str_exact("0.08").unwrap()
        );
    }

    #[test]
    fn a_straddling_period_missing_a_years_parameters_is_refused() {
        let p = period((2025, 7, 1), (2026, 6, 30));

        let e = PeriodPacks::new(p, vec![(2025, packs("0.09"))]).unwrap_err();
        assert!(e.to_string().contains("every year it covers"), "{e}");
    }

    #[test]
    fn supplying_the_wrong_years_parameters_is_refused() {
        let p = period((2025, 7, 1), (2026, 6, 30));

        let e = PeriodPacks::new(p, vec![(2025, packs("0.09")), (2027, packs("0.08"))])
            .unwrap_err();
        assert!(e.to_string().contains("2026"), "{e}");
    }
}

// -- reporting periods reaching the form ----------------------------------

mod period_facts {
    use freshet_engine::{
        compute, compute_across, compute_for_period, Date, Decimal, FactSet, FormSet, PackSet,
        ParamPack, Period, PeriodPacks,
    };

    /// A one-line form that prorates a limit the way a T2 short year does:
    /// the full amount times days in the period over 365.
    fn prorating_form() -> FormSet {
        FormSet::from_json(
            r#"{
              "tax_year": 2025,
              "province": "on",
              "summary": ["t2.limit"],
              "lines": [{
                "id": "t2.limit",
                "label": "Business limit, prorated for a short year",
                "expr": {"op":"div",
                  "of": {"op":"mul",
                    "of": {"op":"param","key":"fed:business_limit"},
                    "by": {"op":"fact","key":"period.days"}},
                  "by": {"op":"const","value":"365"}}
              }]
            }"#,
        )
        .unwrap()
    }

    fn packs() -> PackSet {
        let pack = |j: &str| {
            ParamPack::from_json(&format!(
                r#"{{"jurisdiction":"{j}","tax_year":2025,
                     "scalars":{{"business_limit":{{"value":"500000","source":"test","verified":true}}}},
                     "brackets":{{}}}}"#
            ))
            .unwrap()
        };
        PackSet { federal: pack("fed"), provincial: pack("on") }
    }

    fn period(a: (i32, u32, u32), b: (i32, u32, u32)) -> Period {
        Period::new(
            Date::new(a.0, a.1, a.2).unwrap(),
            Date::new(b.0, b.1, b.2).unwrap(),
        )
        .unwrap()
    }

    /// The whole point of the exercise: a corporation whose first tax year ran
    /// from September gets a fraction of the business limit, and the fraction
    /// is visible in the form rather than hidden in the engine.
    #[test]
    fn a_short_first_year_prorates_the_limit() {
        let got = compute_for_period(
            &prorating_form(),
            &packs(),
            &FactSet::new(),
            period((2025, 9, 15), (2025, 12, 31)),
        )
        .unwrap();

        // 108 days of 365: 500,000 x 108 / 365 = 147,945.2054...
        //
        // Asserted to the cent because that is what the engine produces — tax
        // lines round, and a test carrying the full quotient would be asserting
        // something no return ever shows.
        assert_eq!(
            got.get("t2.limit").unwrap(),
            Decimal::from_str_exact("147945.21").unwrap()
        );
        assert!(got.get("t2.limit").unwrap() < Decimal::from(500_000));
    }

    #[test]
    fn a_full_year_claims_the_whole_limit() {
        let got = compute_for_period(
            &prorating_form(),
            &packs(),
            &FactSet::new(),
            Period::calendar(2025),
        )
        .unwrap();

        assert_eq!(got.get("t2.limit").unwrap(), Decimal::from(500_000));
    }

    /// A T1 is a calendar-year period, so the plain entry point must agree with
    /// the explicit one. If these ever diverge, every T1 golden vector is
    /// suspect.
    #[test]
    fn the_t1_entry_point_is_the_calendar_year_case() {
        let implied = compute(&prorating_form(), &packs(), &FactSet::new()).unwrap();
        let explicit = compute_for_period(
            &prorating_form(),
            &packs(),
            &FactSet::new(),
            Period::calendar(2025),
        )
        .unwrap();

        assert_eq!(implied.get("t2.limit"), explicit.get("t2.limit"));
    }

    #[test]
    fn a_straddling_period_reports_both_years_and_their_days() {
        let form = FormSet::from_json(
            r#"{
              "tax_year": 2025, "province": "on",
              "summary": [],
              "lines": [
                {"id":"p.days","label":"d","expr":{"op":"fact","key":"period.days"}},
                {"id":"p.first","label":"a","expr":{"op":"fact","key":"period.days_in_first_year"}},
                {"id":"p.second","label":"b","expr":{"op":"fact","key":"period.days_in_second_year"}},
                {"id":"p.straddles","label":"s","expr":{"op":"fact","key":"period.straddles"}}
              ]
            }"#,
        )
        .unwrap();

        // A straddling period needs both years, so it goes through the
        // period-aware entry point rather than the single-year one.
        let p = period((2025, 7, 1), (2026, 6, 30));
        let packs =
            PeriodPacks::new(p, vec![(2025, packs()), (2026, packs())]).unwrap();

        let got = compute_across(&form, &packs, &FactSet::new()).unwrap();

        assert_eq!(got.get("p.days").unwrap(), Decimal::from(365));
        assert_eq!(got.get("p.first").unwrap(), Decimal::from(184));
        assert_eq!(got.get("p.second").unwrap(), Decimal::from(181));
        assert_eq!(got.get("p.straddles").unwrap(), Decimal::ONE);

        // The two year counts account for the period exactly, so a blend
        // written against them cannot lose or invent a day.
        assert_eq!(
            got.get("p.first").unwrap() + got.get("p.second").unwrap(),
            got.get("p.days").unwrap()
        );
    }

    /// The test that proves blending does something, as opposed to being a
    /// no-op that happens not to break anything.
    ///
    /// A form asking for a blended rate against two genuinely different years
    /// must land between them, weighted by days — not on either one.
    #[test]
    fn a_rate_that_moved_between_the_years_is_apportioned_by_days() {
        let form = FormSet::from_json(
            r#"{
              "tax_year": 2026, "province": "on", "summary": [],
              "lines": [
                {"id":"t.blended","label":"b",
                 "expr":{"op":"blended_param","key":"fed:corp_rate"}},
                {"id":"t.year_end","label":"y",
                 "expr":{"op":"param","key":"fed:corp_rate"}}
              ]
            }"#,
        )
        .unwrap();

        // Packs built here rather than reusing this module's helper, which
        // carries one fixed rate: the whole point is two different ones.
        let at = |rate: &str| {
            let one = |j: &str| {
                ParamPack::from_json(&format!(
                    r#"{{"jurisdiction":"{j}","tax_year":2025,
                         "scalars":{{"corp_rate":{{"value":"{rate}","source":"test","verified":true}}}},
                         "brackets":{{}}}}"#
                ))
                .unwrap()
            };
            PackSet { federal: one("fed"), provincial: one("on") }
        };

        // 184 days at 10%, then 181 at 8%.
        let p = period((2025, 7, 1), (2026, 6, 30));
        let pp = PeriodPacks::new(p, vec![(2025, at("0.10")), (2026, at("0.08"))]).unwrap();

        let got = compute_across(&form, &pp, &FactSet::new()).unwrap();
        let blended = got.get("t.blended").unwrap();

        let expected = (Decimal::from(184) * Decimal::from_str_exact("0.10").unwrap()
            + Decimal::from(181) * Decimal::from_str_exact("0.08").unwrap())
            / Decimal::from(365);
        assert_eq!(blended, expected.round_dp(2));

        // It sits between the two rates, nearer the year holding more days.
        assert!(blended > Decimal::from_str_exact("0.08").unwrap());
        assert!(blended < Decimal::from_str_exact("0.10").unwrap());

        // A plain parameter still resolves from the closing year, which is what
        // the Act wants for amounts it fixes at year-end rather than by day.
        assert_eq!(
            got.get("t.year_end").unwrap(),
            Decimal::from_str_exact("0.08").unwrap()
        );
    }

    /// A period inside one year reports nil for the second, so a blend needs no
    /// special case: `(first × a + second × b) ÷ days` returns `a` untouched.
    #[test]
    fn a_single_year_period_reports_nothing_in_the_second_year() {
        let form = FormSet::from_json(
            r#"{
              "tax_year": 2025, "province": "on", "summary": [],
              "lines": [
                {"id":"p.first","label":"a","expr":{"op":"fact","key":"period.days_in_first_year"}},
                {"id":"p.second","label":"b","expr":{"op":"fact","key":"period.days_in_second_year"}}
              ]
            }"#,
        )
        .unwrap();

        let got =
            compute_for_period(&form, &packs(), &FactSet::new(), Period::calendar(2025)).unwrap();

        assert_eq!(got.get("p.first").unwrap(), Decimal::from(365));
        assert_eq!(got.get("p.second").unwrap(), Decimal::ZERO);
    }

    /// The period is derived, not entered. A caller supplying one of these
    /// facts would override the real period with nothing on screen to say so.
    #[test]
    fn a_caller_cannot_forge_the_period() {
        let mut facts = FactSet::new();
        facts.set("period.days", Decimal::from(365));

        let e = compute_for_period(
            &prorating_form(),
            &packs(),
            &facts,
            period((2025, 9, 15), (2025, 12, 31)),
        )
        .unwrap_err();

        assert!(e.to_string().contains("derived from the reporting period"), "{e}");
    }
}
