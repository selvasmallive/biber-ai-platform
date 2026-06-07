export const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_XRIQ_API_BASE_URL ?? "";

export interface HealthResponse {
  ok: boolean;
  network: string;
  environment: "private-devnet";
  service: string;
  version: string;
}

export interface NetworkResponse {
  environment: "private-devnet";
  network: string;
  current_height: number;
  latest_block_hash: string;
  state_root: string;
}

export interface ExplorerOverviewResponse {
  environment: "private-devnet";
  network: string;
  chain: {
    current_height: number;
    latest_block_hash: string;
    state_root: string;
    stored_blocks: number;
    pending_transactions: number;
  };
  indexer: IndexerStatusResponse;
  totals: {
    blocks: number;
    transactions: number;
    accounts: number;
  };
}

export interface BlockSummary {
  height: number;
  block_hash: string;
  previous_block_hash: string;
  state_root: string;
  transactions_root: string;
  transaction_count: number;
  timestamp_utc: string;
}

export interface BlockListResponse {
  environment: "private-devnet";
  network: string;
  limit: number;
  next_cursor: string | null;
  blocks: BlockSummary[];
}

export interface BlockDetailResponse extends BlockSummary {
  environment: "private-devnet";
  network: string;
  transactions: TransactionSummary[];
}

export interface TransactionSummary {
  tx_hash: string;
  block_height: number;
  block_hash: string;
  transaction_index: number;
  status: string;
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: number;
}

export interface TransactionListResponse {
  environment: "private-devnet";
  network: string;
  limit: number;
  next_cursor: string | null;
  transactions: TransactionSummary[];
}

export interface TransactionDetailResponse extends TransactionSummary {
  environment: "private-devnet";
  network: string;
}

export interface AccountSummary {
  address: string;
  balance_base_units: string;
  nonce: number;
  height: number;
  state_root: string;
  first_seen_height: number | null;
  last_seen_height: number | null;
}

export interface AccountListResponse {
  environment: "private-devnet";
  network: string;
  limit: number;
  next_cursor: string | null;
  accounts: AccountSummary[];
}

export interface AccountDetailResponse extends AccountSummary {
  environment: "private-devnet";
  network: string;
}

export interface AccountTransaction {
  address: string;
  tx_hash: string;
  direction: string;
  block_height: number;
  transaction_index: number;
  amount_base_units: string;
  fee_base_units: string;
}

export interface AccountHistoryResponse {
  environment: "private-devnet";
  network: string;
  address: string;
  limit: number;
  next_cursor: string | null;
  transactions: AccountTransaction[];
}

export interface IndexerStatusResponse {
  environment: "private-devnet";
  service: string;
  status: string;
  latest_indexed_height: number;
  latest_indexed_block_hash: string;
  lag_blocks: number;
  last_run: {
    run_id: string;
    status: string;
    from_height: number | null;
    to_height: number | null;
    blocks_indexed: number;
    transactions_indexed: number;
  };
}

export interface NodeStatusResponse {
  environment: "private-devnet";
  service: string;
  status: string;
  mode: string;
  source: string;
  network: string;
  current_height: number;
  latest_block_hash: string;
  state_root: string;
  stored_blocks: number;
  pending_transactions: number;
  wallet_submit_status: string;
  block_production_status: string;
}

export interface PostgresReadModelStatusResponse {
  environment: "private-devnet";
  service: string;
  source: "postgres-read-model";
  warning: string;
  route: string;
  container: string;
  database: string;
  status: string;
  read_only: boolean;
  indexer_status: string;
  latest_height: number | null;
  latest_block_hash: string | null;
  counts: {
    blocks: number;
    transactions: number;
    accounts: number;
    account_balances: number;
    account_transactions: number;
    audit_events: number;
    indexer_runs: number;
  };
}

export interface ExplorerSnapshot {
  loadedAt: string;
  health: HealthResponse;
  network: NetworkResponse;
  overview: ExplorerOverviewResponse;
  blocks: BlockListResponse;
  transactions: TransactionListResponse;
  mempool: MempoolResponse;
  accounts: AccountListResponse;
  nodeStatus: NodeStatusResponse;
  indexer: IndexerStatusResponse;
  walletStatus: WalletStatusResponse;
  auditEvents: AdminAuditEventsResponse;
  snapshots: SnapshotListResponse;
}

export interface WalletStatusResponse {
  environment: "private-devnet";
  network: string;
  warning: string;
  current_height: number;
  latest_block_hash: string;
  state_root: string;
  account_count: number;
  pending_transactions: number;
  capabilities: {
    draft: boolean;
    submit: boolean;
    send: boolean;
  };
}

export interface WalletBalanceResponse {
  environment: "private-devnet";
  network: string;
  warning: string;
  address: string;
  balance_base_units: string;
  nonce: number;
  height: number;
  state_root: string;
}

export interface WalletTransactionStatusResponse {
  environment: "private-devnet";
  network: string;
  warning: string;
  tx_hash: string;
  status: string;
  block_height: number | null;
  block_hash: string | null;
  transaction_index: number | null;
}

export interface WalletDraftPreviewRequest {
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: string;
  expires_at_height: string;
}

export interface WalletDraftPreviewResponse {
  environment: "private-devnet";
  network: string;
  warning: string;
  mutation: "none";
  validation: {
    ok: boolean;
    errors: string[];
  };
  draft: {
    chain_id: string;
    from_address: string;
    to_address: string;
    amount_base_units: string;
    fee_base_units: string;
    nonce: number;
    expires_at_height: number | null;
  };
  balance: {
    available_base_units: string | null;
    debit_base_units: string | null;
    remaining_base_units: string | null;
  };
}

export type WalletMutationAction = "submit" | "send";

export const WALLET_SUBMIT_REFUSAL_ENDPOINT =
  "POST /api/v1/wallet/transfers/submit";
export const WALLET_SEND_REFUSAL_ENDPOINT =
  "POST /api/v1/wallet/transfers/send";
const WALLET_SEND_REFUSAL_PATH = "/api/v1/wallet/transfers/send";
export const BLOCK_PRODUCTION_REFUSAL_ENDPOINT = "POST /api/v1/blocks/produce";
const BLOCK_PRODUCTION_REFUSAL_PATH = "/api/v1/blocks/produce";
export const LOCAL_WALLET_SUBMIT_ACCEPTED_CODE =
  "wallet_submit_accepted_local_only";
export const LOCAL_WALLET_SUBMIT_ACCEPTED_MUTATION = "pending_state_only";
export const LOCAL_WALLET_SEND_ACCEPTED_CODE =
  "wallet_send_accepted_local_only";
export const LOCAL_WALLET_SEND_ACCEPTED_MUTATION = "pending_state_only";
export const LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE =
  "block_production_accepted_local_only";
export const LOCAL_BLOCK_PRODUCTION_ACCEPTED_AUDIT_SCOPE = "api-local-accepted";
export const LOCAL_BLOCK_PRODUCTION_ACCEPTED_MUTATION =
  "chain_and_pending_state_local_only";

export interface LocalMutationRefusalResponse {
  environment: "private-devnet";
  network: string;
  endpoint: string;
  enabled: false;
  mutation: "none";
  status: "disabled";
  code: string;
  error: string;
  warning: string;
  required_enablement: {
    mode: "local-private-devnet";
    explicit_flag: string;
    audit_event_required: boolean;
    test_identity_only: boolean;
  };
  request_fields: string[];
  refusal_guards: string[];
}

export type WalletMutationRefusalResponse = LocalMutationRefusalResponse;

export interface LocalWalletSubmitPendingTransaction {
  tx_hash: string;
  status: "pending";
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: number;
  expires_at_height: number;
  block_height: null;
  transaction_index: null;
}

export interface LocalWalletSubmitAcceptedResponse {
  environment: "private-devnet";
  network: "xriq-devnet";
  endpoint: typeof WALLET_SUBMIT_REFUSAL_ENDPOINT;
  code: typeof LOCAL_WALLET_SUBMIT_ACCEPTED_CODE;
  status: "pending";
  mutation: typeof LOCAL_WALLET_SUBMIT_ACCEPTED_MUTATION;
  warning: "local-private-devnet-only";
  transaction: LocalWalletSubmitPendingTransaction;
  pending_state: {
    before_count: number;
    after_count: number;
    added_tx_hash: string;
    pending_file: string;
  };
  chain_state: {
    current_height: number;
    latest_block_hash: string;
    chain_file: string;
    chain_unchanged: true;
  };
  audit_event_recorded: boolean;
  audit_event: {
    event_id: string;
    actor: "local-private-devnet-operator";
    action: "wallet_transfer_submit_attempt";
    resource_type: "wallet_transfer";
    resource_id: string;
    environment: "private-devnet";
    metadata: {
      endpoint: typeof WALLET_SUBMIT_REFUSAL_ENDPOINT;
      outcome: "accepted";
      status: "pending";
      explicit_flag: "--enable-local-wallet-submit";
      local_request_id: string;
      draft_id: string;
      from_address: string;
      to_address: string;
      amount_base_units: string;
      fee_base_units: string;
      nonce: number;
      expires_at_height: number;
      pending_before_count: number;
      pending_after_count: number;
      added_tx_hash: string;
      chain_current_height: number;
      metadata_policy: string;
    };
  };
}

export interface LocalWalletSubmitAcceptedExpectations {
  localRequestId?: string;
  draftId?: string;
  pendingFile?: string;
  chainFile?: string;
  fromAddress?: string;
  toAddress?: string;
}

export interface LocalWalletSendPendingTransaction {
  tx_hash: string;
  status: "pending";
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: number;
  expires_at_height: number;
  block_height: null;
  transaction_index: null;
}

export interface LocalWalletSendAcceptedResponse {
  environment: "private-devnet";
  network: "xriq-devnet";
  endpoint: typeof WALLET_SEND_REFUSAL_ENDPOINT;
  code: typeof LOCAL_WALLET_SEND_ACCEPTED_CODE;
  status: "pending";
  mutation: typeof LOCAL_WALLET_SEND_ACCEPTED_MUTATION;
  warning: "local-private-devnet-only";
  transaction: LocalWalletSendPendingTransaction;
  pending_state: {
    before_count: number;
    after_count: number;
    added_tx_hash: string;
    pending_file: string;
  };
  chain_state: {
    current_height: number;
    latest_block_hash: string;
    chain_file: string;
    chain_unchanged: true;
  };
  audit_event_recorded: boolean;
  audit_event: {
    event_id: string;
    actor: "local-private-devnet-operator";
    action: "wallet_transfer_send_attempt";
    resource_type: "wallet_transfer";
    resource_id: string;
    environment: "private-devnet";
    metadata: {
      endpoint: typeof WALLET_SEND_REFUSAL_ENDPOINT;
      outcome: "accepted";
      status: "pending";
      explicit_flag: "--enable-local-wallet-send";
      local_request_id: string;
      from_address: string;
      to_address: string;
      amount_base_units: string;
      fee_base_units: string;
      nonce: number;
      expires_at_height: number;
      pending_before_count: number;
      pending_after_count: number;
      added_tx_hash: string;
      chain_current_height: number;
      metadata_policy: string;
    };
  };
}

export interface LocalWalletSendAcceptedExpectations {
  localRequestId?: string;
  pendingFile?: string;
  chainFile?: string;
  fromAddress?: string;
  toAddress?: string;
}

export interface LocalWalletSendRequest {
  local_request_id: string;
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: string;
  expires_at_height: string;
}

export interface LocalBlockProductionRequest {
  local_request_id: string;
  producer: string;
  max_transactions: string;
  timestamp_ms: string;
  consensus_round?: string;
}

export interface LocalBlockProductionConfirmedTransaction {
  tx_hash: string;
  status: "confirmed";
  block_height: number;
  block_hash: string;
  transaction_index: number;
}

export interface LocalBlockProductionAcceptedResponse {
  environment: "private-devnet";
  network: "xriq-devnet";
  endpoint: typeof BLOCK_PRODUCTION_REFUSAL_ENDPOINT;
  code: typeof LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE;
  status: "confirmed";
  mutation: typeof LOCAL_BLOCK_PRODUCTION_ACCEPTED_MUTATION;
  warning: "local-private-devnet-only";
  block: BlockSummary;
  confirmed_transactions: LocalBlockProductionConfirmedTransaction[];
  pending_state: {
    before_count: number;
    after_count: number;
    removed_tx_hashes: string[];
    pending_file: string;
  };
  chain_state: {
    previous_height: number;
    current_height: number;
    chain_file: string;
  };
  audit_scope: typeof LOCAL_BLOCK_PRODUCTION_ACCEPTED_AUDIT_SCOPE;
  audit_event_recorded: boolean;
  audit_event: {
    event_id: string;
    actor: "local-private-devnet-operator";
    action: "block_production_attempt";
    resource_type: "block_production";
    resource_id: string;
    environment: "private-devnet";
    metadata: {
      endpoint: typeof BLOCK_PRODUCTION_REFUSAL_ENDPOINT;
      outcome: "accepted";
      status: "confirmed";
      explicit_flag: "--enable-local-block-production";
      local_request_id: string;
      producer: string;
      max_transactions: number;
      timestamp_ms: number;
      pending_before_count: number;
      pending_after_count: number;
      confirmed_transaction_count: number;
      chain_previous_height: number;
      chain_current_height: number;
      metadata_policy: string;
    };
  };
}

export interface LocalBlockProductionAcceptedExpectations {
  localRequestId?: string;
  pendingFile?: string;
  chainFile?: string;
  producer?: string;
  maxTransactions?: number;
}

export interface MempoolEntry {
  tx_hash: string;
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: number;
  status: string;
  first_seen_at_utc: string | null;
  last_seen_at_utc: string | null;
}

export interface MempoolResponse {
  environment: "private-devnet";
  network: string;
  warning: string;
  current_height: number;
  pending_count: number;
  limit: number;
  next_cursor: string | null;
  inspect_status: string;
  submit_status: string;
  produce_block_status: string;
  entries: MempoolEntry[];
}

export interface AdminAuditEvent {
  event_id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  environment: "private-devnet";
}

export interface LocalRefusalAuditEvent extends Omit<AdminAuditEvent, "resource_id"> {
  resource_id: string;
  audit_scope: string;
  recording: string;
  outcome: string;
  status: string;
  mutation: "none";
  metadata: {
    endpoint: string;
    refusal_code: string;
    explicit_flag: string;
    local_request_id: string;
    resource_id_policy: string;
    metadata_policy: string;
  };
}

export interface AdminAuditEventsResponse {
  environment: "private-devnet";
  network: string;
  limit: number;
  next_cursor: string | null;
  audit_events: AdminAuditEvent[];
  local_refusal_audit_count: number;
  local_refusal_audit_events: LocalRefusalAuditEvent[];
}

export interface SnapshotSummary {
  snapshot_name: string;
  snapshot_dir: string;
  current_height: number;
  latest_block_hash: string;
  state_root: string;
  block_count: number;
  transaction_count: number;
  audit_event_count: number;
  export_status: string;
  import_status: string;
}

export interface SnapshotListResponse {
  environment: "private-devnet";
  network: string;
  warning: string;
  snapshots: SnapshotSummary[];
}

export interface IsoTransferFields {
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: number;
}

export interface IsoPaymentInitiationPreviewResponse {
  environment: "private-devnet";
  not_certified: boolean;
  mapping_version: string;
  message_type: string;
  message_id: string;
  source_tx_hash: string;
  xriq: IsoTransferFields;
  iso20022_aligned: {
    creditor_account: string;
    debtor_account: string;
    instructed_amount: string;
    currency: string;
    end_to_end_id: string;
  };
  unsupported_fields: string[];
}

export interface IsoPaymentStatusPreviewResponse {
  environment: "private-devnet";
  not_certified: boolean;
  mapping_version: string;
  message_type: string;
  message_id: string;
  source_tx_hash: string;
  xriq_status: string;
  iso20022_aligned: {
    original_end_to_end_id: string;
    transaction_status: string;
    status_reason: string;
    confirmed_block_height: number | null;
  };
  unsupported_fields: string[];
}

export interface IsoAccountStatementPreviewResponse {
  environment: "private-devnet";
  not_certified: boolean;
  mapping_version: string;
  message_type: string;
  message_id: string;
  account_address: string;
  from: string;
  to: string;
  opening_balance_base_units: string;
  closing_balance_base_units: string;
  entries: Array<{
    tx_hash: string;
    direction: string;
    amount_base_units: string;
    fee_base_units: string;
    status: string;
    block_height: number;
  }>;
  unsupported_fields: string[];
}

export async function loadExplorerSnapshot(
  baseUrl: string,
): Promise<ExplorerSnapshot> {
  const cleanBaseUrl = normalizeBaseUrl(baseUrl);
  const [
    health,
    network,
    overview,
    blocks,
    transactions,
    mempool,
    accounts,
    nodeStatus,
    indexer,
    walletStatus,
    auditEvents,
    snapshots,
  ] = await Promise.all([
    fetchJson<HealthResponse>(cleanBaseUrl, "/api/v1/health"),
    fetchJson<NetworkResponse>(cleanBaseUrl, "/api/v1/network"),
    fetchJson<ExplorerOverviewResponse>(
      cleanBaseUrl,
      "/api/v1/explorer/overview",
    ),
    fetchJson<BlockListResponse>(cleanBaseUrl, "/api/v1/blocks?limit=5"),
    fetchJson<TransactionListResponse>(
      cleanBaseUrl,
      "/api/v1/transactions?limit=5",
    ),
    fetchJson<MempoolResponse>(cleanBaseUrl, "/api/v1/mempool?limit=5"),
    fetchJson<AccountListResponse>(cleanBaseUrl, "/api/v1/accounts?limit=5"),
    fetchJson<NodeStatusResponse>(
      cleanBaseUrl,
      "/api/v1/admin/node/status",
    ),
    fetchJson<IndexerStatusResponse>(
      cleanBaseUrl,
      "/api/v1/admin/indexer/status",
    ),
    fetchJson<WalletStatusResponse>(cleanBaseUrl, "/api/v1/wallet/status"),
    fetchJson<AdminAuditEventsResponse>(
      cleanBaseUrl,
      "/api/v1/admin/audit-events?limit=5",
    ),
    fetchJson<SnapshotListResponse>(cleanBaseUrl, "/api/v1/snapshots"),
  ]);

  return {
    loadedAt: new Date().toISOString(),
    health,
    network,
    overview,
    blocks,
    transactions,
    mempool,
    accounts,
    nodeStatus,
    indexer,
    walletStatus,
    auditEvents,
    snapshots,
  };
}

export async function loadBlockDetail(
  baseUrl: string,
  heightOrHash: string,
): Promise<BlockDetailResponse> {
  return fetchJson<BlockDetailResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/blocks/${encodeURIComponent(heightOrHash)}`,
  );
}

export async function loadTransactionDetail(
  baseUrl: string,
  txHash: string,
): Promise<TransactionDetailResponse> {
  return fetchJson<TransactionDetailResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/transactions/${encodeURIComponent(txHash)}`,
  );
}

export async function loadAccountDetail(
  baseUrl: string,
  address: string,
): Promise<AccountDetailResponse> {
  return fetchJson<AccountDetailResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/accounts/${encodeURIComponent(address)}`,
  );
}

export async function loadAccountHistory(
  baseUrl: string,
  address: string,
): Promise<AccountHistoryResponse> {
  return fetchJson<AccountHistoryResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/accounts/${encodeURIComponent(address)}/transactions?limit=5`,
  );
}

export async function loadWalletStatus(
  baseUrl: string,
): Promise<WalletStatusResponse> {
  return fetchJson<WalletStatusResponse>(
    normalizeBaseUrl(baseUrl),
    "/api/v1/wallet/status",
  );
}

export async function loadWalletBalance(
  baseUrl: string,
  address: string,
): Promise<WalletBalanceResponse> {
  return fetchJson<WalletBalanceResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/wallet/accounts/${encodeURIComponent(address)}/balance`,
  );
}

export async function loadWalletHistory(
  baseUrl: string,
  address: string,
): Promise<AccountHistoryResponse> {
  return fetchJson<AccountHistoryResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/wallet/accounts/${encodeURIComponent(address)}/history?limit=5`,
  );
}

export async function loadWalletTransactionStatus(
  baseUrl: string,
  txHash: string,
): Promise<WalletTransactionStatusResponse> {
  return fetchJson<WalletTransactionStatusResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/wallet/transactions/${encodeURIComponent(txHash)}/status`,
  );
}

export async function loadSnapshotDetail(
  baseUrl: string,
  snapshotName: string,
): Promise<SnapshotSummary> {
  return fetchJson<SnapshotSummary>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/snapshots/${encodeURIComponent(snapshotName)}`,
  );
}

export async function loadPostgresReadModelStatus(
  baseUrl: string,
): Promise<PostgresReadModelStatusResponse> {
  return fetchJson<PostgresReadModelStatusResponse>(
    normalizeBaseUrl(baseUrl),
    "/api/v1/admin/postgres/read-model-status",
  );
}

export async function loadWalletDraftPreview(
  baseUrl: string,
  request: WalletDraftPreviewRequest,
): Promise<WalletDraftPreviewResponse> {
  const params = new URLSearchParams({
    from_address: request.from_address,
    to_address: request.to_address,
    amount_base_units: request.amount_base_units,
    fee_base_units: request.fee_base_units,
    nonce: request.nonce,
  });
  if (request.expires_at_height.trim() !== "") {
    params.set("expires_at_height", request.expires_at_height.trim());
  }

  return fetchJson<WalletDraftPreviewResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/wallet/transfers/draft-preview?${params.toString()}`,
  );
}

export async function loadWalletMutationRefusal(
  baseUrl: string,
  action: WalletMutationAction,
): Promise<WalletMutationRefusalResponse> {
  const path =
    action === "submit"
      ? "/api/v1/wallet/transfers/submit"
      : WALLET_SEND_REFUSAL_PATH;
  return fetchJson<WalletMutationRefusalResponse>(normalizeBaseUrl(baseUrl), path, {
    method: "POST",
    acceptedStatuses: [403],
  });
}

export async function sendLocalWalletTransfer(
  baseUrl: string,
  request: LocalWalletSendRequest,
): Promise<LocalWalletSendAcceptedResponse> {
  const params = new URLSearchParams({
    local_request_id: request.local_request_id,
    from_address: request.from_address,
    to_address: request.to_address,
    amount_base_units: request.amount_base_units,
    fee_base_units: request.fee_base_units,
    nonce: request.nonce,
    expires_at_height: request.expires_at_height,
  });
  const data = await fetchJson<LocalWalletSendAcceptedResponse>(
    normalizeBaseUrl(baseUrl),
    `${WALLET_SEND_REFUSAL_PATH}?${params.toString()}`,
    {
      method: "POST",
      acceptedStatuses: [201],
    },
  );
  const errors = validateLocalWalletSendAcceptedContract(data, {
    localRequestId: request.local_request_id,
    fromAddress: request.from_address,
    toAddress: request.to_address,
  });
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
  return data;
}

export async function loadBlockProductionRefusal(
  baseUrl: string,
): Promise<LocalMutationRefusalResponse> {
  return fetchJson<LocalMutationRefusalResponse>(
    normalizeBaseUrl(baseUrl),
    BLOCK_PRODUCTION_REFUSAL_PATH,
    {
      method: "POST",
      acceptedStatuses: [403],
    },
  );
}

export async function produceLocalBlock(
  baseUrl: string,
  request: LocalBlockProductionRequest,
): Promise<LocalBlockProductionAcceptedResponse> {
  const params = new URLSearchParams({
    local_request_id: request.local_request_id,
    producer: request.producer,
    max_transactions: request.max_transactions,
    timestamp_ms: request.timestamp_ms,
  });
  if (request.consensus_round?.trim()) {
    params.set("consensus_round", request.consensus_round.trim());
  }
  const data = await fetchJson<LocalBlockProductionAcceptedResponse>(
    normalizeBaseUrl(baseUrl),
    `${BLOCK_PRODUCTION_REFUSAL_PATH}?${params.toString()}`,
    {
      method: "POST",
      acceptedStatuses: [201],
    },
  );
  const errors = validateLocalBlockProductionAcceptedContract(data, {
    localRequestId: request.local_request_id,
    producer: request.producer,
    maxTransactions: Number.parseInt(request.max_transactions, 10),
  });
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
  return data;
}

export function validateLocalBlockProductionAcceptedContract(
  data: LocalBlockProductionAcceptedResponse,
  expectations: LocalBlockProductionAcceptedExpectations = {},
): string[] {
  const errors: string[] = [];
  const expectedLocalRequestId = expectations.localRequestId;
  const expectedProducer =
    expectations.producer ?? "xriqdev1author00000000000";
  const expectedMaxTransactions = expectations.maxTransactions ?? 4;

  if (data.environment !== "private-devnet") {
    errors.push("environment must be private-devnet");
  }
  if (data.network !== "xriq-devnet") {
    errors.push("network must be xriq-devnet");
  }
  if (data.endpoint !== BLOCK_PRODUCTION_REFUSAL_ENDPOINT) {
    errors.push("block production accepted endpoint marker is missing");
  }
  if (data.code !== LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE) {
    errors.push(`code must be ${LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE}`);
  }
  if (data.status !== "confirmed") {
    errors.push("status must be confirmed");
  }
  if (data.mutation !== LOCAL_BLOCK_PRODUCTION_ACCEPTED_MUTATION) {
    errors.push(`mutation must be ${LOCAL_BLOCK_PRODUCTION_ACCEPTED_MUTATION}`);
  }
  if (data.warning !== "local-private-devnet-only") {
    errors.push("warning must be local-private-devnet-only");
  }
  if (data.audit_scope !== LOCAL_BLOCK_PRODUCTION_ACCEPTED_AUDIT_SCOPE) {
    errors.push(`audit_scope must be ${LOCAL_BLOCK_PRODUCTION_ACCEPTED_AUDIT_SCOPE}`);
  }
  if (!data.audit_event_recorded) {
    errors.push("audit_event_recorded must be true");
  }
  if (data.block.height !== data.chain_state.current_height) {
    errors.push("block height must match chain_state current_height");
  }
  if (data.chain_state.current_height !== data.chain_state.previous_height + 1) {
    errors.push("chain_state must advance exactly one block");
  }
  if (data.block.transaction_count !== data.confirmed_transactions.length) {
    errors.push("block transaction_count must match confirmed_transactions length");
  }
  if (data.pending_state.after_count > data.pending_state.before_count) {
    errors.push("pending after_count must not exceed before_count");
  }
  if (
    data.pending_state.removed_tx_hashes.length !==
    data.confirmed_transactions.length
  ) {
    errors.push("removed pending hashes must match confirmed transaction count");
  }
  for (const transaction of data.confirmed_transactions) {
    if (transaction.status !== "confirmed") {
      errors.push("confirmed transaction status must be confirmed");
    }
    if (transaction.block_height !== data.block.height) {
      errors.push("confirmed transaction block_height must match block height");
    }
    if (transaction.block_hash !== data.block.block_hash) {
      errors.push("confirmed transaction block_hash must match block hash");
    }
    if (!data.pending_state.removed_tx_hashes.includes(transaction.tx_hash)) {
      errors.push(`confirmed transaction was not removed from pending: ${transaction.tx_hash}`);
    }
  }
  if (expectations.pendingFile && data.pending_state.pending_file !== expectations.pendingFile) {
    errors.push("pending_file does not match expected local smoke file");
  }
  if (expectations.chainFile && data.chain_state.chain_file !== expectations.chainFile) {
    errors.push("chain_file does not match expected local smoke file");
  }

  const audit = data.audit_event;
  const metadata = audit.metadata;
  if (audit.actor !== "local-private-devnet-operator") {
    errors.push("audit actor must be local-private-devnet-operator");
  }
  if (audit.action !== "block_production_attempt") {
    errors.push("audit action must be block_production_attempt");
  }
  if (audit.resource_type !== "block_production") {
    errors.push("audit resource_type must be block_production");
  }
  if (audit.environment !== "private-devnet") {
    errors.push("audit environment must be private-devnet");
  }
  if (expectedLocalRequestId) {
    if (audit.resource_id !== expectedLocalRequestId) {
      errors.push("audit resource_id does not match expected local_request_id");
    }
    if (audit.event_id !== `block-production:${expectedLocalRequestId}`) {
      errors.push("audit event_id does not match expected local_request_id");
    }
    if (metadata.local_request_id !== expectedLocalRequestId) {
      errors.push("audit metadata local_request_id does not match expected value");
    }
  }
  if (metadata.endpoint !== BLOCK_PRODUCTION_REFUSAL_ENDPOINT) {
    errors.push("audit metadata endpoint marker is missing");
  }
  if (metadata.outcome !== "accepted") {
    errors.push("audit metadata outcome must be accepted");
  }
  if (metadata.status !== "confirmed") {
    errors.push("audit metadata status must be confirmed");
  }
  if (metadata.explicit_flag !== "--enable-local-block-production") {
    errors.push("audit metadata explicit flag is wrong");
  }
  if (metadata.producer !== expectedProducer) {
    errors.push("audit metadata producer is wrong");
  }
  if (metadata.max_transactions !== expectedMaxTransactions) {
    errors.push("audit metadata max_transactions is wrong");
  }
  if (metadata.pending_before_count !== data.pending_state.before_count) {
    errors.push("audit metadata pending_before_count must match pending_state");
  }
  if (metadata.pending_after_count !== data.pending_state.after_count) {
    errors.push("audit metadata pending_after_count must match pending_state");
  }
  if (metadata.confirmed_transaction_count !== data.confirmed_transactions.length) {
    errors.push("audit metadata confirmed_transaction_count must match response rows");
  }
  if (metadata.chain_previous_height !== data.chain_state.previous_height) {
    errors.push("audit metadata chain_previous_height must match chain_state");
  }
  if (metadata.chain_current_height !== data.chain_state.current_height) {
    errors.push("audit metadata chain_current_height must match chain_state");
  }
  if (!metadata.metadata_policy.includes("no signing material")) {
    errors.push("audit metadata policy must forbid signing material");
  }

  return errors;
}

export function validateLocalWalletSubmitAcceptedContract(
  data: LocalWalletSubmitAcceptedResponse,
  expectations: LocalWalletSubmitAcceptedExpectations = {},
): string[] {
  const errors: string[] = [];
  const expectedLocalRequestId = expectations.localRequestId;
  const transaction = data.transaction;
  const audit = data.audit_event;
  const metadata = audit.metadata;

  if (data.environment !== "private-devnet") {
    errors.push("environment must be private-devnet");
  }
  if (data.network !== "xriq-devnet") {
    errors.push("network must be xriq-devnet");
  }
  if (data.endpoint !== WALLET_SUBMIT_REFUSAL_ENDPOINT) {
    errors.push("wallet submit accepted endpoint marker is missing");
  }
  if (data.code !== LOCAL_WALLET_SUBMIT_ACCEPTED_CODE) {
    errors.push(`code must be ${LOCAL_WALLET_SUBMIT_ACCEPTED_CODE}`);
  }
  if (data.status !== "pending") {
    errors.push("status must be pending");
  }
  if (data.mutation !== LOCAL_WALLET_SUBMIT_ACCEPTED_MUTATION) {
    errors.push(`mutation must be ${LOCAL_WALLET_SUBMIT_ACCEPTED_MUTATION}`);
  }
  if (data.warning !== "local-private-devnet-only") {
    errors.push("warning must be local-private-devnet-only");
  }
  if (!data.audit_event_recorded) {
    errors.push("audit_event_recorded must be true");
  }
  if (transaction.status !== "pending") {
    errors.push("transaction status must be pending");
  }
  if (transaction.block_height !== null) {
    errors.push("pending transaction block_height must be null");
  }
  if (transaction.transaction_index !== null) {
    errors.push("pending transaction transaction_index must be null");
  }
  if (transaction.tx_hash !== data.pending_state.added_tx_hash) {
    errors.push("pending_state added_tx_hash must match transaction tx_hash");
  }
  if (data.pending_state.after_count !== data.pending_state.before_count + 1) {
    errors.push("pending_state must add exactly one transaction");
  }
  if (data.chain_state.chain_unchanged !== true) {
    errors.push("chain_state chain_unchanged must be true");
  }
  if (expectations.pendingFile && data.pending_state.pending_file !== expectations.pendingFile) {
    errors.push("pending_file does not match expected local smoke file");
  }
  if (expectations.chainFile && data.chain_state.chain_file !== expectations.chainFile) {
    errors.push("chain_file does not match expected local smoke file");
  }
  if (expectations.fromAddress && transaction.from_address !== expectations.fromAddress) {
    errors.push("transaction from_address does not match expected sender");
  }
  if (expectations.toAddress && transaction.to_address !== expectations.toAddress) {
    errors.push("transaction to_address does not match expected recipient");
  }

  if (audit.actor !== "local-private-devnet-operator") {
    errors.push("audit actor must be local-private-devnet-operator");
  }
  if (audit.action !== "wallet_transfer_submit_attempt") {
    errors.push("audit action must be wallet_transfer_submit_attempt");
  }
  if (audit.resource_type !== "wallet_transfer") {
    errors.push("audit resource_type must be wallet_transfer");
  }
  if (audit.environment !== "private-devnet") {
    errors.push("audit environment must be private-devnet");
  }
  if (expectedLocalRequestId) {
    if (audit.event_id !== `wallet-transfer-submit:${expectedLocalRequestId}`) {
      errors.push("audit event_id does not match expected local_request_id");
    }
    if (metadata.local_request_id !== expectedLocalRequestId) {
      errors.push("audit metadata local_request_id does not match expected value");
    }
  }
  if (expectations.draftId && metadata.draft_id !== expectations.draftId) {
    errors.push("audit metadata draft_id does not match expected value");
  }
  if (metadata.endpoint !== WALLET_SUBMIT_REFUSAL_ENDPOINT) {
    errors.push("audit metadata endpoint marker is missing");
  }
  if (metadata.outcome !== "accepted") {
    errors.push("audit metadata outcome must be accepted");
  }
  if (metadata.status !== "pending") {
    errors.push("audit metadata status must be pending");
  }
  if (metadata.explicit_flag !== "--enable-local-wallet-submit") {
    errors.push("audit metadata explicit flag is wrong");
  }
  if (metadata.from_address !== transaction.from_address) {
    errors.push("audit metadata from_address must match transaction");
  }
  if (metadata.to_address !== transaction.to_address) {
    errors.push("audit metadata to_address must match transaction");
  }
  if (metadata.amount_base_units !== transaction.amount_base_units) {
    errors.push("audit metadata amount_base_units must match transaction");
  }
  if (metadata.fee_base_units !== transaction.fee_base_units) {
    errors.push("audit metadata fee_base_units must match transaction");
  }
  if (metadata.nonce !== transaction.nonce) {
    errors.push("audit metadata nonce must match transaction");
  }
  if (metadata.expires_at_height !== transaction.expires_at_height) {
    errors.push("audit metadata expires_at_height must match transaction");
  }
  if (metadata.pending_before_count !== data.pending_state.before_count) {
    errors.push("audit metadata pending_before_count must match pending_state");
  }
  if (metadata.pending_after_count !== data.pending_state.after_count) {
    errors.push("audit metadata pending_after_count must match pending_state");
  }
  if (metadata.added_tx_hash !== transaction.tx_hash) {
    errors.push("audit metadata added_tx_hash must match transaction");
  }
  if (metadata.chain_current_height !== data.chain_state.current_height) {
    errors.push("audit metadata chain_current_height must match chain_state");
  }
  if (!metadata.metadata_policy.includes("no signing material")) {
    errors.push("audit metadata policy must forbid signing material");
  }
  if (!metadata.metadata_policy.includes("custody material")) {
    errors.push("audit metadata policy must forbid custody material");
  }

  return errors;
}

export function validateLocalWalletSendAcceptedContract(
  data: LocalWalletSendAcceptedResponse,
  expectations: LocalWalletSendAcceptedExpectations = {},
): string[] {
  const errors: string[] = [];
  const expectedLocalRequestId = expectations.localRequestId;
  const transaction = data.transaction;
  const audit = data.audit_event;
  const metadata = audit.metadata;

  if (data.environment !== "private-devnet") {
    errors.push("environment must be private-devnet");
  }
  if (data.network !== "xriq-devnet") {
    errors.push("network must be xriq-devnet");
  }
  if (data.endpoint !== WALLET_SEND_REFUSAL_ENDPOINT) {
    errors.push("wallet send accepted endpoint marker is missing");
  }
  if (data.code !== LOCAL_WALLET_SEND_ACCEPTED_CODE) {
    errors.push(`code must be ${LOCAL_WALLET_SEND_ACCEPTED_CODE}`);
  }
  if (data.status !== "pending") {
    errors.push("status must be pending");
  }
  if (data.mutation !== LOCAL_WALLET_SEND_ACCEPTED_MUTATION) {
    errors.push(`mutation must be ${LOCAL_WALLET_SEND_ACCEPTED_MUTATION}`);
  }
  if (data.warning !== "local-private-devnet-only") {
    errors.push("warning must be local-private-devnet-only");
  }
  if (!data.audit_event_recorded) {
    errors.push("audit_event_recorded must be true");
  }
  if (transaction.status !== "pending") {
    errors.push("transaction status must be pending");
  }
  if (transaction.block_height !== null) {
    errors.push("pending transaction block_height must be null");
  }
  if (transaction.transaction_index !== null) {
    errors.push("pending transaction transaction_index must be null");
  }
  if (transaction.tx_hash !== data.pending_state.added_tx_hash) {
    errors.push("pending_state added_tx_hash must match transaction tx_hash");
  }
  if (data.pending_state.after_count !== data.pending_state.before_count + 1) {
    errors.push("pending_state must add exactly one transaction");
  }
  if (data.chain_state.chain_unchanged !== true) {
    errors.push("chain_state chain_unchanged must be true");
  }
  if (expectations.pendingFile && data.pending_state.pending_file !== expectations.pendingFile) {
    errors.push("pending_file does not match expected local smoke file");
  }
  if (expectations.chainFile && data.chain_state.chain_file !== expectations.chainFile) {
    errors.push("chain_file does not match expected local smoke file");
  }
  if (expectations.fromAddress && transaction.from_address !== expectations.fromAddress) {
    errors.push("transaction from_address does not match expected sender");
  }
  if (expectations.toAddress && transaction.to_address !== expectations.toAddress) {
    errors.push("transaction to_address does not match expected recipient");
  }

  if (audit.actor !== "local-private-devnet-operator") {
    errors.push("audit actor must be local-private-devnet-operator");
  }
  if (audit.action !== "wallet_transfer_send_attempt") {
    errors.push("audit action must be wallet_transfer_send_attempt");
  }
  if (audit.resource_type !== "wallet_transfer") {
    errors.push("audit resource_type must be wallet_transfer");
  }
  if (audit.resource_id !== "local_request_id") {
    errors.push("audit resource_id must use the local_request_id marker");
  }
  if (audit.environment !== "private-devnet") {
    errors.push("audit environment must be private-devnet");
  }
  if (expectedLocalRequestId) {
    if (audit.event_id !== `wallet-transfer-send:${expectedLocalRequestId}`) {
      errors.push("audit event_id does not match expected local_request_id");
    }
    if (metadata.local_request_id !== expectedLocalRequestId) {
      errors.push("audit metadata local_request_id does not match expected value");
    }
  }
  if (metadata.endpoint !== WALLET_SEND_REFUSAL_ENDPOINT) {
    errors.push("audit metadata endpoint marker is missing");
  }
  if (metadata.outcome !== "accepted") {
    errors.push("audit metadata outcome must be accepted");
  }
  if (metadata.status !== "pending") {
    errors.push("audit metadata status must be pending");
  }
  if (metadata.explicit_flag !== "--enable-local-wallet-send") {
    errors.push("audit metadata explicit flag is wrong");
  }
  if (metadata.from_address !== transaction.from_address) {
    errors.push("audit metadata from_address must match transaction");
  }
  if (metadata.to_address !== transaction.to_address) {
    errors.push("audit metadata to_address must match transaction");
  }
  if (metadata.amount_base_units !== transaction.amount_base_units) {
    errors.push("audit metadata amount_base_units must match transaction");
  }
  if (metadata.fee_base_units !== transaction.fee_base_units) {
    errors.push("audit metadata fee_base_units must match transaction");
  }
  if (metadata.nonce !== transaction.nonce) {
    errors.push("audit metadata nonce must match transaction");
  }
  if (metadata.expires_at_height !== transaction.expires_at_height) {
    errors.push("audit metadata expires_at_height must match transaction");
  }
  if (metadata.pending_before_count !== data.pending_state.before_count) {
    errors.push("audit metadata pending_before_count must match pending_state");
  }
  if (metadata.pending_after_count !== data.pending_state.after_count) {
    errors.push("audit metadata pending_after_count must match pending_state");
  }
  if (metadata.added_tx_hash !== transaction.tx_hash) {
    errors.push("audit metadata added_tx_hash must match transaction");
  }
  if (metadata.chain_current_height !== data.chain_state.current_height) {
    errors.push("audit metadata chain_current_height must match chain_state");
  }
  if (!metadata.metadata_policy.includes("no signing material")) {
    errors.push("audit metadata policy must forbid signing material");
  }
  if (!metadata.metadata_policy.includes("custody material")) {
    errors.push("audit metadata policy must forbid custody material");
  }

  return errors;
}

export async function loadIsoPaymentInitiationPreview(
  baseUrl: string,
  txHash: string,
): Promise<IsoPaymentInitiationPreviewResponse> {
  const params = new URLSearchParams({ tx_hash: txHash });
  return fetchJson<IsoPaymentInitiationPreviewResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/iso20022/payment-initiation/preview?${params.toString()}`,
  );
}

export async function loadIsoPaymentStatusPreview(
  baseUrl: string,
  txHash: string,
): Promise<IsoPaymentStatusPreviewResponse> {
  return fetchJson<IsoPaymentStatusPreviewResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/iso20022/transactions/${encodeURIComponent(txHash)}/status`,
  );
}

export async function loadIsoAccountStatementPreview(
  baseUrl: string,
  address: string,
  from: string,
  to: string,
): Promise<IsoAccountStatementPreviewResponse> {
  const params = new URLSearchParams({ from, to });
  return fetchJson<IsoAccountStatementPreviewResponse>(
    normalizeBaseUrl(baseUrl),
    `/api/v1/iso20022/accounts/${encodeURIComponent(address)}/statement?${params.toString()}`,
  );
}

async function fetchJson<T>(
  baseUrl: string,
  path: string,
  options?: { method?: "GET" | "POST"; acceptedStatuses?: number[] },
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      Accept: "application/json",
    },
  });
  const acceptedStatuses = options?.acceptedStatuses ?? [200];

  if (!acceptedStatuses.includes(response.status)) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}
