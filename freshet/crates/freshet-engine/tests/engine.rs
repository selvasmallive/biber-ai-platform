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
