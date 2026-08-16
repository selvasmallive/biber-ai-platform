//! Coupled returns.
//!
//! Two spouses file two returns, coupled by amounts that may sit on either and
//! by income that may be moved between them. Getting that right is where most
//! of the money is for a typical couple, and the rules of thumb are unreliable:
//!
//! - **Medical expenses** are reduced by 3% of the claimant's net income, which
//!   argues for the lower earner — until that spouse has no tax to absorb a
//!   non-refundable credit, at which point the answer inverts.
//! - **Donations** are credited at a higher rate above the first $200, so
//!   pooling beats splitting. In Ontario the credit lands *before* the surtax,
//!   so a dollar of it is worth up to 1.56 on a return that pays surtax.
//! - **Pension income splitting** is the one with the most moving parts. Moving
//!   income changes both net incomes, and net income drives the age amount
//!   clawback, the spousal amount, and the medical threshold. It can also
//!   create a *second* $2,000 pension income amount on the receiving return.
//!   The optimum is rarely 50%, and it is rarely 0%.
//!
//! Rather than encode any of that, this crate evaluates every allocation
//! against the real engine and picks the lowest **combined** tax. The
//! heuristics are used only to explain the answer afterwards.

use std::collections::BTreeMap;

use freshet_engine::decimal::parse_entered;
use freshet_engine::{compute, Assessment, Decimal, EngineError, FactSet, FormSet, PackSet};
use serde::Serialize;

// Facts the coupling injects. A single return never sets these itself.
const PARTNER_PRESENT: &str = "partner.present";
const PARTNER_NET_INCOME: &str = "partner.net_income";
const PARTNER_TRANSFER: &str = "partner.transfer_amount";
const PARTNER_ON_TRANSFER: &str = "partner.on_transfer_amount";
const MEDICAL_CLAIMED: &str = "medical.expenses_claimed";
const DONATIONS_CLAIMED: &str = "donations.claimed";
const CHILDCARE_CLAIMED: &str = "childcare.expenses_claimed";
const SPLIT_GIVEN: &str = "pension.split_given";
const SPLIT_RECEIVED: &str = "pension.split_received";
const SPLIT_RECEIVED_ELIGIBLE: &str = "pension.split_received_eligible";
/// Both partners' net income combined. Income-tested provincial credits such as
/// Ontario's CARE are measured against the family, not the individual.
const HOUSEHOLD_NET_INCOME: &str = "household.net_income";
/// Combined employment income. The Workers Benefit builds on the family's
/// working income, not one spouse's.
const HOUSEHOLD_WORKING_INCOME: &str = "household.working_income";
/// Set on the spouse who does *not* claim the Workers Benefit. A couple gets
/// one family benefit, not two.
const CWB_SUPPRESSED: &str = "cwb.suppressed";
/// Set on the spouse who may NOT claim the Ontario tax reduction's dependant
/// amounts. Those go to the *higher* earner — the mirror of child care.
const ON_REDUCTION_SUPPRESSED: &str = "on_reduction.dependants_suppressed";

// Facts the spouse supplies.
const OWN_PENSION: &str = "pension.own_eligible";
const AGE: &str = "taxpayer.age";
const EMPLOYMENT_INCOME: &str = "t4.employment_income";
const SELF_EMPLOYMENT_GROSS: &str = "self_employment.gross";
const SELF_EMPLOYMENT_EXPENSES: &str = "self_employment.expenses";

const TOTAL_TAX: &str = "summary.total_tax";
const BALANCE: &str = "summary.balance";
const NET_INCOME: &str = "fed.23600";
const FED_UNUSED: &str = "fed.unused_transferable";
const ON_UNUSED: &str = "on.unused_transferable";

/// The age at which pension income a spouse sends becomes eligible pension
/// income in the receiver's hands.
const PENSION_ELIGIBILITY_AGE: i64 = 65;

#[derive(Debug, thiserror::Error)]
pub enum CoupleError {
    #[error(transparent)]
    Engine(#[from] EngineError),
}

#[derive(Debug, Clone)]
pub struct Spouse {
    pub label: String,
    pub facts: BTreeMap<String, String>,
}

impl Spouse {
    fn fact(&self, key: &str) -> Decimal {
        self.facts
            .get(key)
            .and_then(|v| parse_entered(v))
            .unwrap_or(Decimal::ZERO)
    }

    fn eligible_pension(&self) -> Decimal {
        self.fact(OWN_PENSION)
    }

    fn is_pension_age(&self) -> bool {
        self.fact(AGE) >= Decimal::from(PENSION_ELIGIBILITY_AGE)
    }

    /// Employment plus net self-employment income. A business loss does not
    /// reduce working income for benefit purposes, so it floors at zero.
    fn working_income(&self) -> Decimal {
        let self_employed = self.fact(SELF_EMPLOYMENT_GROSS) - self.fact(SELF_EMPLOYMENT_EXPENSES);

        self.fact(EMPLOYMENT_INCOME)
            + if self_employed > Decimal::ZERO {
                self_employed
            } else {
                Decimal::ZERO
            }
    }
}

/// A couple and the amounts either of them could claim.
#[derive(Debug, Clone)]
pub struct Household {
    pub a: Spouse,
    pub b: Spouse,
    pub medical_expenses: Decimal,
    pub donations: Decimal,
    /// Family child care expenses. Unlike the others this is *not* allocated by
    /// the optimizer — see [`evaluate`].
    pub childcare: Decimal,
    /// Facts about the children, which belong to the household rather than to
    /// either spouse and are therefore applied to both returns.
    pub dependants: BTreeMap<String, String>,
}

impl Household {
    fn spouse(&self, who: Claimant) -> &Spouse {
        match who {
            Claimant::A => &self.a,
            Claimant::B => &self.b,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Claimant {
    A,
    B,
}

impl Claimant {
    pub const BOTH: [Claimant; 2] = [Claimant::A, Claimant::B];

    fn other(self) -> Self {
        match self {
            Claimant::A => Claimant::B,
            Claimant::B => Claimant::A,
        }
    }
}

/// Who claims what, and how much pension income moves.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct Allocation {
    pub medical: Claimant,
    pub donations: Claimant,
    /// The spouse giving up pension income. Meaningless when the rate is zero.
    pub pension_from: Claimant,
    /// Fraction of that spouse's eligible pension income moved, 0 to 0.50.
    pub pension_split_rate: Decimal,
}

impl Allocation {
    /// Whether any pension income actually moves under this allocation.
    pub fn splits(&self) -> bool {
        self.pension_split_rate > Decimal::ZERO
    }
}

#[derive(Debug, Clone)]
pub struct Outcome {
    pub allocation: Allocation,
    pub a: Assessment,
    pub b: Assessment,
    pub combined_tax: Decimal,
    /// Positive means the couple owes; negative is a combined refund.
    pub combined_balance: Decimal,
    /// Dollars of pension income actually moved.
    pub pension_split_amount: Decimal,
    /// Who the child care deduction fell to. Determined by the rules, not chosen.
    pub childcare_claimed_by: Claimant,
}

#[derive(Debug, Clone, Serialize)]
pub struct Decision {
    pub item: String,
    pub chose: String,
    /// Combined tax saved against the obvious alternative. Zero for a decision
    /// that was not ours to make.
    pub saved: Decimal,
    /// True when the rules fix the answer and there was nothing to optimize.
    pub mandatory: bool,
    pub why: String,
}

#[derive(Debug, Clone)]
pub struct Optimization {
    pub best: Outcome,
    pub decisions: Vec<Decision>,
    pub saving_vs_worst: Decimal,
    pub considered: usize,
}

fn to_facts(map: &BTreeMap<String, String>) -> FactSet {
    let mut facts = FactSet::new();
    for (k, raw) in map {
        if let Some(v) = parse_entered(raw) {
            facts.set(k.clone(), v);
        }
    }
    facts
}

/// How much pension income moves, and in which direction.
fn split_amount(household: &Household, allocation: Allocation) -> Decimal {
    if !allocation.splits() {
        return Decimal::ZERO;
    }
    (household.spouse(allocation.pension_from).eligible_pension()
        * allocation.pension_split_rate)
        .round_dp(2)
}

/// Facts common to every pass: the spouse's own entries plus the split.
fn base_facts(
    household: &Household,
    who: Claimant,
    allocation: Allocation,
    moved: Decimal,
) -> FactSet {
    let mut facts = to_facts(&household.spouse(who).facts);

    // The children are the same children on both returns.
    for (k, raw) in &household.dependants {
        if let Some(v) = parse_entered(raw) {
            facts.set(k.clone(), v);
        }
    }

    // The Workers Benefit is a family benefit claimed on one return. Which one
    // does not change the amount, so it goes to the larger earner and ties are
    // broken toward A, keeping the answer stable.
    let working = household.a.working_income() + household.b.working_income();
    let cwb_claimant = if household.a.working_income() >= household.b.working_income() {
        Claimant::A
    } else {
        Claimant::B
    };

    facts
        .set(HOUSEHOLD_WORKING_INCOME, working)
        .set(
            CWB_SUPPRESSED,
            if who == cwb_claimant {
                Decimal::ZERO
            } else {
                Decimal::ONE
            },
        );

    let giving = allocation.splits() && allocation.pension_from == who;
    let receiving = allocation.splits() && allocation.pension_from != who;

    facts
        .set(SPLIT_GIVEN, if giving { moved } else { Decimal::ZERO })
        .set(SPLIT_RECEIVED, if receiving { moved } else { Decimal::ZERO })
        .set(
            SPLIT_RECEIVED_ELIGIBLE,
            // Split income counts toward the receiver's pension income amount
            // only if the spouse who sent it was old enough for it to be
            // eligible pension income in the first place.
            if receiving && household.spouse(allocation.pension_from).is_pension_age() {
                Decimal::ONE
            } else {
                Decimal::ZERO
            },
        );

    facts
}

fn pooled(who: Claimant, allocation: Allocation, household: &Household) -> (Decimal, Decimal) {
    let medical = if allocation.medical == who {
        household.medical_expenses
    } else {
        Decimal::ZERO
    };
    let donations = if allocation.donations == who {
        household.donations
    } else {
        Decimal::ZERO
    };
    (medical, donations)
}

/// Compute both returns under one allocation.
///
/// Four passes, in this order, because each depends on the one before:
///
/// 0. **Incomes before child care.** Child care is not ours to allocate — the
///    rules require the spouse with the *lower net income* to claim it — so we
///    first need to know who that is, measured before the deduction itself
///    moves the comparison.
/// 1. **Net incomes**, now with child care applied. These also move with the
///    pension split, so they cannot be computed once and reused across
///    allocations the way they could before splitting existed.
/// 2. **Unused transferable amounts.** Schedule 2 needs each spouse's own
///    return resolved first, with no transfer in it, to see what they cannot
///    use.
/// 3. **Final returns**, with each spouse receiving the other's unused amounts.
///
/// A spouse with unused transferable amounts has no tax left, so a transfer
/// flowing back to them is a no-op — which is why running the transfer in both
/// directions is safe and needs no tie-break.
pub fn evaluate(
    forms: &FormSet,
    packs: &PackSet,
    household: &Household,
    allocation: Allocation,
) -> Result<Outcome, CoupleError> {
    let moved = split_amount(household, allocation);

    // Pass 0.
    let mut pre = [Decimal::ZERO; 2];
    for (i, who) in Claimant::BOTH.into_iter().enumerate() {
        let mut facts = base_facts(household, who, allocation, moved);
        facts
            .set(PARTNER_PRESENT, Decimal::ZERO)
            .set(PARTNER_NET_INCOME, Decimal::ZERO)
            .set(MEDICAL_CLAIMED, Decimal::ZERO)
            .set(DONATIONS_CLAIMED, Decimal::ZERO)
            .set(CHILDCARE_CLAIMED, Decimal::ZERO)
            .set(PARTNER_TRANSFER, Decimal::ZERO)
            .set(PARTNER_ON_TRANSFER, Decimal::ZERO);

        pre[i] = compute(forms, packs, &facts)?
            .get(NET_INCOME)
            .unwrap_or(Decimal::ZERO);
    }

    // Ties go to A, which keeps the answer stable rather than flipping between
    // equivalent assignments as unrelated inputs change.
    let childcare_claimed_by = if pre[0] <= pre[1] {
        Claimant::A
    } else {
        Claimant::B
    };

    let childcare_for = |who: Claimant| {
        if who == childcare_claimed_by {
            household.childcare
        } else {
            Decimal::ZERO
        }
    };

    // Pass 1.
    let mut net = [Decimal::ZERO; 2];
    for (i, who) in Claimant::BOTH.into_iter().enumerate() {
        let mut facts = base_facts(household, who, allocation, moved);
        facts
            .set(PARTNER_PRESENT, Decimal::ZERO)
            .set(PARTNER_NET_INCOME, Decimal::ZERO)
            .set(MEDICAL_CLAIMED, Decimal::ZERO)
            .set(DONATIONS_CLAIMED, Decimal::ZERO)
            .set(CHILDCARE_CLAIMED, childcare_for(who))
            .set(
                ON_REDUCTION_SUPPRESSED,
                // Child care goes to the lower earner and the Ontario tax
                // reduction's dependant amounts to the higher, so the same
                // comparison decides both — in opposite directions.
                if who == childcare_claimed_by {
                    Decimal::ONE
                } else {
                    Decimal::ZERO
                },
            )
            .set(PARTNER_TRANSFER, Decimal::ZERO)
            .set(PARTNER_ON_TRANSFER, Decimal::ZERO);

        net[i] = compute(forms, packs, &facts)?
            .get(NET_INCOME)
            .unwrap_or(Decimal::ZERO);
    }

    // Pass 2.
    let mut unused = [(Decimal::ZERO, Decimal::ZERO); 2];
    for (i, who) in Claimant::BOTH.into_iter().enumerate() {
        let (medical, donations) = pooled(who, allocation, household);
        let mut facts = base_facts(household, who, allocation, moved);
        facts
            .set(PARTNER_PRESENT, Decimal::ONE)
            .set(PARTNER_NET_INCOME, net[1 - i])
            .set(HOUSEHOLD_NET_INCOME, net[0] + net[1])
            .set(MEDICAL_CLAIMED, medical)
            .set(DONATIONS_CLAIMED, donations)
            .set(CHILDCARE_CLAIMED, childcare_for(who))
            .set(
                ON_REDUCTION_SUPPRESSED,
                // Child care goes to the lower earner and the Ontario tax
                // reduction's dependant amounts to the higher, so the same
                // comparison decides both — in opposite directions.
                if who == childcare_claimed_by {
                    Decimal::ONE
                } else {
                    Decimal::ZERO
                },
            )
            .set(PARTNER_TRANSFER, Decimal::ZERO)
            .set(PARTNER_ON_TRANSFER, Decimal::ZERO);

        let a = compute(forms, packs, &facts)?;
        unused[i] = (
            a.get(FED_UNUSED).unwrap_or(Decimal::ZERO),
            a.get(ON_UNUSED).unwrap_or(Decimal::ZERO),
        );
    }

    // Pass 3.
    let mut finals = Vec::with_capacity(2);
    for (i, who) in Claimant::BOTH.into_iter().enumerate() {
        let (medical, donations) = pooled(who, allocation, household);
        let mut facts = base_facts(household, who, allocation, moved);
        facts
            .set(PARTNER_PRESENT, Decimal::ONE)
            .set(PARTNER_NET_INCOME, net[1 - i])
            .set(HOUSEHOLD_NET_INCOME, net[0] + net[1])
            .set(MEDICAL_CLAIMED, medical)
            .set(DONATIONS_CLAIMED, donations)
            .set(CHILDCARE_CLAIMED, childcare_for(who))
            .set(
                ON_REDUCTION_SUPPRESSED,
                // Child care goes to the lower earner and the Ontario tax
                // reduction's dependant amounts to the higher, so the same
                // comparison decides both — in opposite directions.
                if who == childcare_claimed_by {
                    Decimal::ONE
                } else {
                    Decimal::ZERO
                },
            )
            .set(PARTNER_TRANSFER, unused[1 - i].0)
            .set(PARTNER_ON_TRANSFER, unused[1 - i].1);

        finals.push(compute(forms, packs, &facts)?);
    }

    let b = finals.pop().expect("two returns");
    let a = finals.pop().expect("two returns");

    let combined_tax =
        a.get(TOTAL_TAX).unwrap_or(Decimal::ZERO) + b.get(TOTAL_TAX).unwrap_or(Decimal::ZERO);
    let combined_balance =
        a.get(BALANCE).unwrap_or(Decimal::ZERO) + b.get(BALANCE).unwrap_or(Decimal::ZERO);

    Ok(Outcome {
        allocation,
        a,
        b,
        combined_tax,
        combined_balance,
        pension_split_amount: moved,
        childcare_claimed_by,
    })
}

/// The split levels worth trying.
///
/// Zero appears once; the direction is meaningless there. A direction is only
/// offered when that spouse actually has pension income to move, which keeps
/// the search at four allocations for the common case of a couple with none.
fn split_options(household: &Household) -> Vec<(Claimant, Decimal)> {
    let mut out = vec![(Claimant::A, Decimal::ZERO)];

    for step in 1..=10i64 {
        let rate = Decimal::new(step * 5, 2);
        for who in Claimant::BOTH {
            if household.spouse(who).eligible_pension() > Decimal::ZERO {
                out.push((who, rate));
            }
        }
    }

    out
}

fn label_of(household: &Household, who: Claimant) -> String {
    household.spouse(who).label.clone()
}

/// Find the allocation with the lowest combined tax, and explain it.
pub fn optimize(
    forms: &FormSet,
    packs: &PackSet,
    household: &Household,
) -> Result<Optimization, CoupleError> {
    let mut outcomes = Vec::new();

    for medical in Claimant::BOTH {
        for donations in Claimant::BOTH {
            for (pension_from, pension_split_rate) in split_options(household) {
                outcomes.push(evaluate(
                    forms,
                    packs,
                    household,
                    Allocation {
                        medical,
                        donations,
                        pension_from,
                        pension_split_rate,
                    },
                )?);
            }
        }
    }

    let considered = outcomes.len();

    // Ties go to the first candidate, which keeps the answer stable rather than
    // flipping between equivalent allocations as unrelated inputs change.
    let best = outcomes
        .iter()
        .min_by(|x, y| x.combined_tax.cmp(&y.combined_tax))
        .expect("the allocation space is never empty")
        .clone();

    let worst = outcomes
        .iter()
        .map(|o| o.combined_tax)
        .max()
        .unwrap_or(best.combined_tax);

    let mut decisions = Vec::new();

    // Reported first because it is the one constraint the couple cannot trade
    // against the others.
    if household.childcare > Decimal::ZERO {
        decisions.push(Decision {
            item: "Child care".into(),
            chose: label_of(household, best.childcare_claimed_by),
            saved: Decimal::ZERO,
            mandatory: true,
            why: "Child care must be claimed by the spouse with the lower net income — this one is not a choice, and there is nothing to optimize. It is also why the two-thirds-of-earned-income cap bites so often: the person required to claim is the one with less income to measure it against.".into(),
        });
    }

    if household.medical_expenses > Decimal::ZERO {
        let alt = evaluate(
            forms,
            packs,
            household,
            Allocation {
                medical: best.allocation.medical.other(),
                ..best.allocation
            },
        )?;

        decisions.push(Decision {
            item: "Medical expenses".into(),
            chose: label_of(household, best.allocation.medical),
            saved: alt.combined_tax - best.combined_tax,
            mandatory: false,
            why: "Medical expenses are reduced by 3% of the claimant's net income, so the lower earner usually claims them — unless their tax is too small to absorb the credit.".into(),
        });
    }

    if household.donations > Decimal::ZERO {
        let alt = evaluate(
            forms,
            packs,
            household,
            Allocation {
                donations: best.allocation.donations.other(),
                ..best.allocation
            },
        )?;

        decisions.push(Decision {
            item: "Donations".into(),
            chose: label_of(household, best.allocation.donations),
            saved: alt.combined_tax - best.combined_tax,
            mandatory: false,
            why: "Only the first $200 of donations is credited at the low rate, so pooling beats splitting. In Ontario the credit also lands before the surtax, so it is worth more on a return that pays surtax.".into(),
        });
    }

    if best.allocation.splits() {
        // Measured against not splitting at all, which is what the couple would
        // otherwise do.
        let alt = evaluate(
            forms,
            packs,
            household,
            Allocation {
                pension_split_rate: Decimal::ZERO,
                ..best.allocation
            },
        )?;

        let rate = (best.allocation.pension_split_rate * Decimal::from(100)).round_dp(0);

        decisions.push(Decision {
            item: "Pension income splitting".into(),
            chose: format!(
                "move {rate}% ({}) from {} to {}",
                best.pension_split_amount,
                label_of(household, best.allocation.pension_from),
                label_of(household, best.allocation.pension_from.other())
            ),
            saved: alt.combined_tax - best.combined_tax,
            mandatory: false,
            why: "Moving pension income lowers one net income and raises the other. That can pull income out of a higher bracket, restore an age amount that was being clawed back, and give the receiving spouse their own $2,000 pension income amount. The best share is rarely the maximum 50%.".into(),
        });
    } else if split_options(household).len() > 1 {
        decisions.push(Decision {
            item: "Pension income splitting".into(),
            chose: "do not split".into(),
            saved: Decimal::ZERO,
            mandatory: false,
            why: "Every share from 5% to 50% was computed and none reduced the couple's combined tax. Splitting would move income without gaining anything.".into(),
        });
    }

    Ok(Optimization {
        best,
        decisions,
        saving_vs_worst: worst
            - outcomes
                .iter()
                .map(|o| o.combined_tax)
                .min()
                .unwrap_or(Decimal::ZERO),
        considered,
    })
}
