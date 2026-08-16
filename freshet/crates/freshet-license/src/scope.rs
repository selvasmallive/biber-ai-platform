//! What a licence covers, and how much of it.
//!
//! # Why a tax year is not enough
//!
//! A T1 is filed for a calendar year, so "this licence covers 2026" is exactly
//! right. A T2 is filed for a **fiscal period**, which can end on any day —
//! a corporation with a 30 June year-end is filing something a calendar year
//! cannot name. CRA certifies T2 software for periods ending inside a range
//! for the same reason.
//!
//! Modelling both as `Vec<u16>` would mean a T2 licence lying about what it
//! covers, and the lie would surface as a corporation unable to file its own
//! return over a date arithmetic detail.
//!
//! # Why an allowance is not just a number
//!
//! T1 buyers are households: a handful of returns, one purchase. T2 buyers
//! split in two — an owner with exactly one corporation, and an accountant with
//! forty. `max_returns: u32` can express the first but has to fake the second
//! with an absurdly large number, and "you have 4,294,967,295 returns left" is
//! not something to show a professional.

use serde::{Deserialize, Serialize};

// These are serialized with serde's default (externally tagged) representation
// rather than an internal `tag = "..."`. Internal tagging cannot express a
// newtype variant wrapping a sequence, which `TaxYears(Vec<u16>)` is. The
// payload is a signed blob nobody writes by hand, so the compact form costs
// nothing in readability where readability would matter.

/// The filing being attempted.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Filing {
    /// A T1, for a calendar tax year.
    TaxYear(u16),

    /// A T2, for a fiscal period ending on this date.
    PeriodEnding(i64),
}

/// What a licence is good for.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Coverage {
    /// Calendar tax years. Sold and certified per year, so a list rather than
    /// a range — 2025 and 2027 without 2026 is a licence someone could hold.
    TaxYears(Vec<u16>),

    /// Any fiscal period ending within this inclusive range.
    PeriodsEnding { from_unix: i64, to_unix: i64 },
}

impl Coverage {
    pub fn covers(&self, filing: &Filing) -> bool {
        match (self, filing) {
            (Coverage::TaxYears(years), Filing::TaxYear(year)) => years.contains(year),

            (Coverage::PeriodsEnding { from_unix, to_unix }, Filing::PeriodEnding(ends)) => {
                ends >= from_unix && ends <= to_unix
            }

            // A T1 licence asked about a fiscal period, or the reverse. Not a
            // near miss to be forgiven — the licence is for a different kind of
            // return entirely.
            _ => false,
        }
    }

    /// How to name this coverage on screen.
    pub fn describe(&self) -> String {
        match self {
            Coverage::TaxYears(years) => match years.as_slice() {
                [] => "no tax years".into(),
                [one] => format!("the {one} tax year"),
                many => {
                    let listed: Vec<String> = many.iter().map(u16::to_string).collect();
                    let (last, rest) = listed.split_last().expect("non-empty");
                    format!("the {} and {} tax years", rest.join(", "), last)
                }
            },

            Coverage::PeriodsEnding { from_unix, to_unix } => format!(
                "fiscal periods ending between {} and {}",
                ymd(*from_unix),
                ymd(*to_unix)
            ),
        }
    }
}

/// How many returns a licence may file.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Allowance {
    /// A fixed number: a T1 household licence, or a single-return T2.
    Returns(u32),

    /// No limit: the professional tier.
    Unlimited,
}

impl Allowance {
    pub fn permits(&self, already_filed: u32) -> bool {
        match self {
            Allowance::Returns(max) => already_filed < *max,
            Allowance::Unlimited => true,
        }
    }

    pub fn remaining(&self, already_filed: u32) -> Option<u32> {
        match self {
            Allowance::Returns(max) => Some(max.saturating_sub(already_filed)),
            Allowance::Unlimited => None,
        }
    }

    /// Whether the filed-count has to come from somewhere the customer cannot
    /// edit.
    ///
    /// This is the whole reason the distinction is typed. A counted licence is
    /// only meaningful if the count is authoritative, and a count kept on the
    /// customer's own machine is reset by reinstalling. An unlimited licence
    /// has nothing to count, so it needs nothing.
    ///
    /// The place to resolve that is **transmission**, which already requires
    /// the network — you are sending the return to CRA. Checking there adds no
    /// dependency that filing did not already have.
    pub fn needs_authoritative_count(&self) -> bool {
        matches!(self, Allowance::Returns(_))
    }

    pub fn describe(&self) -> String {
        match self {
            Allowance::Returns(1) => "one return".into(),
            Allowance::Returns(n) => format!("up to {n} returns"),
            Allowance::Unlimited => "unlimited returns".into(),
        }
    }
}

/// Civil date from a Unix timestamp, UTC, without pulling in a date library.
///
/// Licence dates are coarse — the boundaries of a fiscal period range — so
/// a day either side of a time zone is immaterial here. It would not be for
/// tax arithmetic, which does not use this.
fn ymd(unix: i64) -> String {
    let days = unix.div_euclid(86_400);

    // Howard Hinnant's civil_from_days, shifted to a March-based year so the
    // leap day lands at the end and needs no special case.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };

    format!("{y:04}-{m:02}-{d:02}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_t1_licence_covers_its_years_and_no_others() {
        let c = Coverage::TaxYears(vec![2025, 2026]);

        assert!(c.covers(&Filing::TaxYear(2025)));
        assert!(c.covers(&Filing::TaxYear(2026)));
        assert!(!c.covers(&Filing::TaxYear(2027)));
    }

    #[test]
    fn a_t1_licence_does_not_cover_a_corporate_period() {
        let c = Coverage::TaxYears(vec![2026]);

        // Not a near miss to be forgiven — a different kind of return.
        assert!(!c.covers(&Filing::PeriodEnding(1_800_000_000)));
    }

    #[test]
    fn a_t2_licence_covers_any_year_end_inside_its_range() {
        let c = Coverage::PeriodsEnding {
            from_unix: 1_767_225_600, // 2026-01-01
            to_unix: 1_798_761_600,   // 2027-01-01
        };

        // A June year-end — the case a calendar year cannot name.
        assert!(c.covers(&Filing::PeriodEnding(1_782_000_000)));

        assert!(c.covers(&Filing::PeriodEnding(1_767_225_600)), "inclusive lower bound");
        assert!(c.covers(&Filing::PeriodEnding(1_798_761_600)), "inclusive upper bound");

        assert!(!c.covers(&Filing::PeriodEnding(1_767_225_599)));
        assert!(!c.covers(&Filing::PeriodEnding(1_798_761_601)));
    }

    #[test]
    fn coverage_reads_as_a_sentence() {
        assert_eq!(
            Coverage::TaxYears(vec![2026]).describe(),
            "the 2026 tax year"
        );
        assert_eq!(
            Coverage::TaxYears(vec![2025, 2026]).describe(),
            "the 2025 and 2026 tax years"
        );
        assert!(Coverage::PeriodsEnding {
            from_unix: 1_767_225_600,
            to_unix: 1_798_761_600,
        }
        .describe()
        .contains("2026-01-01"));
    }

    #[test]
    fn a_counted_allowance_runs_out_and_an_unlimited_one_does_not() {
        let five = Allowance::Returns(5);

        assert!(five.permits(4));
        assert!(!five.permits(5));
        assert_eq!(five.remaining(3), Some(2));
        assert_eq!(five.remaining(99), Some(0), "never underflows");

        assert!(Allowance::Unlimited.permits(1_000_000));
        assert_eq!(Allowance::Unlimited.remaining(1_000_000), None);
    }

    #[test]
    fn only_a_counted_allowance_needs_the_count_to_be_trustworthy() {
        assert!(Allowance::Returns(1).needs_authoritative_count());
        assert!(Allowance::Returns(5).needs_authoritative_count());
        assert!(!Allowance::Unlimited.needs_authoritative_count());
    }

    #[test]
    fn a_professional_is_not_told_a_number() {
        assert_eq!(Allowance::Unlimited.describe(), "unlimited returns");
        assert_eq!(Allowance::Returns(1).describe(), "one return");
        assert_eq!(Allowance::Returns(5).describe(), "up to 5 returns");
    }

    #[test]
    fn dates_convert_correctly_including_leap_days() {
        assert_eq!(ymd(0), "1970-01-01");
        assert_eq!(ymd(1_767_225_600), "2026-01-01");
        assert_eq!(ymd(951_782_400), "2000-02-29", "2000 was a leap year");
        assert_eq!(ymd(1_709_164_800), "2024-02-29");
        assert_eq!(ymd(-86_400), "1969-12-31", "handles dates before the epoch");
    }
}
