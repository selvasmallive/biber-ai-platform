import { useEffect, useState } from "react";
import { ExplorerSnapshot, SnapshotSummary, loadSnapshotDetail } from "./api";

interface SnapshotCatalogPanelProps {
  apiBaseUrl: string;
  snapshot: ExplorerSnapshot | null;
}

type SnapshotDetailState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: SnapshotSummary | null; error: null }
  | { status: "ready"; data: SnapshotSummary; error: null }
  | { status: "error"; data: SnapshotSummary | null; error: string };

export function SnapshotCatalogPanel({
  apiBaseUrl,
  snapshot,
}: SnapshotCatalogPanelProps) {
  const snapshots = snapshot?.snapshots.snapshots ?? [];
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const selectedSnapshot = snapshots.find(
    (candidate) => candidate.snapshot_name === selectedName,
  );
  const activeSnapshot = selectedSnapshot ?? snapshots[0] ?? null;
  const activeName = activeSnapshot?.snapshot_name ?? "";
  const [detail, setDetail] = useState<SnapshotDetailState>({
    status: "idle",
    data: null,
    error: null,
  });

  useEffect(() => {
    if (!activeName) {
      setDetail({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setDetail((current) => ({
      status: "loading",
      data: current.data?.snapshot_name === activeName ? current.data : null,
      error: null,
    }));
    void loadSnapshotDetail(apiBaseUrl, activeName)
      .then((data) => {
        if (!cancelled) {
          setDetail({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDetail((current) => ({
            status: "error",
            data: current.data,
            error:
              error instanceof Error ? error.message : "Snapshot detail failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, activeName]);

  return (
    <section className="panel detailPanel widePanel snapshotPanel">
      <div className="panelTitle">
        <h2>Snapshot Catalog</h2>
        <span>{snapshots.length}</span>
      </div>

      <div className="snapshotGuard">
        <span>{snapshot?.snapshots.warning ?? "read-only-snapshot-catalog"}</span>
        <strong>Export and import controls disabled</strong>
      </div>

      <div className="miniTable">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Height</th>
              <th>Blocks</th>
              <th>Transactions</th>
              <th>Audit</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.length > 0 ? (
              snapshots.map((entry) => (
                <tr
                  key={entry.snapshot_name}
                  className={activeName === entry.snapshot_name ? "selectedRow" : undefined}
                >
                  <td>
                    <button
                      className="rowButton"
                      type="button"
                      onClick={() => setSelectedName(entry.snapshot_name)}
                    >
                      {entry.snapshot_name}
                    </button>
                  </td>
                  <td>{entry.current_height}</td>
                  <td>{entry.block_count}</td>
                  <td>{entry.transaction_count}</td>
                  <td>{entry.audit_event_count}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>No snapshots</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="snapshotDetail">
        <div className="subHeading">
          <h3>Selected Snapshot Detail</h3>
          <span>{detail.status}</span>
        </div>
        {detail.status === "error" ? <p className="errorText">{detail.error}</p> : null}
        {detail.data ? (
          <dl className="detailList">
            <Detail label="Name" value={detail.data.snapshot_name} compact />
            <Detail label="Source" value={detail.data.snapshot_dir} compact />
            <Detail label="Height" value={detail.data.current_height} />
            <Detail label="Tip Hash" value={detail.data.latest_block_hash} compact />
            <Detail label="State Root" value={detail.data.state_root} compact />
            <Detail label="Export" value={detail.data.export_status} />
            <Detail label="Import" value={detail.data.import_status} />
          </dl>
        ) : (
          <p className="mutedText">
            {snapshots.length > 0 ? "Loading snapshot detail" : "No snapshot selected"}
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
