import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_API_BASE_URL,
  ExplorerSnapshot,
  loadExplorerSnapshot,
} from "./api";
import "./styles.css";

type LoadState =
  | { status: "loading"; snapshot: ExplorerSnapshot | null; error: null }
  | { status: "ready"; snapshot: ExplorerSnapshot; error: null }
  | { status: "error"; snapshot: ExplorerSnapshot | null; error: string };

function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [loadState, setLoadState] = useState<LoadState>({
    status: "loading",
    snapshot: null,
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
  const statusText = useMemo(() => {
    if (loadState.status === "loading") {
      return "Syncing";
    }
    if (loadState.status === "error") {
      return "API offline";
    }
    return snapshot?.health.ok ? "Healthy" : "Degraded";
  }, [loadState.status, snapshot?.health.ok]);

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
          rows={(snapshot?.blocks.blocks ?? []).map((block) => [
            block.height,
            shortHash(block.block_hash),
            block.transaction_count,
            compactTime(block.timestamp_utc),
          ])}
        />

        <TablePanel
          title="Transactions"
          columns={["Hash", "Status", "Amount", "Fee"]}
          rows={(snapshot?.transactions.transactions ?? []).map((transaction) => [
            shortHash(transaction.tx_hash),
            transaction.status,
            transaction.amount_base_units,
            transaction.fee_base_units,
          ])}
        />

        <TablePanel
          title="Accounts"
          columns={["Address", "Balance", "Nonce", "Height"]}
          rows={(snapshot?.accounts.accounts ?? []).map((account) => [
            shortAddress(account.address),
            account.balance_base_units,
            account.nonce,
            account.height,
          ])}
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
  rows: Array<Array<string | number>>;
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
              rows.map((row, rowIndex) => (
                <tr key={`${title}-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`${title}-${rowIndex}-${cellIndex}`}>{cell}</td>
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
