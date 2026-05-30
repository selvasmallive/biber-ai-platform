import { useEffect, useMemo, useState } from "react";
import {
  IsoAccountStatementPreviewResponse,
  IsoPaymentInitiationPreviewResponse,
  IsoPaymentStatusPreviewResponse,
  loadIsoAccountStatementPreview,
  loadIsoPaymentInitiationPreview,
  loadIsoPaymentStatusPreview,
} from "./api";

const STATEMENT_FROM = "1970-01-01T00:00:00Z";
const STATEMENT_TO = "1970-01-01T00:00:02Z";

interface IsoPreviewPanelProps {
  apiBaseUrl: string;
  transactionHash: string;
  accountAddress: string;
}

type IsoState =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: IsoPreviewBundle | null; error: null }
  | { status: "ready"; data: IsoPreviewBundle; error: null }
  | { status: "error"; data: IsoPreviewBundle | null; error: string };

interface IsoPreviewBundle {
  initiation: IsoPaymentInitiationPreviewResponse;
  paymentStatus: IsoPaymentStatusPreviewResponse;
  statement: IsoAccountStatementPreviewResponse;
}

export function IsoPreviewPanel({
  apiBaseUrl,
  transactionHash,
  accountAddress,
}: IsoPreviewPanelProps) {
  const [state, setState] = useState<IsoState>({
    status: "idle",
    data: null,
    error: null,
  });

  useEffect(() => {
    if (!transactionHash || !accountAddress) {
      setState({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setState((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));

    void Promise.all([
      loadIsoPaymentInitiationPreview(apiBaseUrl, transactionHash),
      loadIsoPaymentStatusPreview(apiBaseUrl, transactionHash),
      loadIsoAccountStatementPreview(
        apiBaseUrl,
        accountAddress,
        STATEMENT_FROM,
        STATEMENT_TO,
      ),
    ])
      .then(([initiation, paymentStatus, statement]) => {
        if (!cancelled) {
          setState({
            status: "ready",
            data: { initiation, paymentStatus, statement },
            error: null,
          });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState((current) => ({
            status: "error",
            data: current.data,
            error:
              error instanceof Error ? error.message : "ISO preview failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accountAddress, apiBaseUrl, transactionHash]);

  const unsupportedCount = useMemo(() => {
    const data = state.data;
    if (!data) {
      return 0;
    }
    return (
      data.initiation.unsupported_fields.length +
      data.paymentStatus.unsupported_fields.length +
      data.statement.unsupported_fields.length
    );
  }, [state.data]);

  return (
    <section className="panel detailPanel widePanel isoPanel">
      <div className="panelTitle">
        <h2>ISO 20022 Preview</h2>
        <span>{state.status}</span>
      </div>

      {state.status === "error" ? <p className="errorText">{state.error}</p> : null}

      <div className="isoGrid" aria-label="Private-devnet ISO 20022 preview">
        <IsoBlock
          title="Payment Initiation"
          rows={[
            ["Type", state.data?.initiation.message_type ?? "-"],
            ["Message", state.data?.initiation.message_id ?? "-"],
            ["Certified", state.data?.initiation.not_certified ? "no" : "-"],
            ["Currency", state.data?.initiation.iso20022_aligned.currency ?? "-"],
            [
              "Amount",
              state.data?.initiation.iso20022_aligned.instructed_amount ?? "-",
            ],
            ["Unsupported", state.data?.initiation.unsupported_fields.length ?? "-"],
          ]}
        />
        <IsoBlock
          title="Payment Status"
          rows={[
            ["Type", state.data?.paymentStatus.message_type ?? "-"],
            [
              "XRIQ Status",
              state.data?.paymentStatus.xriq_status ?? "-",
            ],
            [
              "ISO Status",
              state.data?.paymentStatus.iso20022_aligned.transaction_status ?? "-",
            ],
            [
              "Reason",
              state.data?.paymentStatus.iso20022_aligned.status_reason ?? "-",
            ],
            [
              "Block",
              state.data?.paymentStatus.iso20022_aligned.confirmed_block_height ??
                "-",
            ],
            ["Unsupported", state.data?.paymentStatus.unsupported_fields.length ?? "-"],
          ]}
        />
        <IsoBlock
          title="Account Statement"
          rows={[
            ["Type", state.data?.statement.message_type ?? "-"],
            ["Account", state.data?.statement.account_address ?? "-"],
            [
              "Opening",
              state.data?.statement.opening_balance_base_units ?? "-",
            ],
            [
              "Closing",
              state.data?.statement.closing_balance_base_units ?? "-",
            ],
            ["Entries", state.data?.statement.entries.length ?? "-"],
            ["Unsupported", state.data?.statement.unsupported_fields.length ?? "-"],
          ]}
        />
      </div>

      <div className="isoFooter">
        <span>Mapping {state.data?.initiation.mapping_version ?? "-"}</span>
        <span>Unsupported fields {unsupportedCount}</span>
        <span>Read only</span>
      </div>

      <pre className="previewBox isoPreviewBox" aria-label="ISO 20022 preview JSON">
        {state.data ? JSON.stringify(state.data, null, 2) : "{}"}
      </pre>
    </section>
  );
}

function IsoBlock({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, string | number]>;
}) {
  return (
    <div className="isoBlock">
      <h3>{title}</h3>
      <dl className="detailList">
        {rows.map(([label, value]) => (
          <IsoRow key={label} label={label} value={value} />
        ))}
      </dl>
    </div>
  );
}

function IsoRow({ label, value }: { label: string; value: string | number }) {
  const isLong = typeof value === "string" && value.length > 22;
  return (
    <>
      <dt>{label}</dt>
      <dd className={isLong ? "mono truncate" : undefined}>{value}</dd>
    </>
  );
}
