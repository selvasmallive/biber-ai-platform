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

export interface ExplorerSnapshot {
  loadedAt: string;
  health: HealthResponse;
  network: NetworkResponse;
  overview: ExplorerOverviewResponse;
  blocks: BlockListResponse;
  transactions: TransactionListResponse;
  accounts: AccountListResponse;
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

export interface AdminAuditEvent {
  event_id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  environment: "private-devnet";
}

export interface AdminAuditEventsResponse {
  environment: "private-devnet";
  network: string;
  limit: number;
  next_cursor: string | null;
  audit_events: AdminAuditEvent[];
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
    accounts,
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
    fetchJson<AccountListResponse>(cleanBaseUrl, "/api/v1/accounts?limit=5"),
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
    accounts,
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

async function fetchJson<T>(baseUrl: string, path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}
