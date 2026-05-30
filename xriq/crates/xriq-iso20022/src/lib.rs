//! ISO 20022-aligned preview mappings for the XRIQ private devnet.
//!
//! This crate is a compatibility adapter only. It does not claim ISO 20022
//! certification, bank connectivity, SWIFT connectivity, legal compliance, or
//! production payment-network support.

use xriq_api::{AccountHistoryResponse, AccountTransactionResponse, TransactionResponse};

pub const ISO_ENVIRONMENT: &str = "private-devnet";
pub const ISO_MAPPING_VERSION: &str = "xriq-iso20022-preview-v1";
pub const ISO_DEV_CURRENCY: &str = "XRIQ-DEV";

pub const PAYMENT_INITIATION_MESSAGE_TYPE: &str = "payment_initiation_preview";
pub const PAYMENT_STATUS_MESSAGE_TYPE: &str = "payment_status_preview";
pub const ACCOUNT_STATEMENT_MESSAGE_TYPE: &str = "account_statement_preview";

pub const PAYMENT_INITIATION_UNSUPPORTED_FIELDS: &[&str] = &[
    "bank_bic",
    "iban",
    "clearing_system_member_id",
    "legal_entity_identifier",
];
pub const PAYMENT_STATUS_UNSUPPORTED_FIELDS: &[&str] =
    &["interbank_settlement_date", "clearing_system_reference"];
pub const ACCOUNT_STATEMENT_UNSUPPORTED_FIELDS: &[&str] = &[
    "bank_account_servicer",
    "booking_date_from_bank",
    "fiat_currency",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PaymentInitiationPreview {
    pub environment: &'static str,
    pub not_certified: bool,
    pub mapping_version: &'static str,
    pub message_type: &'static str,
    pub message_id: String,
    pub source_tx_hash: String,
    pub xriq: XriqTransferFields,
    pub iso20022_aligned: PaymentInitiationAligned,
    pub unsupported_fields: Vec<&'static str>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct XriqTransferFields {
    pub from_address: String,
    pub to_address: String,
    pub amount_base_units: String,
    pub fee_base_units: String,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PaymentInitiationAligned {
    pub creditor_account: String,
    pub debtor_account: String,
    pub instructed_amount: String,
    pub currency: &'static str,
    pub end_to_end_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PaymentStatusPreview {
    pub environment: &'static str,
    pub not_certified: bool,
    pub mapping_version: &'static str,
    pub message_type: &'static str,
    pub message_id: String,
    pub source_tx_hash: String,
    pub xriq_status: String,
    pub iso20022_aligned: PaymentStatusAligned,
    pub unsupported_fields: Vec<&'static str>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PaymentStatusAligned {
    pub original_end_to_end_id: String,
    pub transaction_status: &'static str,
    pub status_reason: &'static str,
    pub confirmed_block_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountStatementPreview {
    pub environment: &'static str,
    pub not_certified: bool,
    pub mapping_version: &'static str,
    pub message_type: &'static str,
    pub message_id: String,
    pub account_address: String,
    pub from: String,
    pub to: String,
    pub opening_balance_base_units: String,
    pub closing_balance_base_units: String,
    pub entries: Vec<AccountStatementEntry>,
    pub unsupported_fields: Vec<&'static str>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountStatementEntry {
    pub tx_hash: String,
    pub direction: &'static str,
    pub amount_base_units: String,
    pub fee_base_units: String,
    pub status: &'static str,
    pub block_height: u64,
}

pub fn payment_initiation_preview(transaction: &TransactionResponse) -> PaymentInitiationPreview {
    PaymentInitiationPreview {
        environment: ISO_ENVIRONMENT,
        not_certified: true,
        mapping_version: ISO_MAPPING_VERSION,
        message_type: PAYMENT_INITIATION_MESSAGE_TYPE,
        message_id: format!("iso-preview-{}", short_hash(&transaction.tx_hash)),
        source_tx_hash: transaction.tx_hash.clone(),
        xriq: XriqTransferFields {
            from_address: transaction.from_address.clone(),
            to_address: transaction.to_address.clone(),
            amount_base_units: transaction.amount_base_units.clone(),
            fee_base_units: transaction.fee_base_units.clone(),
            nonce: transaction.nonce,
        },
        iso20022_aligned: PaymentInitiationAligned {
            creditor_account: transaction.to_address.clone(),
            debtor_account: transaction.from_address.clone(),
            instructed_amount: transaction.amount_base_units.clone(),
            currency: ISO_DEV_CURRENCY,
            end_to_end_id: transaction.tx_hash.clone(),
        },
        unsupported_fields: PAYMENT_INITIATION_UNSUPPORTED_FIELDS.to_vec(),
    }
}

pub fn payment_status_preview(transaction: &TransactionResponse) -> PaymentStatusPreview {
    let status = payment_status_mapping(transaction);
    PaymentStatusPreview {
        environment: ISO_ENVIRONMENT,
        not_certified: true,
        mapping_version: ISO_MAPPING_VERSION,
        message_type: PAYMENT_STATUS_MESSAGE_TYPE,
        message_id: format!("iso-status-{}", short_hash(&transaction.tx_hash)),
        source_tx_hash: transaction.tx_hash.clone(),
        xriq_status: transaction.status.clone(),
        iso20022_aligned: status,
        unsupported_fields: PAYMENT_STATUS_UNSUPPORTED_FIELDS.to_vec(),
    }
}

pub fn account_statement_preview(
    history: &AccountHistoryResponse,
    opening_balance_base_units: impl Into<String>,
    closing_balance_base_units: impl Into<String>,
    from: impl Into<String>,
    to: impl Into<String>,
) -> AccountStatementPreview {
    let to = to.into();
    AccountStatementPreview {
        environment: ISO_ENVIRONMENT,
        not_certified: true,
        mapping_version: ISO_MAPPING_VERSION,
        message_type: ACCOUNT_STATEMENT_MESSAGE_TYPE,
        message_id: statement_message_id(&history.address, history.transactions.last()),
        account_address: history.address.clone(),
        from: from.into(),
        to,
        opening_balance_base_units: opening_balance_base_units.into(),
        closing_balance_base_units: closing_balance_base_units.into(),
        entries: history
            .transactions
            .iter()
            .map(account_statement_entry)
            .collect(),
        unsupported_fields: ACCOUNT_STATEMENT_UNSUPPORTED_FIELDS.to_vec(),
    }
}

fn payment_status_mapping(transaction: &TransactionResponse) -> PaymentStatusAligned {
    match transaction.status.as_str() {
        "confirmed" => PaymentStatusAligned {
            original_end_to_end_id: transaction.tx_hash.clone(),
            transaction_status: "ACSC",
            status_reason: "accepted_settlement_completed_on_private_devnet",
            confirmed_block_height: Some(transaction.block_height),
        },
        "pending" => PaymentStatusAligned {
            original_end_to_end_id: transaction.tx_hash.clone(),
            transaction_status: "PDNG",
            status_reason: "pending_private_devnet_confirmation",
            confirmed_block_height: None,
        },
        "rejected" => PaymentStatusAligned {
            original_end_to_end_id: transaction.tx_hash.clone(),
            transaction_status: "RJCT",
            status_reason: "rejected_on_private_devnet",
            confirmed_block_height: None,
        },
        _ => PaymentStatusAligned {
            original_end_to_end_id: transaction.tx_hash.clone(),
            transaction_status: "UNKW",
            status_reason: "unsupported_xriq_status",
            confirmed_block_height: None,
        },
    }
}

fn account_statement_entry(transaction: &AccountTransactionResponse) -> AccountStatementEntry {
    AccountStatementEntry {
        tx_hash: transaction.tx_hash.clone(),
        direction: statement_direction(transaction.direction),
        amount_base_units: transaction.amount_base_units.clone(),
        fee_base_units: transaction.fee_base_units.clone(),
        status: "confirmed",
        block_height: transaction.block_height,
    }
}

fn statement_direction(direction: &str) -> &'static str {
    match direction {
        "sent" => "debit",
        "received" => "credit",
        "self" => "self",
        _ => "unknown",
    }
}

fn statement_message_id(
    address: &str,
    last_transaction: Option<&AccountTransactionResponse>,
) -> String {
    let account_label = address
        .strip_prefix("xriqdev1")
        .unwrap_or(address)
        .chars()
        .take(5)
        .collect::<String>();
    let height = last_transaction
        .map(|transaction| transaction.block_height)
        .unwrap_or(0);
    format!("iso-statement-{account_label}-{height:04}")
}

fn short_hash(tx_hash: &str) -> String {
    tx_hash.chars().take(8).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_api::{AccountHistoryResponse, AccountTransactionResponse, TransactionResponse};

    const TX_HASH: &str = "fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565";

    fn transaction() -> TransactionResponse {
        TransactionResponse {
            tx_hash: TX_HASH.to_string(),
            block_height: 1,
            block_hash: "fe349b87f4219a7edd3dc8cb430b27200eb3500ab9550692b1493d4c4312371d"
                .to_string(),
            transaction_index: 0,
            status: "confirmed".to_string(),
            from_address: "xriqdev1alice00000000000".to_string(),
            to_address: "xriqdev1bobbb00000000000".to_string(),
            amount_base_units: "25".to_string(),
            fee_base_units: "2".to_string(),
            nonce: 0,
        }
    }

    fn history() -> AccountHistoryResponse {
        AccountHistoryResponse {
            environment: "private-devnet",
            network: "xriq-devnet".to_string(),
            address: "xriqdev1alice00000000000".to_string(),
            limit: 25,
            next_cursor: None,
            transactions: vec![AccountTransactionResponse {
                address: "xriqdev1alice00000000000".to_string(),
                tx_hash: TX_HASH.to_string(),
                direction: "sent",
                block_height: 1,
                transaction_index: 0,
                amount_base_units: "25".to_string(),
                fee_base_units: "2".to_string(),
            }],
        }
    }

    #[test]
    fn maps_payment_initiation_preview_without_certification_claims() {
        let preview = payment_initiation_preview(&transaction());

        assert_eq!(preview.environment, ISO_ENVIRONMENT);
        assert!(preview.not_certified);
        assert_eq!(preview.mapping_version, ISO_MAPPING_VERSION);
        assert_eq!(preview.message_type, PAYMENT_INITIATION_MESSAGE_TYPE);
        assert_eq!(preview.message_id, "iso-preview-fceb9425");
        assert_eq!(preview.source_tx_hash, TX_HASH);
        assert_eq!(preview.xriq.from_address, "xriqdev1alice00000000000");
        assert_eq!(preview.xriq.to_address, "xriqdev1bobbb00000000000");
        assert_eq!(preview.xriq.amount_base_units, "25");
        assert_eq!(preview.xriq.fee_base_units, "2");
        assert_eq!(preview.xriq.nonce, 0);
        assert_eq!(
            preview.iso20022_aligned.creditor_account,
            "xriqdev1bobbb00000000000"
        );
        assert_eq!(preview.iso20022_aligned.currency, ISO_DEV_CURRENCY);
        assert_eq!(preview.iso20022_aligned.end_to_end_id, TX_HASH);
        assert_eq!(
            preview.unsupported_fields,
            PAYMENT_INITIATION_UNSUPPORTED_FIELDS
        );
    }

    #[test]
    fn maps_confirmed_status_to_private_devnet_acsc_preview() {
        let status = payment_status_preview(&transaction());

        assert_eq!(status.environment, ISO_ENVIRONMENT);
        assert!(status.not_certified);
        assert_eq!(status.message_type, PAYMENT_STATUS_MESSAGE_TYPE);
        assert_eq!(status.message_id, "iso-status-fceb9425");
        assert_eq!(status.xriq_status, "confirmed");
        assert_eq!(status.iso20022_aligned.original_end_to_end_id, TX_HASH);
        assert_eq!(status.iso20022_aligned.transaction_status, "ACSC");
        assert_eq!(
            status.iso20022_aligned.status_reason,
            "accepted_settlement_completed_on_private_devnet"
        );
        assert_eq!(status.iso20022_aligned.confirmed_block_height, Some(1));
        assert_eq!(status.unsupported_fields, PAYMENT_STATUS_UNSUPPORTED_FIELDS);
    }

    #[test]
    fn maps_non_confirmed_statuses_without_inventing_bank_data() {
        let mut pending = transaction();
        pending.status = "pending".to_string();
        let pending_status = payment_status_preview(&pending);

        assert_eq!(pending_status.iso20022_aligned.transaction_status, "PDNG");
        assert_eq!(pending_status.iso20022_aligned.confirmed_block_height, None);

        let mut unknown = transaction();
        unknown.status = "other".to_string();
        let unknown_status = payment_status_preview(&unknown);

        assert_eq!(unknown_status.iso20022_aligned.transaction_status, "UNKW");
        assert_eq!(
            unknown_status.iso20022_aligned.status_reason,
            "unsupported_xriq_status"
        );
    }

    #[test]
    fn maps_account_statement_preview_with_debit_entry() {
        let statement = account_statement_preview(
            &history(),
            "100",
            "73",
            "1970-01-01T00:00:00Z",
            "1970-01-01T00:00:02Z",
        );

        assert_eq!(statement.environment, ISO_ENVIRONMENT);
        assert!(statement.not_certified);
        assert_eq!(statement.message_type, ACCOUNT_STATEMENT_MESSAGE_TYPE);
        assert_eq!(statement.message_id, "iso-statement-alice-0001");
        assert_eq!(statement.account_address, "xriqdev1alice00000000000");
        assert_eq!(statement.opening_balance_base_units, "100");
        assert_eq!(statement.closing_balance_base_units, "73");
        assert_eq!(statement.entries.len(), 1);
        assert_eq!(statement.entries[0].tx_hash, TX_HASH);
        assert_eq!(statement.entries[0].direction, "debit");
        assert_eq!(statement.entries[0].amount_base_units, "25");
        assert_eq!(statement.entries[0].fee_base_units, "2");
        assert_eq!(statement.entries[0].status, "confirmed");
        assert_eq!(statement.entries[0].block_height, 1);
        assert_eq!(
            statement.unsupported_fields,
            ACCOUNT_STATEMENT_UNSUPPORTED_FIELDS
        );
    }

    #[test]
    fn account_statement_direction_mapping_is_explicit() {
        assert_eq!(statement_direction("sent"), "debit");
        assert_eq!(statement_direction("received"), "credit");
        assert_eq!(statement_direction("self"), "self");
        assert_eq!(statement_direction("not-a-direction"), "unknown");
    }

    #[test]
    fn short_message_ids_are_stable() {
        assert_eq!(short_hash(TX_HASH), "fceb9425");
        assert_eq!(
            statement_message_id("xriqdev1bobbb00000000000", None),
            "iso-statement-bobbb-0000"
        );
    }
}
