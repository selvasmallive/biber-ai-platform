//! Fiscal periods, for T2.
//!
//! # Why a tax year is not a year
//!
//! A T1 is filed for a calendar year, so the year *is* the period. A
//! corporation picks its own year-end, and its tax year is whatever falls
//! between one and the next — up to 53 weeks, and frequently not 365 days at
//! all. A company incorporated in September has a first tax year of a few
//! months; one that changes its year-end has a short year on purpose.
//!
//! Two consequences run through the whole T2 return:
//!
//! 1. **Amounts prorate.** The business limit behind the small business
//!    deduction, capital cost allowance and several others are reduced in
//!    proportion to the days in a short tax year.
//! 2. **Rates blend.** A period from 1 July to 30 June sits in two calendar
//!    years. If a rate changed between them, the tax is apportioned by the days
//!    falling either side, not by which year the period "mostly" occupies.
//!
//! Both reduce to counting days correctly, which is why this module is
//! arithmetic and dates with no tax content at all. Getting a day count wrong
//! does not fail loudly — it produces a return that looks entirely plausible
//! and is wrong by a fraction of a percent.
//!
//! # Inclusive counting
//!
//! A period from 1 January to 31 December is **365 days**, not 364. Both
//! endpoints are part of the tax year. Off-by-one here would understate every
//! prorated amount in the return by a day, everywhere, invisibly.

use serde::{Deserialize, Serialize};

use crate::{Decimal, EngineError};

/// The longest tax year a corporation may have: 53 weeks.
///
/// ITA 249(1). A period longer than this is not a short year that needs
/// prorating — it is an error in the dates.
pub const MAX_DAYS: i64 = 371;

/// A civil date. No time, no zone: a fiscal period is a matter of calendar
/// dates, and introducing a clock would only create ways to be off by one.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Date {
    pub year: i32,
    pub month: u32,
    pub day: u32,
}

impl Date {
    pub fn new(year: i32, month: u32, day: u32) -> Result<Self, EngineError> {
        if !(1..=12).contains(&month) {
            return Err(EngineError::BadPeriod(format!("month {month} is not a month")));
        }
        if day < 1 || day > days_in_month(year, month) {
            return Err(EngineError::BadPeriod(format!(
                "{year:04}-{month:02} has no day {day}"
            )));
        }
        Ok(Date { year, month, day })
    }

    /// Days since 1970-01-01, so date arithmetic is integer arithmetic.
    ///
    /// Howard Hinnant's `days_from_civil`, which shifts to a March-based year
    /// so the leap day falls at the end and needs no special case anywhere.
    pub fn to_days(self) -> i64 {
        let y = if self.month <= 2 { self.year - 1 } else { self.year } as i64;
        let era = if y >= 0 { y } else { y - 399 } / 400;
        let yoe = y - era * 400;
        let m = self.month as i64;
        let d = self.day as i64;
        let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + d - 1;
        let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;

        era * 146_097 + doe - 719_468
    }

    pub fn from_days(days: i64) -> Self {
        let z = days + 719_468;
        let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
        let doe = z - era * 146_097;
        let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
        let y = yoe + era * 400;
        let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
        let mp = (5 * doy + 2) / 153;
        let d = doy - (153 * mp + 2) / 5 + 1;
        let m = if mp < 10 { mp + 3 } else { mp - 9 };

        Date {
            year: (if m <= 2 { y + 1 } else { y }) as i32,
            month: m as u32,
            day: d as u32,
        }
    }
}

impl std::fmt::Display for Date {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:04}-{:02}-{:02}", self.year, self.month, self.day)
    }
}

pub fn is_leap(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

pub fn days_in_year(year: i32) -> i64 {
    if is_leap(year) {
        366
    } else {
        365
    }
}

fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if is_leap(year) => 29,
        2 => 28,
        _ => 0,
    }
}

/// A corporation's tax year.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Period {
    pub start: Date,
    pub end: Date,
}

impl Period {
    pub fn new(start: Date, end: Date) -> Result<Self, EngineError> {
        if end < start {
            return Err(EngineError::BadPeriod(format!(
                "a tax year cannot end ({end}) before it starts ({start})"
            )));
        }

        let period = Period { start, end };
        if period.days() > MAX_DAYS {
            return Err(EngineError::BadPeriod(format!(
                "{start} to {end} is {} days; a tax year may not exceed {MAX_DAYS} \
                 (53 weeks), so these dates are wrong rather than a long year",
                period.days()
            )));
        }

        Ok(period)
    }

    /// A calendar year, for the common case.
    pub fn calendar(year: i32) -> Self {
        Period {
            start: Date { year, month: 1, day: 1 },
            end: Date { year, month: 12, day: 31 },
        }
    }

    /// Days in the period, counting both endpoints.
    pub fn days(&self) -> i64 {
        self.end.to_days() - self.start.to_days() + 1
    }

    /// Whether this is a short tax year, meaning prorated amounts apply.
    ///
    /// Measured against the length of the calendar year the period starts in,
    /// so a full 366-day year in a leap year is not treated as long.
    pub fn is_short(&self) -> bool {
        self.days() < days_in_year(self.start.year)
    }

    /// Whether the period crosses a calendar year boundary, which is what makes
    /// rate blending necessary.
    pub fn straddles(&self) -> bool {
        self.start.year != self.end.year
    }

    /// Days of this period falling in each calendar year it touches, in order.
    ///
    /// This is the basis of every rate blend: a period is apportioned by the
    /// days on each side of the boundary, not by which year holds the majority.
    pub fn days_by_year(&self) -> Vec<(i32, i64)> {
        let mut out = Vec::new();

        for year in self.start.year..=self.end.year {
            let year_start = Date { year, month: 1, day: 1 }.to_days();
            let year_end = Date { year, month: 12, day: 31 }.to_days();

            let from = year_start.max(self.start.to_days());
            let to = year_end.min(self.end.to_days());

            if to >= from {
                out.push((year, to - from + 1));
            }
        }

        out
    }

    /// The share of the period falling in each calendar year, summing to one.
    ///
    /// Weights are derived from the day counts rather than computed
    /// independently, so they cannot disagree with them.
    pub fn weights(&self) -> Vec<(i32, Decimal)> {
        let total = Decimal::from(self.days());

        self.days_by_year()
            .into_iter()
            .map(|(year, days)| (year, Decimal::from(days) / total))
            .collect()
    }

    /// The factor a short-year amount is multiplied by.
    ///
    /// `denominator` is supplied rather than assumed: the Act says 365 for the
    /// business limit even in a leap year, and reading 366 off the calendar
    /// would quietly under-claim. Making the caller state it keeps that choice
    /// visible in the form definition instead of buried here.
    pub fn proration(&self, denominator: i64) -> Decimal {
        Decimal::from(self.days()) / Decimal::from(denominator)
    }
}

impl std::fmt::Display for Period {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} to {}", self.start, self.end)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn date(y: i32, m: u32, d: u32) -> Date {
        Date::new(y, m, d).unwrap()
    }

    fn period(a: (i32, u32, u32), b: (i32, u32, u32)) -> Period {
        Period::new(date(a.0, a.1, a.2), date(b.0, b.1, b.2)).unwrap()
    }

    // -- date arithmetic ---------------------------------------------------

    #[test]
    fn dates_round_trip_through_their_day_number() {
        for days in [-100_000i64, -1, 0, 1, 19_000, 20_500, 100_000] {
            let d = Date::from_days(days);
            assert_eq!(d.to_days(), days, "{d} did not round-trip");
        }
    }

    #[test]
    fn the_epoch_and_the_dates_around_it_are_right() {
        assert_eq!(date(1970, 1, 1).to_days(), 0);
        assert_eq!(date(1969, 12, 31).to_days(), -1);
        assert_eq!(date(1970, 1, 2).to_days(), 1);
    }

    #[test]
    fn leap_years_follow_the_full_rule_not_just_divisible_by_four() {
        assert!(is_leap(2024));
        assert!(!is_leap(2025));
        assert!(!is_leap(1900), "1900 is divisible by 100 and not a leap year");
        assert!(is_leap(2000), "2000 is divisible by 400 and is a leap year");
    }

    #[test]
    fn a_date_that_does_not_exist_is_rejected() {
        assert!(Date::new(2025, 2, 29).is_err(), "2025 is not a leap year");
        assert!(Date::new(2024, 2, 29).is_ok(), "2024 is");
        assert!(Date::new(2025, 4, 31).is_err(), "April has 30 days");
        assert!(Date::new(2025, 13, 1).is_err());
        assert!(Date::new(2025, 0, 1).is_err());
        assert!(Date::new(2025, 1, 0).is_err());
    }

    // -- counting ----------------------------------------------------------

    /// The off-by-one that would understate every prorated amount in the
    /// return, by one day, invisibly.
    #[test]
    fn a_calendar_year_is_365_days_because_both_ends_count() {
        assert_eq!(Period::calendar(2025).days(), 365);
        assert_eq!(Period::calendar(2024).days(), 366);
        assert_eq!(period((2025, 1, 1), (2025, 1, 1)).days(), 1, "a one-day period");
    }

    #[test]
    fn a_period_over_a_leap_day_counts_it() {
        assert_eq!(period((2024, 2, 1), (2024, 3, 1)).days(), 30);
        assert_eq!(period((2025, 2, 1), (2025, 3, 1)).days(), 29);
    }

    #[test]
    fn a_full_year_in_a_leap_year_is_not_a_short_year() {
        assert!(!Period::calendar(2024).is_short());
        assert!(!Period::calendar(2025).is_short());

        // A 365-day period starting in a leap year *is* short by a day.
        assert!(period((2024, 1, 1), (2024, 12, 30)).is_short());
    }

    #[test]
    fn a_first_tax_year_after_incorporation_is_short() {
        let first = period((2025, 9, 15), (2025, 12, 31));

        assert_eq!(first.days(), 108);
        assert!(first.is_short());
        assert!(!first.straddles());
    }

    #[test]
    fn a_tax_year_longer_than_53_weeks_is_an_error_not_a_long_year() {
        let start = date(2025, 1, 1);

        assert!(Period::new(start, date(2025, 12, 31)).is_ok());
        assert!(Period::new(start, Date::from_days(start.to_days() + MAX_DAYS - 1)).is_ok());

        let too_long = Period::new(start, Date::from_days(start.to_days() + MAX_DAYS));
        let message = too_long.unwrap_err().to_string();
        assert!(message.contains("53 weeks"), "{message}");
    }

    #[test]
    fn a_period_that_ends_before_it_starts_is_rejected() {
        let e = Period::new(date(2025, 12, 31), date(2025, 1, 1)).unwrap_err();
        assert!(e.to_string().contains("cannot end"), "{e}");
    }

    // -- straddling --------------------------------------------------------

    /// The case the whole module exists for: a June year-end, which no calendar
    /// year names and which apportions by days rather than by majority.
    #[test]
    fn a_june_year_end_splits_by_days_on_each_side_of_the_boundary() {
        let p = period((2025, 7, 1), (2026, 6, 30));

        assert!(p.straddles());
        assert_eq!(p.days(), 365);
        assert!(!p.is_short());

        assert_eq!(p.days_by_year(), vec![(2025, 184), (2026, 181)]);

        // And the two halves account for the whole period, exactly.
        let counted: i64 = p.days_by_year().iter().map(|(_, d)| d).sum();
        assert_eq!(counted, p.days());
    }

    #[test]
    fn a_period_inside_one_year_has_a_single_share_of_one() {
        let w = Period::calendar(2025).weights();

        assert_eq!(w.len(), 1);
        assert_eq!(w[0].0, 2025);
        assert_eq!(w[0].1, Decimal::from(1));
    }

    #[test]
    fn the_shares_of_a_straddling_period_sum_to_exactly_one() {
        // Deliberately awkward: a period whose split does not divide evenly.
        for p in [
            period((2025, 7, 1), (2026, 6, 30)),
            period((2025, 12, 31), (2026, 1, 1)),
            period((2024, 3, 1), (2025, 2, 28)),
        ] {
            let total: Decimal = p.weights().iter().map(|(_, w)| *w).sum();
            assert_eq!(total, Decimal::from(1), "{p} did not apportion cleanly");
        }
    }

    #[test]
    fn a_period_ending_on_the_first_of_january_still_counts_that_day() {
        let p = period((2025, 12, 31), (2026, 1, 1));

        assert_eq!(p.days(), 2);
        assert_eq!(p.days_by_year(), vec![(2025, 1), (2026, 1)]);
    }

    // -- proration ---------------------------------------------------------

    #[test]
    fn a_full_year_prorates_to_one() {
        assert_eq!(Period::calendar(2025).proration(365), Decimal::from(1));
    }

    /// The Act prorates the business limit over 365 even in a leap year, so a
    /// 366-day year claims very slightly more than the full limit. Reading the
    /// denominator off the calendar instead would silently under-claim.
    #[test]
    fn the_denominator_is_the_callers_choice_not_the_calendars() {
        let leap = Period::calendar(2024);

        assert_eq!(leap.days(), 366);
        assert!(leap.proration(365) > Decimal::from(1));
        assert_eq!(leap.proration(366), Decimal::from(1));
    }

    #[test]
    fn a_short_year_claims_its_share_and_no_more() {
        let half = period((2025, 1, 1), (2025, 7, 2));

        assert_eq!(half.days(), 183);
        assert_eq!(half.proration(365), Decimal::from(183) / Decimal::from(365));
        assert!(half.proration(365) < Decimal::from(1));
    }
}
