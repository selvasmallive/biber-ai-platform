//! Where imported data comes from.
//!
//! Everything above this trait — mapping, aggregation, reconciliation, the
//! review flow — is ours and is fully implemented. The trait itself is the seam
//! where CRA's transport plugs in.

use rust_decimal::Decimal;

use crate::mapping::fact_for;
use crate::model::{ImportedBox, ImportedData, ImportedSlip, RoomFigure, RoomKind};
use crate::AutofillError;

pub trait SlipSource {
    /// Shown in the UI and recorded on the import, for the audit trail.
    fn label(&self) -> String;

    fn fetch(&self, tax_year: u16) -> Result<ImportedData, AutofillError>;
}

fn d(s: &str) -> Decimal {
    Decimal::from_str_exact(s).expect("fixture amounts are well formed")
}

/// Build a box, resolving its fact mapping from the table.
fn slip_box(slip_type: &str, label: &str, description: &str, amount: &str) -> ImportedBox {
    ImportedBox {
        box_label: label.to_string(),
        description: description.to_string(),
        amount: d(amount),
        fact_key: fact_for(slip_type, label).map(str::to_string),
    }
}

/// The real CRA Auto-fill my return transport.
///
/// **Not implemented, and cannot be implemented from public information.**
/// The endpoints, message schemas, and the delegated-authorization flow are
/// distributed to registered software developers under CRA's confidentiality
/// agreement. Guessing at them would produce something that looks finished and
/// silently is not.
///
/// What plugs in here once you are registered and AFR-approved:
///
/// 1. The taxpayer signs in to their own CRA My Account from inside the app —
///    a system browser or embedded auth flow CRA specifies. Freshet must never
///    see, prompt for, or store CRA credentials.
/// 2. The returned authorization is exchanged for the AFR payload for the
///    requested tax year.
/// 3. That payload is parsed into [`ImportedData`]. Every box CRA sends is
///    represented, mapped or not.
///
/// Nothing below this trait changes when that lands.
pub struct CraAutofill {
    pub tax_year: u16,
}

impl SlipSource for CraAutofill {
    fn label(&self) -> String {
        "CRA Auto-fill my return".to_string()
    }

    fn fetch(&self, _tax_year: u16) -> Result<ImportedData, AutofillError> {
        Err(AutofillError::TransportUnavailable)
    }
}

/// A stand-in source with realistic data, so the whole import path — mapping,
/// aggregation, conflicts, unmapped boxes, room advisories — can be exercised
/// and tested before CRA registration.
///
/// Deliberately includes the awkward cases: two employers whose combined CPP
/// exceeds the annual maximum, and a slip box Freshet does not model yet.
pub struct FixtureSource;

impl SlipSource for FixtureSource {
    fn label(&self) -> String {
        "Sample data (not CRA)".to_string()
    }

    fn fetch(&self, tax_year: u16) -> Result<ImportedData, AutofillError> {
        if tax_year != 2025 {
            return Err(AutofillError::UnsupportedYear(tax_year));
        }

        Ok(ImportedData {
            tax_year,
            source_label: self.label(),
            retrieved_at_unix: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|t| t.as_secs() as i64)
                .unwrap_or(0),

            slips: vec![
                ImportedSlip {
                    slip_type: "T4".into(),
                    issuer: "Northbay Logistics Ltd.".into(),
                    boxes: vec![
                        slip_box("T4", "14", "Employment income", "72500.00"),
                        slip_box("T4", "16", "Employee's CPP contributions", "4034.10"),
                        slip_box("T4", "16A", "Employee's second CPP contributions", "396.00"),
                        slip_box("T4", "18", "Employee's EI premiums", "1077.48"),
                        slip_box("T4", "22", "Income tax deducted", "13950.00"),
                    ],
                },
                ImportedSlip {
                    slip_type: "T4".into(),
                    issuer: "Riverside College".into(),
                    boxes: vec![
                        slip_box("T4", "14", "Employment income", "12500.00"),
                        // A second employer cannot see the first one's
                        // contributions, so together they exceed the annual
                        // maximum. The excess comes back on the return.
                        slip_box("T4", "16", "Employee's CPP contributions", "520.00"),
                        slip_box("T4", "18", "Employee's EI premiums", "205.00"),
                        slip_box("T4", "22", "Income tax deducted", "1450.00"),
                    ],
                },
                ImportedSlip {
                    slip_type: "T5".into(),
                    issuer: "Lakeshore Savings".into(),
                    boxes: vec![slip_box(
                        "T5",
                        "13",
                        "Interest from Canadian sources",
                        "842.55",
                    )],
                },
                ImportedSlip {
                    slip_type: "T4A".into(),
                    issuer: "Cedar Hill Consulting".into(),
                    // Freshet does not model self-employment yet, so this
                    // arrives unmapped and must be shown, never dropped.
                    boxes: vec![slip_box("T4A", "048", "Fees for services", "3200.00")],
                },
            ],

            rooms: vec![
                RoomFigure {
                    kind: RoomKind::RrspDeductionLimit,
                    amount: d("18420.00"),
                    as_of: "2026-03-15".into(),
                },
                RoomFigure {
                    kind: RoomKind::RrspUnusedContributions,
                    amount: d("0.00"),
                    as_of: "2026-03-15".into(),
                },
                RoomFigure {
                    kind: RoomKind::TfsaContributionRoom,
                    amount: d("14500.00"),
                    as_of: "2026-01-01".into(),
                },
            ],
        })
    }
}
