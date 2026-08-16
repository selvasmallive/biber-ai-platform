//! CRA Auto-fill my return.
//!
//! Auto-fill is a CRA service, not a scrape. Freshet never sees, prompts for,
//! or stores CRA credentials; the taxpayer authorizes access in their own My
//! Account and CRA returns the data.
//!
//! Two things this crate insists on, because both are ways importers hurt
//! people:
//!
//! - **Nothing is written to the return without a decision.** CRA is explicit
//!   that Auto-fill does not transfer responsibility — the filer must confirm
//!   every field. So this crate produces [`Proposal`]s, never mutations.
//! - **Contribution room always carries its as-of date.** CRA's figures reflect
//!   the last information processed and miss unreported contributions.
//!   Presenting one as a spendable balance is how software gets someone a
//!   penalty.
//!
//! The transport is the one piece that cannot be built from public information;
//! see [`CraAutofill`].

pub mod mapping;
pub mod model;
pub mod reconcile;
pub mod source;

pub use model::{ImportedBox, ImportedData, ImportedSlip, RoomFigure, RoomKind};
pub use reconcile::{apply, reconcile, Disposition, Proposal, SlipContribution};
pub use source::{CraAutofill, FixtureSource, SlipSource};

#[derive(Debug, thiserror::Error)]
pub enum AutofillError {
    #[error(
        "Auto-fill my return is not available in this build. It requires \
         registration with CRA as a software developer and approval for the \
         Auto-fill service."
    )]
    TransportUnavailable,

    #[error("you are not authorized to import this return's data")]
    NotAuthorized,

    #[error(
        "CRA does not have this year's slips yet. Most are received by the end \
         of February and available from mid-March."
    )]
    NotYetAvailable,

    #[error("Auto-fill is not supported for the {0} tax year in this build")]
    UnsupportedYear(u16),

    #[error("could not reach CRA: {0}")]
    Transport(String),
}
