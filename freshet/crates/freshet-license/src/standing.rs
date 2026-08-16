//! How a licence is doing, and what to say about it.
//!
//! Expiry is the one licensing mechanism that can hurt someone who paid. Every
//! decision in this module is about making sure it never does that at the worst
//! possible moment.
//!
//! The failure people actually experience with licensed software is this: it
//! works on Tuesday, and on Wednesday a modal says EXPIRED and their deadline
//! is Thursday. Nothing about that is necessary. Four rules prevent it here:
//!
//! 1. **Preparing is never gated.** Expiry touches filing and nothing else. A
//!    return can always be opened, edited, recalculated, printed and exported,
//!    forever, licence or no licence. Holding someone's own tax data hostage
//!    would be indefensible.
//! 2. **Say the date from the first day.** A licence that shows "covers filing
//!    until 30 April 2027" on the day it is installed cannot surprise anyone
//!    eleven months later.
//! 3. **Warn early, and only once it is useful.** Silence until the last week
//!    is a trap; a countdown from day one is nagging. The warning starts when
//!    it becomes actionable.
//! 4. **A grace period, honoured quietly.** Filing keeps working for a month
//!    past expiry. Late and amended returns are normal, deadlines slip, and a
//!    licence that lapsed four days ago is not the moment to stop someone
//!    filing. The anti-sharing property survives — a leaked licence still dies,
//!    just not on someone's deadline.

/// Filing keeps working this long past expiry.
///
/// Thirty days is chosen to cover the realistic gap — a return finished just
/// after the season, an amendment prompted by a slip that arrived late — while
/// staying far short of a second filing season.
pub const GRACE_SECS: i64 = 30 * 24 * 60 * 60;

/// How far ahead the app starts mentioning the expiry date.
pub const NOTICE_SECS: i64 = 60 * 24 * 60 * 60;

const DAY: i64 = 24 * 60 * 60;

/// Where a licence sits relative to its own expiry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Standing {
    /// Fine, and far enough away to be worth not mentioning.
    Current,

    /// Fine, and close enough that the date is worth showing.
    EndingSoon { days_left: i64 },

    /// Past its expiry but inside the grace period. Filing still works.
    InGrace { days_left: i64 },

    /// Past grace. Filing is blocked; everything else still works.
    Ended,

    /// The machine's clock is set before the licence was issued.
    ///
    /// Almost always a flat CMOS battery or a fresh install with the wrong
    /// date — not fraud. Treated as usable, because refusing to file over a
    /// wrong clock would punish the wrong person for the wrong reason, and a
    /// signature check does not depend on the clock at all.
    ClockLooksWrong,
}

impl Standing {
    /// Whether filing is permitted, as far as expiry is concerned.
    pub fn permits_filing(self) -> bool {
        !matches!(self, Standing::Ended)
    }

    /// Whether the app should draw attention to this.
    pub fn worth_saying(self) -> bool {
        !matches!(self, Standing::Current)
    }
}

/// Work out a licence's standing.
///
/// `expires_unix` of `None` never expires, which is the right answer for a
/// perpetual licence and for every development and certification licence.
pub fn standing(issued_unix: i64, expires_unix: Option<i64>, now_unix: i64) -> Standing {
    // Checked before expiry: a clock behind the issue date makes every other
    // comparison meaningless, and "expired" would be an actively misleading
    // thing to tell someone whose real problem is the date on their computer.
    if now_unix < issued_unix - DAY {
        return Standing::ClockLooksWrong;
    }

    let Some(expires) = expires_unix else {
        return Standing::Current;
    };

    if now_unix < expires {
        let days_left = ceil_days(expires - now_unix);

        return if expires - now_unix <= NOTICE_SECS {
            Standing::EndingSoon { days_left }
        } else {
            Standing::Current
        };
    }

    let grace_ends = expires + GRACE_SECS;

    if now_unix < grace_ends {
        Standing::InGrace {
            days_left: ceil_days(grace_ends - now_unix),
        }
    } else {
        Standing::Ended
    }
}

/// Round up, so a licence with six hours left says "1 day", never "0 days".
///
/// Telling someone they have zero days left while the software still works is
/// the kind of small dishonesty that makes people distrust the rest of it.
fn ceil_days(secs: i64) -> i64 {
    (secs + DAY - 1) / DAY
}

/// What to show the user, in plain words.
///
/// Deliberately never the word "expired" on its own, and never an instruction
/// to buy without first saying what still works.
pub fn describe(standing: Standing) -> Option<String> {
    match standing {
        Standing::Current => None,

        Standing::EndingSoon { days_left } => Some(format!(
            "This licence covers filing for {} more {}. Preparing returns \
             carries on working afterwards either way.",
            days_left,
            plural(days_left, "day", "days"),
        )),

        Standing::InGrace { days_left } => Some(format!(
            "This licence has passed its end date, so filing is running on a \
             {}-day grace period — {} left. Renew when convenient; nothing you \
             have entered is affected.",
            GRACE_SECS / DAY,
            days_left,
        )),

        Standing::Ended => Some(
            "This licence has ended, so it can no longer file. Everything else \
             still works: your returns open, recalculate, print and export as \
             normal, and renewing restores filing."
                .to_string(),
        ),

        Standing::ClockLooksWrong => Some(
            "This computer's date looks wrong — it is set earlier than the day \
             this licence was issued. Filing still works; it is worth fixing \
             the date so tax calculations that depend on it are right."
                .to_string(),
        ),
    }
}

fn plural(n: i64, one: &'static str, many: &'static str) -> &'static str {
    if n == 1 {
        one
    } else {
        many
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ISSUED: i64 = 1_800_000_000;
    const YEAR: i64 = 365 * DAY;

    fn at(offset_days: i64, expires: Option<i64>) -> Standing {
        standing(ISSUED, expires, ISSUED + offset_days * DAY)
    }

    #[test]
    fn a_perpetual_licence_is_never_chased_about_anything() {
        assert_eq!(at(0, None), Standing::Current);
        assert_eq!(at(10_000, None), Standing::Current);
    }

    #[test]
    fn a_fresh_licence_says_nothing_at_all() {
        let expires = Some(ISSUED + YEAR);

        assert_eq!(at(0, expires), Standing::Current);
        assert!(!at(0, expires).worth_saying(), "a new licence should not nag");
    }

    #[test]
    fn the_warning_starts_when_it_becomes_useful_and_not_before() {
        let expires = Some(ISSUED + YEAR);
        let notice_days = NOTICE_SECS / DAY;

        assert_eq!(at(365 - notice_days - 1, expires), Standing::Current);
        assert!(matches!(
            at(365 - notice_days + 1, expires),
            Standing::EndingSoon { .. }
        ));
    }

    #[test]
    fn a_licence_with_hours_left_says_one_day_not_zero() {
        let expires = ISSUED + YEAR;
        let six_hours_before = expires - 6 * 60 * 60;

        assert_eq!(
            standing(ISSUED, Some(expires), six_hours_before),
            Standing::EndingSoon { days_left: 1 },
            "rounding down would say 0 days while the software still works"
        );
    }

    #[test]
    fn filing_survives_the_day_after_expiry() {
        let expires = Some(ISSUED + YEAR);
        let just_after = at(366, expires);

        assert!(matches!(just_after, Standing::InGrace { .. }));
        assert!(
            just_after.permits_filing(),
            "a licence that lapsed yesterday must not block someone's deadline"
        );
    }

    #[test]
    fn the_grace_period_runs_out_exactly_when_it_should() {
        let expires = ISSUED + YEAR;
        let grace_days = GRACE_SECS / DAY;

        assert!(standing(ISSUED, Some(expires), expires + GRACE_SECS - 1).permits_filing());
        assert!(!standing(ISSUED, Some(expires), expires + GRACE_SECS).permits_filing());
        assert_eq!(
            standing(ISSUED, Some(expires), expires + 1),
            Standing::InGrace { days_left: grace_days }
        );
    }

    #[test]
    fn an_ended_licence_blocks_filing_and_nothing_else() {
        let expires = Some(ISSUED + YEAR);
        let ended = at(365 + 31, expires);

        assert_eq!(ended, Standing::Ended);
        assert!(!ended.permits_filing());

        // The wording has to lead with what still works, not with the sale.
        let said = describe(ended).unwrap();
        assert!(said.contains("open, recalculate, print and export"), "{said}");
    }

    #[test]
    fn a_backwards_clock_is_treated_as_a_broken_clock_not_a_cheat() {
        let before = ISSUED - 30 * DAY;
        let s = standing(ISSUED, Some(ISSUED + YEAR), before);

        assert_eq!(s, Standing::ClockLooksWrong);
        assert!(
            s.permits_filing(),
            "a flat CMOS battery must not stop someone filing"
        );
        assert!(describe(s).unwrap().contains("date looks wrong"));
    }

    #[test]
    fn a_clock_off_by_an_hour_is_not_worth_mentioning() {
        // Time zones, DST and NTP drift all produce small negative skew. Only a
        // genuinely wrong date should say anything.
        let s = standing(ISSUED, Some(ISSUED + YEAR), ISSUED - 3_600);
        assert_eq!(s, Standing::Current);
    }

    #[test]
    fn nothing_we_say_leads_with_a_demand_for_money() {
        let expires = Some(ISSUED + YEAR);

        for s in [
            at(360, expires),
            at(366, expires),
            at(400, expires),
            standing(ISSUED, expires, ISSUED - 30 * DAY),
        ] {
            let said = describe(s).expect("this standing should say something");
            let first = said.split('.').next().unwrap().to_lowercase();

            assert!(
                !first.contains("buy") && !first.contains("purchase"),
                "the opening sentence is a sales pitch: {said}"
            );
        }
    }
}
