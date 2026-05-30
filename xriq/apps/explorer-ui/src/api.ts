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
  };
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
