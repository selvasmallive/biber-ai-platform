use std::fmt;

use crate::{IndexedChainSnapshot, IndexedReadModel};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PostgresWritePlan {
    pub run_id: String,
    pub statements: Vec<String>,
}

impl PostgresWritePlan {
    pub fn to_sql(&self) -> String {
        let mut output = String::new();
        output.push_str("-- XRIQ private-devnet indexer write plan.\n");
        output.push_str("-- Local prototype only; review before applying to any database.\n");
        output.push_str("BEGIN;\n\n");
        for statement in &self.statements {
            output.push_str(statement);
            output.push_str("\n\n");
        }
        output.push_str("COMMIT;");
        output
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PostgresWritePlanError {
    InvalidNumeric { field: &'static str, value: String },
}

impl fmt::Display for PostgresWritePlanError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidNumeric { field, value } => {
                write!(formatter, "invalid numeric value for {field}: {value}")
            }
        }
    }
}

pub fn postgres_write_plan(
    snapshot: &IndexedChainSnapshot,
) -> Result<PostgresWritePlan, PostgresWritePlanError> {
    let run_id = format!(
        "private-devnet-replay-{}-{}",
        snapshot.current_height, snapshot.latest_block_hash
    );
    let mut statements = Vec::new();
    push_indexer_run_statement(snapshot, &run_id, &mut statements);
    push_snapshot_statement(snapshot, &mut statements);
    push_account_statements(&snapshot.read_model, &mut statements);
    push_block_statements(&snapshot.read_model, &mut statements);
    push_transaction_statements(&snapshot.read_model, &mut statements)?;
    push_account_balance_statements(&snapshot.read_model, &mut statements)?;
    push_account_transaction_statements(&snapshot.read_model, &mut statements)?;
    push_audit_event_statements(&snapshot.read_model, &mut statements);
    Ok(PostgresWritePlan { run_id, statements })
}

fn push_indexer_run_statement(
    snapshot: &IndexedChainSnapshot,
    run_id: &str,
    statements: &mut Vec<String>,
) {
    statements.push(format!(
        "INSERT INTO xriq_indexer_runs \
         (run_id, started_at, completed_at, status, from_height, to_height, blocks_indexed, transactions_indexed, error)\n\
         VALUES ({run_id}, now(), now(), 'completed', {from_height}, {to_height}, {blocks}, {transactions}, NULL)\n\
         ON CONFLICT (run_id) DO UPDATE SET\n\
         completed_at = EXCLUDED.completed_at,\n\
         status = EXCLUDED.status,\n\
         from_height = EXCLUDED.from_height,\n\
         to_height = EXCLUDED.to_height,\n\
         blocks_indexed = EXCLUDED.blocks_indexed,\n\
         transactions_indexed = EXCLUDED.transactions_indexed,\n\
         error = NULL;",
        run_id = sql_text(run_id),
        from_height = sql_optional_u64(snapshot.summary.from_height),
        to_height = sql_optional_u64(snapshot.summary.to_height),
        blocks = snapshot.summary.blocks_indexed,
        transactions = snapshot.summary.transactions_indexed,
    ));
}

fn push_snapshot_statement(snapshot: &IndexedChainSnapshot, statements: &mut Vec<String>) {
    statements.push(format!(
        "INSERT INTO xriq_snapshots \
         (snapshot_name, snapshot_dir, chain_id, current_height, latest_block_hash, state_root, pending_transactions, created_at)\n\
         VALUES ('current-indexed-chain', 'read-model://current-indexed-chain', {chain_id}, {current_height}, {latest_block_hash}, {state_root}, 0, now())\n\
         ON CONFLICT (snapshot_name) DO UPDATE SET\n\
         snapshot_dir = EXCLUDED.snapshot_dir,\n\
         chain_id = EXCLUDED.chain_id,\n\
         current_height = EXCLUDED.current_height,\n\
         latest_block_hash = EXCLUDED.latest_block_hash,\n\
         state_root = EXCLUDED.state_root,\n\
         pending_transactions = EXCLUDED.pending_transactions,\n\
         created_at = EXCLUDED.created_at,\n\
         indexed_at = now();",
        chain_id = sql_text(&snapshot.chain_id),
        current_height = snapshot.current_height,
        latest_block_hash = sql_text(&snapshot.latest_block_hash),
        state_root = sql_text(&snapshot.state_root),
    ));
}

fn push_account_statements(model: &IndexedReadModel, statements: &mut Vec<String>) {
    for account in model.accounts.values() {
        statements.push(format!(
            "INSERT INTO xriq_accounts (address, first_seen_height, last_seen_height)\n\
             VALUES ({address}, {first_seen}, {last_seen})\n\
             ON CONFLICT (address) DO UPDATE SET\n\
             first_seen_height = EXCLUDED.first_seen_height,\n\
             last_seen_height = EXCLUDED.last_seen_height,\n\
             updated_at = now();",
            address = sql_text(&account.address),
            first_seen = sql_optional_u64(account.first_seen_height),
            last_seen = sql_optional_u64(account.last_seen_height),
        ));
    }
}

fn push_block_statements(model: &IndexedReadModel, statements: &mut Vec<String>) {
    for block in model.blocks.values() {
        statements.push(format!(
            "INSERT INTO xriq_blocks \
             (height, block_hash, previous_block_hash, state_root, transactions_root, transaction_count, timestamp_utc)\n\
             VALUES ({height}, {block_hash}, {previous_block_hash}, {state_root}, {transactions_root}, {transaction_count}, to_timestamp({timestamp_ms}::double precision / 1000.0))\n\
             ON CONFLICT (height) DO UPDATE SET\n\
             block_hash = EXCLUDED.block_hash,\n\
             previous_block_hash = EXCLUDED.previous_block_hash,\n\
             state_root = EXCLUDED.state_root,\n\
             transactions_root = EXCLUDED.transactions_root,\n\
             transaction_count = EXCLUDED.transaction_count,\n\
             timestamp_utc = EXCLUDED.timestamp_utc;",
            height = block.height,
            block_hash = sql_text(&block.block_hash),
            previous_block_hash = sql_text(&block.previous_block_hash),
            state_root = sql_text(&block.state_root),
            transactions_root = sql_text(&block.transactions_root),
            transaction_count = block.transaction_count,
            timestamp_ms = block.timestamp_ms,
        ));
    }
}

fn push_transaction_statements(
    model: &IndexedReadModel,
    statements: &mut Vec<String>,
) -> Result<(), PostgresWritePlanError> {
    for transaction in model.transactions.values() {
        let amount = sql_numeric(
            "xriq_transactions.amount_base_units",
            &transaction.amount_base_units,
        )?;
        let fee = sql_numeric(
            "xriq_transactions.fee_base_units",
            &transaction.fee_base_units,
        )?;
        statements.push(format!(
            "INSERT INTO xriq_transactions \
             (tx_hash, block_height, block_hash, transaction_index, status, from_address, to_address, amount_base_units, fee_base_units, nonce)\n\
             VALUES ({tx_hash}, {block_height}, {block_hash}, {transaction_index}, {status}, {from_address}, {to_address}, {amount}, {fee}, {nonce})\n\
             ON CONFLICT (tx_hash) DO UPDATE SET\n\
             block_height = EXCLUDED.block_height,\n\
             block_hash = EXCLUDED.block_hash,\n\
             transaction_index = EXCLUDED.transaction_index,\n\
             status = EXCLUDED.status,\n\
             from_address = EXCLUDED.from_address,\n\
             to_address = EXCLUDED.to_address,\n\
             amount_base_units = EXCLUDED.amount_base_units,\n\
             fee_base_units = EXCLUDED.fee_base_units,\n\
             nonce = EXCLUDED.nonce;",
            tx_hash = sql_text(&transaction.tx_hash),
            block_height = transaction.block_height,
            block_hash = sql_text(&transaction.block_hash),
            transaction_index = transaction.transaction_index,
            status = sql_text(transaction.status),
            from_address = sql_text(&transaction.from_address),
            to_address = sql_text(&transaction.to_address),
            amount = amount,
            fee = fee,
            nonce = transaction.nonce,
        ));
    }
    Ok(())
}

fn push_account_balance_statements(
    model: &IndexedReadModel,
    statements: &mut Vec<String>,
) -> Result<(), PostgresWritePlanError> {
    for balance in model.account_balances.values() {
        let amount = sql_numeric(
            "xriq_account_balances.balance_base_units",
            &balance.balance_base_units,
        )?;
        statements.push(format!(
            "INSERT INTO xriq_account_balances \
             (address, balance_base_units, nonce, height, state_root)\n\
             VALUES ({address}, {balance_base_units}, {nonce}, {height}, {state_root})\n\
             ON CONFLICT (address) DO UPDATE SET\n\
             balance_base_units = EXCLUDED.balance_base_units,\n\
             nonce = EXCLUDED.nonce,\n\
             height = EXCLUDED.height,\n\
             state_root = EXCLUDED.state_root,\n\
             updated_at = now();",
            address = sql_text(&balance.address),
            balance_base_units = amount,
            nonce = balance.nonce,
            height = balance.height,
            state_root = sql_text(&balance.state_root),
        ));
    }
    Ok(())
}

fn push_account_transaction_statements(
    model: &IndexedReadModel,
    statements: &mut Vec<String>,
) -> Result<(), PostgresWritePlanError> {
    for transaction in model.account_transactions.values() {
        let amount = sql_numeric(
            "xriq_account_transactions.amount_base_units",
            &transaction.amount_base_units,
        )?;
        let fee = sql_numeric(
            "xriq_account_transactions.fee_base_units",
            &transaction.fee_base_units,
        )?;
        statements.push(format!(
            "INSERT INTO xriq_account_transactions \
             (address, tx_hash, direction, block_height, transaction_index, amount_base_units, fee_base_units)\n\
             VALUES ({address}, {tx_hash}, {direction}, {block_height}, {transaction_index}, {amount}, {fee})\n\
             ON CONFLICT (address, tx_hash, direction) DO UPDATE SET\n\
             block_height = EXCLUDED.block_height,\n\
             transaction_index = EXCLUDED.transaction_index,\n\
             amount_base_units = EXCLUDED.amount_base_units,\n\
             fee_base_units = EXCLUDED.fee_base_units;",
            address = sql_text(&transaction.address),
            tx_hash = sql_text(&transaction.tx_hash),
            direction = sql_text(transaction.direction),
            block_height = transaction.block_height,
            transaction_index = transaction.transaction_index,
            amount = amount,
            fee = fee,
        ));
    }
    Ok(())
}

fn push_audit_event_statements(model: &IndexedReadModel, statements: &mut Vec<String>) {
    for event in model.audit_events.values() {
        statements.push(format!(
            "INSERT INTO xriq_audit_events \
             (event_id, actor, action, resource_type, resource_id, environment, metadata_json)\n\
             VALUES ({event_id}, {actor}, {action}, {resource_type}, {resource_id}, {environment}, NULL)\n\
             ON CONFLICT (event_id) DO NOTHING;",
            event_id = sql_text(&event.event_id),
            actor = sql_text(event.actor),
            action = sql_text(event.action),
            resource_type = sql_text(event.resource_type),
            resource_id = sql_optional_text(event.resource_id.as_deref()),
            environment = sql_text(event.environment),
        ));
    }
}

fn sql_text(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    output.push('\'');
    for character in value.chars() {
        if character == '\'' {
            output.push_str("''");
        } else {
            output.push(character);
        }
    }
    output.push('\'');
    output
}

fn sql_optional_text(value: Option<&str>) -> String {
    value.map(sql_text).unwrap_or_else(|| "NULL".to_string())
}

fn sql_optional_u64(value: Option<u64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "NULL".to_string())
}

fn sql_numeric(field: &'static str, value: &str) -> Result<String, PostgresWritePlanError> {
    if value.is_empty() || !value.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err(PostgresWritePlanError::InvalidNumeric {
            field,
            value: value.to_string(),
        });
    }
    Ok(value.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        index_private_devnet_store, private_devnet_indexer_genesis, IndexedAccountTransaction,
        XriqAmount,
    };
    use xriq_core::{Address, Block, BlockHeader, Hash32, SignatureBytes, Transaction};
    use xriq_crypto::{
        account_state_root, block_header_signing_hash, test_only_signature_for_hash,
        transaction_signing_hash, transactions_root,
    };
    use xriq_ledger::LedgerState;
    use xriq_storage::{ChainStore, InMemoryChainStore};

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn signed_transaction() -> Transaction {
        let mut transaction = Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from: address("alice"),
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(25),
            fee: XriqAmount::from_base_units(2),
            nonce: 0,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(Vec::new()),
            public_key: Vec::new(),
        };
        transaction.signature =
            test_only_signature_for_hash(transaction_signing_hash(&transaction));
        transaction
    }

    fn snapshot() -> crate::IndexedChainSnapshot {
        let genesis = private_devnet_indexer_genesis(Some(XriqAmount::from_base_units(100)));
        let transaction = signed_transaction();
        let mut ledger = LedgerState::from_genesis(&genesis).unwrap();
        ledger.apply_transaction(&transaction).unwrap();
        let mut header = BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            height: 1,
            previous_block_hash: Hash32::ZERO,
            state_root: account_state_root(&ledger.state_root_entries()),
            transactions_root: transactions_root(std::slice::from_ref(&transaction)),
            timestamp_ms: 1_001,
            producer: genesis.authority,
            consensus_round: 0,
            signature: SignatureBytes::new(Vec::new()),
            public_key: Vec::new(),
        };
        header.signature = test_only_signature_for_hash(block_header_signing_hash(&header));
        let mut store = InMemoryChainStore::new();
        store
            .append_block_with_canonical_hash(Block {
                header,
                transactions: vec![transaction],
            })
            .unwrap();
        index_private_devnet_store(&store, Some(XriqAmount::from_base_units(100))).unwrap()
    }

    #[test]
    fn renders_idempotent_postgres_write_plan_in_fk_order() {
        let snapshot = snapshot();

        let plan = postgres_write_plan(&snapshot).unwrap();
        let sql = plan.to_sql();

        assert!(sql.starts_with("-- XRIQ private-devnet indexer write plan."));
        assert!(sql.contains("BEGIN;"));
        assert!(sql.ends_with("COMMIT;"));
        assert!(sql.contains("INSERT INTO xriq_indexer_runs"));
        assert!(sql.contains("INSERT INTO xriq_snapshots"));
        assert!(sql.contains("current-indexed-chain"));
        assert!(sql.contains("read-model://current-indexed-chain"));
        assert!(sql.contains("INSERT INTO xriq_blocks"));
        assert!(sql.contains("INSERT INTO xriq_transactions"));
        assert!(sql.contains("INSERT INTO xriq_account_balances"));
        assert!(sql.contains("ON CONFLICT (tx_hash) DO UPDATE SET"));
        assert!(sql.contains("private-devnet-replay-1-"));
        assert_eq!(plan.statements.len(), 13);

        let snapshots_index = sql.find("INSERT INTO xriq_snapshots").unwrap();
        let accounts_index = sql.find("INSERT INTO xriq_accounts").unwrap();
        let blocks_index = sql.find("INSERT INTO xriq_blocks").unwrap();
        let transactions_index = sql.find("INSERT INTO xriq_transactions").unwrap();
        let balances_index = sql.find("INSERT INTO xriq_account_balances").unwrap();
        let account_transactions_index = sql.find("INSERT INTO xriq_account_transactions").unwrap();
        assert!(snapshots_index < accounts_index);
        assert!(accounts_index < balances_index);
        assert!(blocks_index < transactions_index);
        assert!(transactions_index < account_transactions_index);
    }

    #[test]
    fn escapes_sql_text_literals() {
        assert_eq!(sql_text("xriq's test"), "'xriq''s test'");
        assert_eq!(sql_optional_text(None), "NULL");
    }

    #[test]
    fn rejects_non_numeric_amounts() {
        let mut snapshot = snapshot();
        let key = snapshot
            .read_model
            .account_transactions
            .keys()
            .next()
            .cloned()
            .unwrap();
        snapshot.read_model.account_transactions.insert(
            key,
            IndexedAccountTransaction {
                address: "xriqdev1alice00000000000".to_string(),
                tx_hash: "a".repeat(64),
                direction: "sent",
                block_height: 1,
                transaction_index: 0,
                amount_base_units: "25.5".to_string(),
                fee_base_units: "2".to_string(),
            },
        );

        assert!(matches!(
            postgres_write_plan(&snapshot),
            Err(PostgresWritePlanError::InvalidNumeric { .. })
        ));
    }
}
