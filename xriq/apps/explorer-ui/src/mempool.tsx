import { useEffect, useState } from "react";
import {
  ExplorerSnapshot,
  WalletTransactionStatusResponse,
  loadWalletTransactionStatus,
} from "./api";

interface PendingTransactionsPanelProps {
  apiBaseUrl: string;
  snapshot: ExplorerSnapshot | null;
}

type PendingStatusState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: WalletTransactionStatusResponse | null; error: null }
  | { status: "ready"; data: WalletTransactionStatusResponse; error: null }
  | { status: "error"; data: WalletTransactionStatusResponse | null; error: string };

export function PendingTransactionsPanel({
  apiBaseUrl,
  snapshot,
}: PendingTransactionsPanelProps) {
  const entries = snapshot?.mempool.entries ?? [];
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const selectedEntry = entries.find((entry) => entry.tx_hash === selectedHash);
  const activeEntry = selectedEntry ?? entries[0] ?? null;
  const activeHash = activeEntry?.tx_hash ?? "";
  const [pendingStatus, setPendingStatus] = useState<PendingStatusState>({
    status: "idle",
    data: null,
    error: null,
  });

  useEffect(() => {
    if (!activeHash) {
      setPendingStatus({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setPendingStatus((current) => ({
      status: "loading",
      data: current.data?.tx_hash === activeHash ? current.data : null,
      error: null,
    }));
    void loadWalletTransactionStatus(apiBaseUrl, activeHash)
      .then((data) => {
        if (!cancelled) {
          setPendingStatus({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setPendingStatus((current) => ({
            status: "error",
            data: current.data,
            error:
              error instanceof Error
                ? error.message
                : "Pending transaction status failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, activeHash]);

  return (
    <section className="panel detailPanel widePanel mempoolPanel">
      <div className="panelTitle">
        <h2>Pending Transactions</h2>
        <span>{snapshot?.mempool.pending_count ?? entries.length}</span>
      </div>

      <div className="miniTable">
        <table>
          <thead>
            <tr>
              <th>Hash</th>
              <th>Status</th>
              <th>Amount</th>
              <th>Fee</th>
              <th>Nonce</th>
            </tr>
          </thead>
          <tbody>
            {entries.length > 0 ? (
              entries.map((entry) => (
                <tr
                  key={entry.tx_hash}
                  className={activeHash === entry.tx_hash ? "selectedRow" : undefined}
                >
                  <td>
                    <button
                      className="rowButton"
                      type="button"
                      onClick={() => setSelectedHash(entry.tx_hash)}
                    >
                      {shortHash(entry.tx_hash)}
                    </button>
                  </td>
                  <td>{entry.status}</td>
                  <td>{entry.amount_base_units}</td>
                  <td>{entry.fee_base_units}</td>
                  <td>{entry.nonce}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>No pending transactions</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pendingDetail">
        <div className="subHeading">
          <h3>Selected Pending Status</h3>
          <span>{pendingStatus.status}</span>
        </div>
        {pendingStatus.status === "error" ? (
          <p className="errorText">{pendingStatus.error}</p>
        ) : null}
        {pendingStatus.data ? (
          <dl className="detailList">
            <Detail label="Hash" value={pendingStatus.data.tx_hash} compact />
            <Detail label="Status" value={pendingStatus.data.status} />
            <Detail label="Block" value={nullableNumber(pendingStatus.data.block_height)} />
            <Detail label="Index" value={nullableNumber(pendingStatus.data.transaction_index)} />
            <Detail label="From" value={activeEntry?.from_address ?? "-"} compact />
            <Detail label="To" value={activeEntry?.to_address ?? "-"} compact />
          </dl>
        ) : (
          <p className="mutedText">
            {entries.length > 0
              ? "Loading pending transaction status"
              : "No pending transaction selected"}
          </p>
        )}
      </div>
    </section>
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

function nullableNumber(value: number | null | undefined) {
  if (value === null) {
    return "null";
  }
  return value ?? "-";
}

function shortHash(value: string) {
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}
