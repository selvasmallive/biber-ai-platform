//! What comes back from an Auto-fill request.

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

/// One box on one slip, as CRA holds it.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImportedBox {
    /// The box as printed on the slip, e.g. `"14"` or `"16A"`.
    pub box_label: String,
    pub description: String,
    pub amount: Decimal,
    /// The engine fact this maps to, or `None` if Freshet does not yet model it.
    /// Unmapped boxes are surfaced rather than dropped — silently discarding
    /// income CRA already knows about is the worst thing an importer can do.
    pub fact_key: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImportedSlip {
    /// `"T4"`, `"T5"`, `"T4A"`, ...
    pub slip_type: String,
    /// Employer or payer name, as CRA holds it.
    pub issuer: String,
    pub boxes: Vec<ImportedBox>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RoomKind {
    RrspDeductionLimit,
    RrspUnusedContributions,
    FhsaParticipationRoom,
    TfsaContributionRoom,
}

impl RoomKind {
    pub fn label(self) -> &'static str {
        match self {
            RoomKind::RrspDeductionLimit => "RRSP deduction limit",
            RoomKind::RrspUnusedContributions => "Unused RRSP contributions",
            RoomKind::FhsaParticipationRoom => "FHSA participation room",
            RoomKind::TfsaContributionRoom => "TFSA contribution room",
        }
    }

    /// Whether over-contributing to this account attracts a penalty tax.
    pub fn penalises_over_contribution(self) -> bool {
        matches!(
            self,
            RoomKind::TfsaContributionRoom | RoomKind::FhsaParticipationRoom
        )
    }
}

/// A contribution-room figure. Always carries the date CRA computed it.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoomFigure {
    pub kind: RoomKind,
    pub amount: Decimal,
    /// ISO date the figure is current as of, straight from CRA.
    pub as_of: String,
}

impl RoomFigure {
    /// The caution that must accompany this figure wherever it is shown.
    ///
    /// CRA's room figures reflect the last information it processed and miss
    /// contributions an issuer has not yet reported. Presenting one as a
    /// spendable balance is how software gets a user penalised.
    pub fn advisory(&self) -> String {
        let base = format!(
            "CRA computed this as of {}. It does not include any contribution your issuer has not yet reported.",
            self.as_of
        );

        if self.kind.penalises_over_contribution() {
            format!(
                "{base} Confirm the figure with your financial institution before contributing — over-contributing is penalised at 1% per month on the excess."
            )
        } else {
            format!("{base} Confirm it against your latest notice of assessment.")
        }
    }
}

/// The result of one Auto-fill request.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImportedData {
    pub tax_year: u16,
    /// Which source produced this, for the audit trail.
    pub source_label: String,
    pub retrieved_at_unix: i64,
    pub slips: Vec<ImportedSlip>,
    pub rooms: Vec<RoomFigure>,
}

impl ImportedData {
    /// Boxes CRA sent that Freshet cannot yet place on the return.
    ///
    /// The user must be told about these explicitly: they represent income or
    /// deductions that CRA knows about and this build would otherwise omit.
    pub fn unmapped(&self) -> Vec<&ImportedBox> {
        self.slips
            .iter()
            .flat_map(|s| &s.boxes)
            .filter(|b| b.fact_key.is_none())
            .collect()
    }

    pub fn slip_count(&self) -> usize {
        self.slips.len()
    }
}
