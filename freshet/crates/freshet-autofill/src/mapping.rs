//! CRA slip boxes to engine facts.
//!
//! Kept as one explicit table rather than spread through the importer, so the
//! set of boxes Freshet understands can be reviewed at a glance — and so the
//! gaps are visible. Anything absent here arrives as an unmapped box and is
//! shown to the user rather than dropped.

/// The engine fact a slip box feeds, if Freshet models it yet.
pub fn fact_for(slip_type: &str, box_label: &str) -> Option<&'static str> {
    let slip = slip_type.trim().to_ascii_uppercase();
    let boxed = box_label.trim().to_ascii_uppercase();

    match (slip.as_str(), boxed.as_str()) {
        ("T4", "14") => Some("t4.employment_income"),
        ("T4", "16") => Some("t4.cpp_contributions"),
        ("T4", "16A") => Some("t4.cpp2_contributions"),
        ("T4", "18") => Some("t4.ei_premiums"),
        ("T4", "22") => Some("t4.income_tax_deducted"),

        ("T5", "13") => Some("investment.interest"),

        _ => None,
    }
}

/// Human label for a fact key, for the import review screen.
pub fn describe(fact_key: &str) -> &str {
    match fact_key {
        "t4.employment_income" => "Employment income",
        "t4.cpp_contributions" => "CPP contributions",
        "t4.cpp2_contributions" => "Second CPP contributions",
        "t4.ei_premiums" => "EI premiums",
        "t4.income_tax_deducted" => "Income tax deducted",
        "investment.interest" => "Interest and investment income",
        "rrsp.deduction_claimed" => "RRSP deduction claimed",
        other => other,
    }
}
