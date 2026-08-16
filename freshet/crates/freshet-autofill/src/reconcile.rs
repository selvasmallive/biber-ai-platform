//! Turning imported slips into proposed changes.
//!
//! Nothing here writes to the return. It produces proposals the user accepts or
//! rejects, because CRA is explicit that Auto-fill does not transfer
//! responsibility: the filer must confirm every field is true, accurate and
//! complete. Software that silently merges imported values takes that decision
//! away from the person who is legally answerable for it.

use std::collections::BTreeMap;

use freshet_engine::decimal::parse_entered;
use rust_decimal::Decimal;
use serde::Serialize;

use crate::mapping::describe;
use crate::model::ImportedData;

/// Which slip an amount came from, kept so the review screen can show
/// "$85,000 = $72,500 from A + $12,500 from B".
#[derive(Debug, Clone, Serialize)]
pub struct SlipContribution {
    pub slip_type: String,
    pub issuer: String,
    pub box_label: String,
    pub amount: Decimal,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Disposition {
    /// Nothing entered for this fact yet.
    New,
    /// What is entered already equals what CRA holds.
    Matches,
    /// The user has a different value. Never overwritten without a decision.
    Conflict { current: Decimal },
}

#[derive(Debug, Clone, Serialize)]
pub struct Proposal {
    pub fact_key: String,
    pub description: String,
    /// The sum across every slip feeding this fact.
    pub total: Decimal,
    pub from: Vec<SlipContribution>,
    pub disposition: Disposition,
}

impl Proposal {
    /// Whether accepting this changes anything.
    pub fn is_change(&self) -> bool {
        !matches!(self.disposition, Disposition::Matches)
    }
}

/// Compare imported data against what is currently on the return.
///
/// Multiple slips feeding one fact are summed — two T4s make one employment
/// income figure — which is the case hand entry most often gets wrong.
pub fn reconcile(data: &ImportedData, current: &BTreeMap<String, String>) -> Vec<Proposal> {
    let mut totals: BTreeMap<&str, (Decimal, Vec<SlipContribution>)> = BTreeMap::new();

    for slip in &data.slips {
        for entry in &slip.boxes {
            let Some(key) = entry.fact_key.as_deref() else {
                continue;
            };

            let slot = totals.entry(key).or_insert((Decimal::ZERO, Vec::new()));
            slot.0 += entry.amount;
            slot.1.push(SlipContribution {
                slip_type: slip.slip_type.clone(),
                issuer: slip.issuer.clone(),
                box_label: entry.box_label.clone(),
                amount: entry.amount,
            });
        }
    }

    totals
        .into_iter()
        .map(|(key, (total, from))| {
            let entered = current.get(key).and_then(|raw| parse_entered(raw));

            let disposition = match entered {
                None => Disposition::New,
                Some(v) if v == total => Disposition::Matches,
                Some(v) => Disposition::Conflict { current: v },
            };

            Proposal {
                fact_key: key.to_string(),
                description: describe(key).to_string(),
                total,
                from,
                disposition,
            }
        })
        .collect()
}

/// Apply the chosen proposals to a fact map, returning the updated map.
///
/// Only the keys named in `accept` are touched; everything else on the return
/// is left exactly as the user had it.
pub fn apply(
    current: &BTreeMap<String, String>,
    proposals: &[Proposal],
    accept: &[String],
) -> BTreeMap<String, String> {
    let mut next = current.clone();

    for p in proposals {
        if accept.iter().any(|k| k == &p.fact_key) {
            next.insert(p.fact_key.clone(), p.total.to_string());
        }
    }

    next
}
