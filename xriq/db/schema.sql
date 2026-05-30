-- XRIQ Phase 1.1 PostgreSQL read model schema.
-- Private-devnet/local prototype only. This schema is an indexed read model,
-- not consensus state, custody infrastructure, or a production payment ledger.

CREATE TABLE IF NOT EXISTS xriq_blocks (
    height BIGINT PRIMARY KEY,
    block_hash TEXT NOT NULL UNIQUE,
    previous_block_hash TEXT NOT NULL,
    state_root TEXT NOT NULL,
    transactions_root TEXT NOT NULL,
    transaction_count INTEGER NOT NULL CHECK (transaction_count >= 0),
    timestamp_utc TIMESTAMPTZ NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_blocks_hash ON xriq_blocks (block_hash);
CREATE INDEX IF NOT EXISTS idx_xriq_blocks_indexed_at ON xriq_blocks (indexed_at);

CREATE TABLE IF NOT EXISTS xriq_transactions (
    tx_hash TEXT PRIMARY KEY,
    block_height BIGINT NULL REFERENCES xriq_blocks(height),
    block_hash TEXT NULL,
    transaction_index INTEGER NULL CHECK (transaction_index IS NULL OR transaction_index >= 0),
    status TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount_base_units NUMERIC(78, 0) NOT NULL CHECK (amount_base_units >= 0),
    fee_base_units NUMERIC(78, 0) NOT NULL CHECK (fee_base_units >= 0),
    nonce BIGINT NOT NULL CHECK (nonce >= 0),
    created_at TIMESTAMPTZ NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_transactions_block_height
    ON xriq_transactions (block_height, transaction_index);
CREATE INDEX IF NOT EXISTS idx_xriq_transactions_from_address
    ON xriq_transactions (from_address);
CREATE INDEX IF NOT EXISTS idx_xriq_transactions_to_address
    ON xriq_transactions (to_address);
CREATE INDEX IF NOT EXISTS idx_xriq_transactions_status
    ON xriq_transactions (status);

CREATE TABLE IF NOT EXISTS xriq_accounts (
    address TEXT PRIMARY KEY,
    first_seen_height BIGINT NULL,
    last_seen_height BIGINT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_accounts_last_seen_height
    ON xriq_accounts (last_seen_height);

CREATE TABLE IF NOT EXISTS xriq_account_balances (
    address TEXT PRIMARY KEY REFERENCES xriq_accounts(address),
    balance_base_units NUMERIC(78, 0) NOT NULL CHECK (balance_base_units >= 0),
    nonce BIGINT NOT NULL CHECK (nonce >= 0),
    height BIGINT NOT NULL,
    state_root TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_account_balances_height
    ON xriq_account_balances (height);

CREATE TABLE IF NOT EXISTS xriq_account_transactions (
    address TEXT NOT NULL REFERENCES xriq_accounts(address),
    tx_hash TEXT NOT NULL REFERENCES xriq_transactions(tx_hash),
    direction TEXT NOT NULL,
    block_height BIGINT NULL,
    transaction_index INTEGER NULL CHECK (transaction_index IS NULL OR transaction_index >= 0),
    amount_base_units NUMERIC(78, 0) NOT NULL CHECK (amount_base_units >= 0),
    fee_base_units NUMERIC(78, 0) NOT NULL CHECK (fee_base_units >= 0),
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (address, tx_hash, direction)
);

CREATE INDEX IF NOT EXISTS idx_xriq_account_transactions_address_height
    ON xriq_account_transactions (address, block_height DESC, transaction_index DESC);

CREATE TABLE IF NOT EXISTS xriq_mempool_entries (
    tx_hash TEXT PRIMARY KEY,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount_base_units NUMERIC(78, 0) NOT NULL CHECK (amount_base_units >= 0),
    fee_base_units NUMERIC(78, 0) NOT NULL CHECK (fee_base_units >= 0),
    nonce BIGINT NOT NULL CHECK (nonce >= 0),
    status TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_mempool_entries_sender_nonce
    ON xriq_mempool_entries (from_address, nonce);
CREATE INDEX IF NOT EXISTS idx_xriq_mempool_entries_last_seen_at
    ON xriq_mempool_entries (last_seen_at);

CREATE TABLE IF NOT EXISTS xriq_snapshots (
    snapshot_name TEXT PRIMARY KEY,
    snapshot_dir TEXT NOT NULL,
    chain_id TEXT NOT NULL,
    current_height BIGINT NOT NULL CHECK (current_height >= 0),
    latest_block_hash TEXT NOT NULL,
    state_root TEXT NOT NULL,
    pending_transactions INTEGER NOT NULL CHECK (pending_transactions >= 0),
    created_at TIMESTAMPTZ NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_snapshots_height
    ON xriq_snapshots (current_height DESC);

CREATE TABLE IF NOT EXISTS xriq_indexer_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    from_height BIGINT NULL,
    to_height BIGINT NULL,
    blocks_indexed INTEGER NOT NULL DEFAULT 0 CHECK (blocks_indexed >= 0),
    transactions_indexed INTEGER NOT NULL DEFAULT 0 CHECK (transactions_indexed >= 0),
    error TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_xriq_indexer_runs_started_at
    ON xriq_indexer_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS xriq_audit_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NULL,
    environment TEXT NOT NULL,
    metadata_json TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_xriq_audit_events_occurred_at
    ON xriq_audit_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_xriq_audit_events_action
    ON xriq_audit_events (action);

CREATE TABLE IF NOT EXISTS xriq_iso20022_messages (
    message_id TEXT PRIMARY KEY,
    tx_hash TEXT NULL,
    account_address TEXT NULL,
    message_type TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    environment TEXT NOT NULL,
    not_certified BOOLEAN NOT NULL DEFAULT TRUE,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xriq_iso20022_messages_tx_hash
    ON xriq_iso20022_messages (tx_hash);
CREATE INDEX IF NOT EXISTS idx_xriq_iso20022_messages_account
    ON xriq_iso20022_messages (account_address);
CREATE INDEX IF NOT EXISTS idx_xriq_iso20022_messages_type_created
    ON xriq_iso20022_messages (message_type, created_at DESC);
