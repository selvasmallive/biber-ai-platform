import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  AccountDetailResponse,
  AccountHistoryResponse,
  BlockDetailResponse,
  DEFAULT_API_BASE_URL,
  ExplorerSnapshot,
  TransactionDetailResponse,
  loadAccountDetail,
  loadAccountHistory,
  loadBlockDetail,
  loadExplorerSnapshot,
  loadTransactionDetail,
} from "./api";
import { AdminStatusPanel } from "./admin";
import { IsoPreviewPanel } from "./iso";
import "./styles.css";
import { WalletShell } from "./wallet";

type LoadState =
  | { status: "loading"; snapshot: ExplorerSnapshot | null; error: null }
  | { status: "ready"; snapshot: ExplorerSnapshot; error: null }
  | { status: "error"; snapshot: ExplorerSnapshot | null; error: string };

type DetailState<T> =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: T | null; error: null }
  | { status: "ready"; data: T; error: null }
  | { status: "error"; data: T | null; error: string };

function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [loadState, setLoadState] = useState<LoadState>({
    status: "loading",
    snapshot: null,
    error: null,
  });
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [selectedTransactionHash, setSelectedTransactionHash] = useState<string | null>(null);
  const [selectedAccountAddress, setSelectedAccountAddress] = useState<string | null>(null);
  const [blockDetail, setBlockDetail] = useState<DetailState<BlockDetailResponse>>({
    status: "idle",
    data: null,
    error: null,
  });
  const [transactionDetail, setTransactionDetail] = useState<
    DetailState<TransactionDetailResponse>
  >({
    status: "idle",
    data: null,
    error: null,
  });
  const [accountDetail, setAccountDetail] = useState<DetailState<AccountDetailResponse>>({
    status: "idle",
    data: null,
    error: null,
  });
  const [accountHistory, setAccountHistory] = useState<DetailState<AccountHistoryResponse>>({
    status: "idle",
    data: null,
    error: null,
  });

  const refresh = useCallback(async () => {
    setLoadState((current) => ({
      status: "loading",
      snapshot: current.snapshot,
      error: null,
    }));
    try {
      const snapshot = await loadExplorerSnapshot(apiBaseUrl);
      setLoadState({ status: "ready", snapshot, error: null });
    } catch (error) {
      setLoadState((current) => ({
        status: "error",
        snapshot: current.snapshot,
        error: error instanceof Error ? error.message : "Explorer load failed",
      }));
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const snapshot = loadState.snapshot;
  const totals = snapshot?.overview.totals;
  const activeBlockId =
    selectedBlockId ?? snapshot?.blocks.blocks[0]?.height.toString() ?? "";
  const activeTransactionHash =
    selectedTransactionHash ?? snapshot?.transactions.transactions[0]?.tx_hash ?? "";
  const activeAccountAddress =
    selectedAccountAddress ?? snapshot?.accounts.accounts[0]?.address ?? "";
  const statusText = useMemo(() => {
    if (loadState.status === "loading") {
      return "Syncing";
    }
    if (loadState.status === "error") {
      return "API offline";
    }
    return snapshot?.health.ok ? "Healthy" : "Degraded";
  }, [loadState.status, snapshot?.health.ok]);

  useEffect(() => {
    if (!activeBlockId) {
      setBlockDetail({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setBlockDetail((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadBlockDetail(apiBaseUrl, activeBlockId)
      .then((data) => {
        if (!cancelled) {
          setBlockDetail({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setBlockDetail((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Block detail failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, activeBlockId]);

  useEffect(() => {
    if (!activeTransactionHash) {
      setTransactionDetail({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setTransactionDetail((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadTransactionDetail(apiBaseUrl, activeTransactionHash)
      .then((data) => {
        if (!cancelled) {
          setTransactionDetail({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setTransactionDetail((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Transaction detail failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, activeTransactionHash]);

  useEffect(() => {
    if (!activeAccountAddress) {
      setAccountDetail({ status: "idle", data: null, error: null });
      setAccountHistory({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setAccountDetail((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    setAccountHistory((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadAccountDetail(apiBaseUrl, activeAccountAddress)
      .then((data) => {
        if (!cancelled) {
          setAccountDetail({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setAccountDetail((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Account detail failed",
          }));
        }
      });
    void loadAccountHistory(apiBaseUrl, activeAccountAddress)
      .then((data) => {
        if (!cancelled) {
          setAccountHistory({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setAccountHistory((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Account history failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, activeAccountAddress]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void refresh();
  }

  return (
    <main className="appShell">
      <header className="topBar">
        <div>
          <p className="eyebrow">XRIQ Private Devnet</p>
          <h1>XRIQ Explorer</h1>
        </div>
        <div className="statusCluster">
          <span className={`statusPill ${loadState.status}`}>{statusText}</span>
          <button className="iconButton" type="button" onClick={() => void refresh()}>
            <span>Refresh</span>
          </button>
        </div>
      </header>

      <form className="apiBar" onSubmit={handleSubmit}>
        <label htmlFor="apiBaseUrl">API URL</label>
        <input
          id="apiBaseUrl"
          value={apiBaseUrl}
          onChange={(event) => setApiBaseUrl(event.target.value)}
          placeholder="same-origin"
          spellCheck={false}
        />
        <button type="submit">Connect</button>
      </form>

      {loadState.status === "error" ? (
        <section className="notice" role="status">
          <strong>{loadState.error}</strong>
          <span>{apiBaseUrl || "same-origin"}</span>
        </section>
      ) : null}

      <section className="metricGrid" aria-label="Explorer totals">
        <Metric label="Height" value={snapshot?.network.current_height ?? "-"} />
        <Metric label="Blocks" value={totals?.blocks ?? "-"} />
        <Metric label="Transactions" value={totals?.transactions ?? "-"} />
        <Metric label="Accounts" value={totals?.accounts ?? "-"} />
      </section>

      <section className="contentGrid">
        <section className="panel heroPanel">
          <div>
            <p className="sectionLabel">Network</p>
            <h2>{snapshot?.network.network ?? "xriq-devnet"}</h2>
            <dl className="detailList">
              <Detail label="Environment" value={snapshot?.health.environment ?? "private-devnet"} />
              <Detail label="Tip Hash" value={snapshot?.network.latest_block_hash ?? "-"} compact />
              <Detail label="State Root" value={snapshot?.network.state_root ?? "-"} compact />
              <Detail label="Indexer" value={snapshot?.indexer.status ?? "-"} />
              <Detail label="Lag" value={snapshot?.indexer.lag_blocks ?? "-"} />
            </dl>
          </div>
          <img
            className="topology"
            src="/xriq-topology.svg"
            alt="XRIQ local private-devnet topology"
          />
        </section>

        <TablePanel
          title="Latest Blocks"
          columns={["Height", "Hash", "Tx", "Time"]}
          rows={(snapshot?.blocks.blocks ?? []).map((block) => ({
            id: block.height.toString(),
            cells: [
              block.height,
              shortHash(block.block_hash),
              block.transaction_count,
              compactTime(block.timestamp_utc),
            ],
            isSelected: activeBlockId === block.height.toString(),
            onSelect: () => setSelectedBlockId(block.height.toString()),
          }))}
        />

        <TablePanel
          title="Transactions"
          columns={["Hash", "Status", "Amount", "Fee"]}
          rows={(snapshot?.transactions.transactions ?? []).map((transaction) => ({
            id: transaction.tx_hash,
            cells: [
              shortHash(transaction.tx_hash),
              transaction.status,
              transaction.amount_base_units,
              transaction.fee_base_units,
            ],
            isSelected: activeTransactionHash === transaction.tx_hash,
            onSelect: () => setSelectedTransactionHash(transaction.tx_hash),
          }))}
        />

        <TablePanel
          title="Accounts"
          columns={["Address", "Balance", "Nonce", "Height"]}
          rows={(snapshot?.accounts.accounts ?? []).map((account) => ({
            id: account.address,
            cells: [
              shortAddress(account.address),
              account.balance_base_units,
              account.nonce,
              account.height,
            ],
            isSelected: activeAccountAddress === account.address,
            onSelect: () => setSelectedAccountAddress(account.address),
          }))}
        />

        <BlockDetailPanel state={blockDetail} onTransactionSelect={setSelectedTransactionHash} />
        <TransactionDetailPanel
          state={transactionDetail}
          onAccountSelect={setSelectedAccountAddress}
        />
        <AccountDetailPanel detail={accountDetail} history={accountHistory} />
        <WalletShell
          apiBaseUrl={apiBaseUrl}
          snapshot={snapshot}
          activeAccountAddress={activeAccountAddress}
          onAccountSelect={(address) => setSelectedAccountAddress(address)}
        />
        <IsoPreviewPanel
          apiBaseUrl={apiBaseUrl}
          transactionHash={activeTransactionHash}
          accountAddress={activeAccountAddress}
        />
        <AdminStatusPanel
          apiBaseUrl={apiBaseUrl}
          snapshot={snapshot}
          loadStatus={loadState.status}
        />
      </section>

      <footer className="footerLine">
        <span>Loaded {snapshot ? compactTime(snapshot.loadedAt) : "-"}</span>
        <span>{snapshot?.health.version ?? "phase1.1-dev"}</span>
      </footer>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Detail({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string | number;
  compact?: boolean;
}) {
  return (
    <>
      <dt>{label}</dt>
      <dd className={compact ? "mono truncate" : undefined}>{value}</dd>
    </>
  );
}

function TablePanel({
  title,
  columns,
  rows,
}: {
  title: string;
  columns: string[];
  rows: Array<{
    id: string;
    cells: Array<string | number>;
    isSelected?: boolean;
    onSelect?: () => void;
  }>;
}) {
  return (
    <section className="panel">
      <div className="panelTitle">
        <h2>{title}</h2>
        <span>{rows.length}</span>
      </div>
      <div className="tableFrame">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((row) => (
                <tr key={row.id} className={row.isSelected ? "selectedRow" : undefined}>
                  {row.cells.map((cell, cellIndex) => (
                    <td key={`${row.id}-${cellIndex}`}>
                      {cellIndex === 0 && row.onSelect ? (
                        <button className="rowButton" type="button" onClick={row.onSelect}>
                          {cell}
                        </button>
                      ) : (
                        cell
                      )}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length}>No rows</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BlockDetailPanel({
  state,
  onTransactionSelect,
}: {
  state: DetailState<BlockDetailResponse>;
  onTransactionSelect: (txHash: string) => void;
}) {
  const block = state.data;
  return (
    <section className="panel detailPanel">
      <PanelHeading title="Block Detail" status={state.status} />
      {state.status === "error" ? <p className="errorText">{state.error}</p> : null}
      {block ? (
        <>
          <dl className="detailList">
            <Detail label="Height" value={block.height} />
            <Detail label="Hash" value={block.block_hash} compact />
            <Detail label="Previous" value={block.previous_block_hash} compact />
            <Detail label="State Root" value={block.state_root} compact />
            <Detail label="Tx Root" value={block.transactions_root} compact />
            <Detail label="Timestamp" value={compactTime(block.timestamp_utc)} />
          </dl>
          <div className="miniTable">
            <table>
              <thead>
                <tr>
                  <th>Tx Hash</th>
                  <th>Amount</th>
                  <th>Fee</th>
                </tr>
              </thead>
              <tbody>
                {block.transactions.map((transaction) => (
                  <tr key={transaction.tx_hash}>
                    <td>
                      <button
                        className="rowButton"
                        type="button"
                        onClick={() => onTransactionSelect(transaction.tx_hash)}
                      >
                        {shortHash(transaction.tx_hash)}
                      </button>
                    </td>
                    <td>{transaction.amount_base_units}</td>
                    <td>{transaction.fee_base_units}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="mutedText">No block selected</p>
      )}
    </section>
  );
}

function TransactionDetailPanel({
  state,
  onAccountSelect,
}: {
  state: DetailState<TransactionDetailResponse>;
  onAccountSelect: (address: string) => void;
}) {
  const transaction = state.data;
  return (
    <section className="panel detailPanel">
      <PanelHeading title="Transaction Detail" status={state.status} />
      {state.status === "error" ? <p className="errorText">{state.error}</p> : null}
      {transaction ? (
        <dl className="detailList">
          <Detail label="Hash" value={transaction.tx_hash} compact />
          <Detail label="Status" value={transaction.status} />
          <Detail label="Block" value={transaction.block_height} />
          <Detail label="Amount" value={transaction.amount_base_units} />
          <Detail label="Fee" value={transaction.fee_base_units} />
          <Detail label="Nonce" value={transaction.nonce} />
          <dt>From</dt>
          <dd>
            <button
              className="rowButton"
              type="button"
              onClick={() => onAccountSelect(transaction.from_address)}
            >
              {shortAddress(transaction.from_address)}
            </button>
          </dd>
          <dt>To</dt>
          <dd>
            <button
              className="rowButton"
              type="button"
              onClick={() => onAccountSelect(transaction.to_address)}
            >
              {shortAddress(transaction.to_address)}
            </button>
          </dd>
        </dl>
      ) : (
        <p className="mutedText">No transaction selected</p>
      )}
    </section>
  );
}

function AccountDetailPanel({
  detail,
  history,
}: {
  detail: DetailState<AccountDetailResponse>;
  history: DetailState<AccountHistoryResponse>;
}) {
  const account = detail.data;
  return (
    <section className="panel detailPanel widePanel">
      <PanelHeading title="Account Detail" status={detail.status} />
      {detail.status === "error" ? <p className="errorText">{detail.error}</p> : null}
      {account ? (
        <>
          <dl className="detailList accountDetailList">
            <Detail label="Address" value={account.address} compact />
            <Detail label="Balance" value={account.balance_base_units} />
            <Detail label="Nonce" value={account.nonce} />
            <Detail label="Height" value={account.height} />
            <Detail label="First Seen" value={account.first_seen_height ?? "-"} />
            <Detail label="Last Seen" value={account.last_seen_height ?? "-"} />
            <Detail label="State Root" value={account.state_root} compact />
          </dl>
          <div className="miniTable">
            <div className="subHeading">
              <h3>Account Transactions</h3>
              <span>{history.status}</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Hash</th>
                  <th>Direction</th>
                  <th>Amount</th>
                  <th>Fee</th>
                </tr>
              </thead>
              <tbody>
                {(history.data?.transactions ?? []).map((transaction) => (
                  <tr key={`${transaction.tx_hash}-${transaction.direction}`}>
                    <td>{shortHash(transaction.tx_hash)}</td>
                    <td>{transaction.direction}</td>
                    <td>{transaction.amount_base_units}</td>
                    <td>{transaction.fee_base_units}</td>
                  </tr>
                ))}
                {history.data?.transactions.length === 0 ? (
                  <tr>
                    <td colSpan={4}>No rows</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
            {history.status === "error" ? (
              <p className="errorText">{history.error}</p>
            ) : null}
          </div>
        </>
      ) : (
        <p className="mutedText">No account selected</p>
      )}
    </section>
  );
}

function PanelHeading({ title, status }: { title: string; status: string }) {
  return (
    <div className="panelTitle">
      <h2>{title}</h2>
      <span>{status}</span>
    </div>
  );
}

function shortHash(value: string) {
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}

function shortAddress(value: string) {
  return value.length > 18 ? `${value.slice(0, 12)}...${value.slice(-4)}` : value;
}

function compactTime(value: string) {
  return value.replace("T", " ").replace("Z", "");
}

export default App;
