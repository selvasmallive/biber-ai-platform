import { useEffect, useState } from "react";
import {
  ExplorerSnapshot,
  WalletTransactionStatusResponse,
  loadWalletTransactionStatus,
} from "./api";

interface AdminStatusPanelProps {
  apiBaseUrl: string;
  snapshot: ExplorerSnapshot | null;
  loadStatus: string;
}

type WalletTxStatusState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: WalletTransactionStatusResponse | null; error: null }
  | { status: "ready"; data: WalletTransactionStatusResponse; error: null }
  | { status: "error"; data: WalletTransactionStatusResponse | null; error: string };

export function AdminStatusPanel({
  apiBaseUrl,
  snapshot,
  loadStatus,
}: AdminStatusPanelProps) {
  const node = snapshot?.nodeStatus;
  const indexer = snapshot?.indexer;
  const wallet = snapshot?.walletStatus;
  const mempool = snapshot?.mempool;
  const firstPending = mempool?.entries[0];
  const [walletTxStatus, setWalletTxStatus] = useState<WalletTxStatusState>({
    status: "idle",
    data: null,
    error: null,
  });
  const snapshotCatalog = snapshot?.snapshots.snapshots[0];
  const latestAuditEvent = snapshot?.auditEvents.audit_events[0];
  const pendingWalletStatus = firstPending
    ? walletTxStatus.data?.status ?? walletTxStatus.status
    : "-";
  const pendingWalletBlock = firstPending
    ? nullableNumber(walletTxStatus.data?.block_height)
    : "-";
  const pendingWalletIndex = firstPending
    ? nullableNumber(walletTxStatus.data?.transaction_index)
    : "-";

  useEffect(() => {
    if (!firstPending?.tx_hash) {
      setWalletTxStatus({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setWalletTxStatus((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadWalletTransactionStatus(apiBaseUrl, firstPending.tx_hash)
      .then((data) => {
        if (!cancelled) {
          setWalletTxStatus({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setWalletTxStatus((current) => ({
            status: "error",
            data: current.data,
            error:
              error instanceof Error
                ? error.message
                : "Wallet transaction status failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, firstPending?.tx_hash]);

  return (
    <section className="panel detailPanel widePanel adminPanel">
      <div className="panelTitle">
        <h2>Admin Status</h2>
        <span>{loadStatus}</span>
      </div>

      <div className="adminGrid" aria-label="Private-devnet admin status">
        <StatusBlock
          title="Node"
          rows={[
            ["Status", node?.status ?? "-"],
            ["Mode", node?.mode ?? "-"],
            ["Source", node?.source ?? "-"],
            ["Stored Blocks", node?.stored_blocks ?? "-"],
            ["Pending", node?.pending_transactions ?? "-"],
            ["Wallet Submit", node?.wallet_submit_status ?? "-"],
            ["Block Production", node?.block_production_status ?? "-"],
          ]}
        />
        <StatusBlock
          title="Network"
          rows={[
            ["Environment", snapshot?.network.environment ?? "private-devnet"],
            ["Height", snapshot?.network.current_height ?? "-"],
            ["Tip Hash", snapshot?.network.latest_block_hash ?? "-"],
            ["State Root", snapshot?.network.state_root ?? "-"],
          ]}
        />
        <StatusBlock
          title="Indexer"
          rows={[
            ["Status", indexer?.status ?? "-"],
            ["Lag", indexer?.lag_blocks ?? "-"],
            ["Run Status", indexer?.last_run.status ?? "-"],
            ["Run", indexer?.last_run.run_id ?? "-"],
            ["Blocks", indexer?.last_run.blocks_indexed ?? "-"],
            ["Transactions", indexer?.last_run.transactions_indexed ?? "-"],
          ]}
        />
        <StatusBlock
          title="Wallet"
          rows={[
            ["Warning", wallet?.warning ?? "-"],
            ["Accounts", wallet?.account_count ?? "-"],
            ["Pending", wallet?.pending_transactions ?? "-"],
            ["Draft", wallet?.capabilities.draft ? "enabled" : "disabled"],
            ["Submit", wallet?.capabilities.submit ? "enabled" : "disabled"],
            ["Send", wallet?.capabilities.send ? "enabled" : "disabled"],
          ]}
        />
        <StatusBlock
          title="Mempool"
          rows={[
            ["Warning", mempool?.warning ?? "-"],
            ["Height", mempool?.current_height ?? "-"],
            ["Pending", mempool?.pending_count ?? "-"],
            ["Entries", mempool?.entries.length ?? "-"],
            ["First Pending", firstPending?.tx_hash ?? "-"],
            ["First Amount", firstPending?.amount_base_units ?? "-"],
            ["First Status", firstPending?.status ?? "-"],
            ["Wallet Tx Status", pendingWalletStatus],
            ["Wallet Tx Block", pendingWalletBlock],
            ["Wallet Tx Index", pendingWalletIndex],
            ["Inspect", mempool?.inspect_status ?? "-"],
            ["Submit", mempool?.submit_status ?? "-"],
            ["Produce Block", mempool?.produce_block_status ?? "-"],
          ]}
        />
        <StatusBlock
          title="Snapshot Catalog"
          rows={[
            ["Warning", snapshot?.snapshots.warning ?? "-"],
            ["Name", snapshotCatalog?.snapshot_name ?? "-"],
            ["Height", snapshotCatalog?.current_height ?? "-"],
            ["Blocks", snapshotCatalog?.block_count ?? "-"],
            ["Transactions", snapshotCatalog?.transaction_count ?? "-"],
            ["Audit Events", snapshotCatalog?.audit_event_count ?? "-"],
            ["Export", snapshotCatalog?.export_status ?? "-"],
            ["Import", snapshotCatalog?.import_status ?? "-"],
          ]}
        />
        <StatusBlock
          title="Audit Events"
          rows={[
            ["Count", snapshot?.auditEvents.audit_events.length ?? "-"],
            ["Latest", latestAuditEvent?.event_id ?? "-"],
            ["Actor", latestAuditEvent?.actor ?? "-"],
            ["Action", latestAuditEvent?.action ?? "-"],
            ["Resource", latestAuditEvent?.resource_type ?? "-"],
            ["Resource Id", latestAuditEvent?.resource_id ?? "-"],
          ]}
        />
      </div>
    </section>
  );
}

function nullableNumber(value: number | null | undefined) {
  if (value === null) {
    return "null";
  }
  return value ?? "-";
}

function StatusBlock({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, string | number]>;
}) {
  return (
    <div className="adminBlock">
      <h3>{title}</h3>
      <dl className="detailList">
        {rows.map(([label, value]) => (
          <FragmentRow key={label} label={label} value={value} />
        ))}
      </dl>
    </div>
  );
}

function FragmentRow({ label, value }: { label: string; value: string | number }) {
  const isLong = typeof value === "string" && value.length > 24;
  return (
    <>
      <dt>{label}</dt>
      <dd className={isLong ? "mono truncate" : undefined}>{value}</dd>
    </>
  );
}
