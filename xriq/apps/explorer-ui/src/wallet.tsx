import { useEffect, useMemo, useState } from "react";
import {
  AccountSummary,
  AccountHistoryResponse,
  Ed25519SignedSubmitAcceptedResponse,
  Ed25519TransferFields,
  ExplorerSnapshot,
  LocalWalletSendAcceptedResponse,
  LocalWalletSendRequest,
  MempoolEntry,
  TransactionSummary,
  WalletBalanceResponse,
  WalletDraftPreviewResponse,
  WalletMutationAction,
  WalletMutationRefusalResponse,
  WalletStatusResponse,
  WalletTransactionStatusResponse,
  loadWalletBalance,
  loadWalletDraftPreview,
  loadWalletHistory,
  loadWalletMutationRefusal,
  loadWalletStatus,
  loadWalletTransactionStatus,
  prepareSignedSubmitSigningHash,
  sendLocalWalletTransfer,
  submitEd25519SignedTransfer,
} from "./api";
import { createEphemeralSigner } from "./signing";
import { transactionSigningHashHex } from "./canonical";

const DEFAULT_RECIPIENT = "xriqdev1bobbb00000000000";
const MIN_PRIVATE_DEVNET_FEE = 2n;
const PREVIEW_WARNING = "private-devnet-preview-only-no-signing-no-submit";
const PREFLIGHT_WARNING = "local-private-devnet-preflight-only";
const LOCAL_WALLET_SEND_UI_ENABLED =
  import.meta.env.VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI === "true";
const LOCAL_WALLET_SIGNED_SUBMIT_UI_ENABLED =
  import.meta.env.VITE_XRIQ_ENABLE_LOCAL_WALLET_SIGNED_SUBMIT_UI === "true";
// The server signed-submit endpoint accepts only this configured test sender.
const SIGNED_SUBMIT_TEST_SENDER = "xriqdev1alice00000000000";

const ACTION_GUARD_EXPECTATIONS: Record<
  WalletMutationAction,
  {
    buttonLabel: string;
    code: string;
    flag: string;
    label: string;
  }
> = {
  submit: {
    buttonLabel: "Submit Draft",
    code: "wallet_submit_disabled",
    flag: "--enable-local-wallet-submit",
    label: "Submit",
  },
  send: {
    buttonLabel: "Send Transfer",
    code: "wallet_send_disabled",
    flag: "--enable-local-wallet-send",
    label: "Send",
  },
};

interface WalletShellProps {
  apiBaseUrl: string;
  snapshot: ExplorerSnapshot | null;
  activeAccountAddress: string;
  onAccountSelect: (address: string) => void;
}

interface DraftPreview {
  format_version: "xriq-wallet-transfer-preview-v1";
  warning: typeof PREVIEW_WARNING;
  environment: "private-devnet";
  chain_id: string;
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: string;
  expires_at_height: string | null;
  mutation: "none";
}

interface DraftValidation {
  errors: string[];
  balance: bigint | null;
  debit: bigint | null;
  remaining: bigint | null;
}

export interface WalletActivityRow {
  id: string;
  txHash: string;
  source: "confirmed" | "pending";
  status: string;
  direction: "sent" | "received";
  amount: string;
  fee: string;
  nonce: number;
  block: string;
  transactionIndex: string;
  counterparty: string;
}

type ApiState<T> =
  | { status: "idle"; data: null; error: null }
  | { status: "loading"; data: T | null; error: null }
  | { status: "ready"; data: T; error: null }
  | { status: "error"; data: T | null; error: string };

type WalletActionGuardState = Record<
  WalletMutationAction,
  ApiState<WalletMutationRefusalResponse>
>;

type LocalWalletSendState = ApiState<LocalWalletSendAcceptedResponse>;

export function WalletShell({
  apiBaseUrl,
  snapshot,
  activeAccountAddress,
  onAccountSelect,
}: WalletShellProps) {
  const accounts = snapshot?.accounts.accounts ?? [];
  const selectedAccount =
    accounts.find((account) => account.address === activeAccountAddress) ??
    accounts[0] ??
    null;
  const initialFromAddress = selectedAccount?.address ?? "";
  const [fromAddress, setFromAddress] = useState(initialFromAddress);
  const [toAddress, setToAddress] = useState(
    defaultRecipient(accounts, initialFromAddress),
  );
  const [amount, setAmount] = useState("1");
  const [fee, setFee] = useState(MIN_PRIVATE_DEVNET_FEE.toString());
  const [nonce, setNonce] = useState(selectedAccount?.nonce.toString() ?? "0");
  const [expiresAtHeight, setExpiresAtHeight] = useState(
    snapshot ? (snapshot.network.current_height + 100).toString() : "",
  );
  const [walletStatus, setWalletStatus] = useState<ApiState<WalletStatusResponse>>({
    status: "idle",
    data: null,
    error: null,
  });
  const [walletBalance, setWalletBalance] = useState<ApiState<WalletBalanceResponse>>({
    status: "idle",
    data: null,
    error: null,
  });
  const [walletHistory, setWalletHistory] = useState<ApiState<AccountHistoryResponse>>({
    status: "idle",
    data: null,
    error: null,
  });
  const [apiPreview, setApiPreview] = useState<ApiState<WalletDraftPreviewResponse>>({
    status: "idle",
    data: null,
    error: null,
  });
  const [actionGuards, setActionGuards] = useState<WalletActionGuardState>(() =>
    initialActionGuards(),
  );
  const [localWalletSend, setLocalWalletSend] = useState<LocalWalletSendState>({
    status: "idle",
    data: null,
    error: null,
  });
  const [activityStatus, setActivityStatus] = useState<
    ApiState<WalletTransactionStatusResponse>
  >({
    status: "idle",
    data: null,
    error: null,
  });
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedAccount || !snapshot) {
      return;
    }

    const nextFromAddress = selectedAccount.address;
    const nextRecipient = defaultRecipient(accounts, nextFromAddress);
    setFromAddress(nextFromAddress);
    setNonce(selectedAccount.nonce.toString());
    setExpiresAtHeight((snapshot.network.current_height + 100).toString());
    setToAddress((current) =>
      current.trim() === "" || current === nextFromAddress ? nextRecipient : current,
    );
  }, [accounts, selectedAccount, snapshot]);

  const fromAccount =
    accounts.find((account) => account.address === fromAddress) ?? selectedAccount;
  const walletActivity = useMemo(
    () => walletActivityRows(snapshot, fromAddress),
    [fromAddress, snapshot],
  );
  const selectedActivity =
    walletActivity.find((activity) => activity.id === selectedActivityId) ??
    walletActivity[0] ??
    null;
  const selectedActivityTxHash = selectedActivity?.txHash ?? "";

  useEffect(() => {
    if (!snapshot) {
      setWalletStatus({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setWalletStatus((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadWalletStatus(apiBaseUrl)
      .then((data) => {
        if (!cancelled) {
          setWalletStatus({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setWalletStatus((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Wallet status failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, snapshot]);

  useEffect(() => {
    if (!fromAddress) {
      setWalletBalance({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setWalletBalance((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadWalletBalance(apiBaseUrl, fromAddress)
      .then((data) => {
        if (!cancelled) {
          setWalletBalance({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setWalletBalance((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Wallet balance failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, fromAddress]);

  useEffect(() => {
    if (!fromAddress) {
      setWalletHistory({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setWalletHistory((current) => ({
      status: "loading",
      data: current.data?.address === fromAddress ? current.data : null,
      error: null,
    }));
    void loadWalletHistory(apiBaseUrl, fromAddress)
      .then((data) => {
        if (!cancelled) {
          setWalletHistory({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setWalletHistory((current) => ({
            status: "error",
            data: current.data,
            error: error instanceof Error ? error.message : "Wallet history failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, fromAddress]);

  useEffect(() => {
    if (!selectedActivityTxHash) {
      setActivityStatus({ status: "idle", data: null, error: null });
      return;
    }

    let cancelled = false;
    setActivityStatus((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    void loadWalletTransactionStatus(apiBaseUrl, selectedActivityTxHash)
      .then((data) => {
        if (!cancelled) {
          setActivityStatus({ status: "ready", data, error: null });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setActivityStatus((current) => ({
            status: "error",
            data: current.data,
            error:
              error instanceof Error
                ? error.message
                : "Wallet activity status failed",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, selectedActivityTxHash]);

  const validation = useMemo(
    () =>
      validateDraft({
        fromAccount,
        fromAddress,
        toAddress,
        amount,
        fee,
        nonce,
        expiresAtHeight,
      }),
    [amount, expiresAtHeight, fee, fromAccount, fromAddress, nonce, toAddress],
  );
  const localWalletSendErrors = useMemo(() => {
    const errors = [...validation.errors];
    if (expiresAtHeight.trim() === "") {
      errors.push("Expires is required for local wallet send.");
    }
    return errors;
  }, [expiresAtHeight, validation.errors]);

  const balancePreview = apiPreview.data
    ? {
        balance: parseNullableInteger(apiPreview.data.balance.available_base_units),
        debit: parseNullableInteger(apiPreview.data.balance.debit_base_units),
        remaining: parseNullableInteger(apiPreview.data.balance.remaining_base_units),
      }
    : {
        balance:
          walletBalance.data?.balance_base_units === undefined
            ? validation.balance
            : parseInteger(walletBalance.data.balance_base_units),
        debit: validation.debit,
        remaining: validation.remaining,
      };

  const preview = useMemo<DraftPreview>(
    () => ({
      format_version: "xriq-wallet-transfer-preview-v1",
      warning: PREVIEW_WARNING,
      environment: "private-devnet",
      chain_id: snapshot?.network.network ?? "xriq-devnet",
      from_address: fromAddress,
      to_address: toAddress.trim(),
      amount_base_units: amount.trim(),
      fee_base_units: fee.trim(),
      nonce: nonce.trim(),
      expires_at_height: expiresAtHeight.trim() === "" ? null : expiresAtHeight.trim(),
      mutation: "none",
    }),
    [amount, expiresAtHeight, fee, fromAddress, nonce, snapshot?.network.network, toAddress],
  );
  const previewJson = localWalletSend.data ?? apiPreview.data ?? preview;

  function handleFromChange(address: string) {
    setFromAddress(address);
    onAccountSelect(address);
    const account = accounts.find((candidate) => candidate.address === address);
    if (account) {
      setNonce(account.nonce.toString());
    }
    if (toAddress.trim() === "" || toAddress === address) {
      setToAddress(defaultRecipient(accounts, address));
    }
    setApiPreview({ status: "idle", data: null, error: null });
    setLocalWalletSend({ status: "idle", data: null, error: null });
  }

  function handleDraftFieldChange(update: () => void) {
    update();
    setApiPreview({ status: "idle", data: null, error: null });
    setLocalWalletSend({ status: "idle", data: null, error: null });
  }

  async function handleCheckPreview() {
    if (validation.errors.length > 0) {
      return;
    }

    setApiPreview((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    try {
      const data = await loadWalletDraftPreview(apiBaseUrl, {
        from_address: fromAddress,
        to_address: toAddress.trim(),
        amount_base_units: amount.trim(),
        fee_base_units: fee.trim(),
        nonce: nonce.trim(),
        expires_at_height: expiresAtHeight.trim(),
      });
      setApiPreview({ status: "ready", data, error: null });
    } catch (error) {
      setApiPreview((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof Error ? error.message : "Wallet preview failed",
      }));
    }
  }

  async function handleCheckActionGuard(action: WalletMutationAction) {
    setActionGuards((current) => ({
      ...current,
      [action]: {
        status: "loading",
        data: current[action].data,
        error: null,
      },
    }));
    try {
      const data = await loadWalletMutationRefusal(apiBaseUrl, action);
      const contractErrors = validateActionRefusalContract(action, data);
      if (contractErrors.length > 0) {
        throw new Error(contractErrors.join("; "));
      }
      setActionGuards((current) => ({
        ...current,
        [action]: { status: "ready", data, error: null },
      }));
    } catch (error) {
      setActionGuards((current) => ({
        ...current,
        [action]: {
          status: "error",
          data: current[action].data,
          error: error instanceof Error ? error.message : "Wallet guard check failed",
        },
      }));
    }
  }

  async function handleCheckActionGuards() {
    await Promise.all(
      (Object.keys(ACTION_GUARD_EXPECTATIONS) as WalletMutationAction[]).map(
        (action) => handleCheckActionGuard(action),
      ),
    );
  }

  async function handleLocalWalletSend() {
    if (!LOCAL_WALLET_SEND_UI_ENABLED || localWalletSendErrors.length > 0) {
      return;
    }

    const request: LocalWalletSendRequest = {
      local_request_id: nextLocalWalletSendRequestId(),
      from_address: fromAddress,
      to_address: toAddress.trim(),
      amount_base_units: amount.trim(),
      fee_base_units: fee.trim(),
      nonce: nonce.trim(),
      expires_at_height: expiresAtHeight.trim(),
    };
    setLocalWalletSend((current) => ({
      status: "loading",
      data: current.data,
      error: null,
    }));
    try {
      const data = await sendLocalWalletTransfer(apiBaseUrl, request);
      setLocalWalletSend({ status: "ready", data, error: null });
    } catch (error) {
      setLocalWalletSend((current) => ({
        status: "error",
        data: current.data,
        error: error instanceof Error ? error.message : "Local wallet send failed",
      }));
    }
  }

  return (
    <section className="panel detailPanel widePanel walletPanel">
      <div className="panelTitle">
        <h2>Wallet Preview</h2>
        <span>{apiPreview.status === "ready" ? "api" : validation.errors.length === 0 ? "ready" : "check"}</span>
      </div>

      <div className="walletGrid">
        <div className="walletForm" aria-label="Private-devnet wallet transfer preview">
          <div className="walletApiStrip" aria-label="Wallet API status">
            <span>{walletStatus.status}</span>
            <strong>{walletStatus.data?.capabilities.draft ? "draft" : "local"}</strong>
            <strong>{walletStatus.data?.capabilities.submit ? "submit" : "no-submit"}</strong>
            <strong>{walletStatus.data?.capabilities.send ? "send" : "no-send"}</strong>
          </div>

          <label>
            From
            <select
              value={fromAddress}
              onChange={(event) => handleFromChange(event.target.value)}
              disabled={accounts.length === 0}
            >
              {accounts.length > 0 ? (
                accounts.map((account) => (
                  <option key={account.address} value={account.address}>
                    {shortAddress(account.address)}
                  </option>
                ))
              ) : (
                <option value="">No local account</option>
              )}
            </select>
          </label>

          <label>
            To
            <input
              value={toAddress}
              onChange={(event) =>
                handleDraftFieldChange(() => setToAddress(event.target.value))
              }
              spellCheck={false}
            />
          </label>

          <div className="walletFields">
            <label>
              Amount
              <input
                inputMode="numeric"
                value={amount}
                onChange={(event) =>
                  handleDraftFieldChange(() => setAmount(event.target.value))
                }
              />
            </label>
            <label>
              Fee
              <input
                inputMode="numeric"
                value={fee}
                onChange={(event) =>
                  handleDraftFieldChange(() => setFee(event.target.value))
                }
              />
            </label>
            <label>
              Nonce
              <input
                inputMode="numeric"
                value={nonce}
                onChange={(event) =>
                  handleDraftFieldChange(() => setNonce(event.target.value))
                }
              />
            </label>
            <label>
              Expires
              <input
                inputMode="numeric"
                value={expiresAtHeight}
                onChange={(event) =>
                  handleDraftFieldChange(() => setExpiresAtHeight(event.target.value))
                }
              />
            </label>
          </div>

          <div className="balanceStrip" aria-label="Transfer balance preview">
            <BalanceMetric label="Available" value={balancePreview.balance} />
            <BalanceMetric label="Debit" value={balancePreview.debit} />
            <BalanceMetric label="Remaining" value={balancePreview.remaining} />
          </div>

          <div className="walletActions">
            <button
              type="button"
              onClick={() => void handleCheckPreview()}
              disabled={validation.errors.length > 0 || apiPreview.status === "loading"}
            >
              Check Preview
            </button>
            <span>{apiPreview.status}</span>
          </div>

          <WalletActionGuards
            guards={actionGuards}
            onCheck={() => void handleCheckActionGuards()}
          />

          <LocalWalletSendControl
            enabled={LOCAL_WALLET_SEND_UI_ENABLED}
            errors={localWalletSendErrors}
            state={localWalletSend}
            onSend={() => void handleLocalWalletSend()}
          />

          {LOCAL_WALLET_SIGNED_SUBMIT_UI_ENABLED ? (
            <NonCustodialSignSubmitPanel apiBaseUrl={apiBaseUrl} />
          ) : null}

          {validation.errors.length > 0 ? (
            <ul className="validationList" aria-label="Wallet preview checks">
              {validation.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          ) : LOCAL_WALLET_SEND_UI_ENABLED ? (
            <p className="mutedText">Local send is pending-state only. No signing material.</p>
          ) : (
            <p className="mutedText">Preview only. No signing or submission.</p>
          )}
          {apiPreview.status === "error" ? (
            <p className="errorText">{apiPreview.error}</p>
          ) : null}
          {walletStatus.status === "error" ? (
            <p className="errorText">{walletStatus.error}</p>
          ) : null}

          <WalletActivity
            activeActivity={selectedActivity}
            activityStatus={activityStatus}
            rows={walletActivity}
            onActivitySelect={setSelectedActivityId}
          />
          <WalletHistory history={walletHistory} />
        </div>

        <pre className="previewBox" aria-label="Wallet transfer draft preview">
          {JSON.stringify(previewJson, null, 2)}
        </pre>
      </div>
    </section>
  );
}

function LocalWalletSendControl({
  enabled,
  errors,
  state,
  onSend,
}: {
  enabled: boolean;
  errors: string[];
  state: LocalWalletSendState;
  onSend: () => void;
}) {
  const data = state.data;
  const metadata = data?.audit_event.metadata;
  const sendDisabled = !enabled || errors.length > 0 || state.status === "loading";

  return (
    <div className="localWalletSend" aria-label="Local Wallet Send">
      <div className="subHeading">
        <h3>Local Wallet Send</h3>
        <span>{enabled ? "feature switch on" : "feature switch off"}</span>
      </div>
      <div className="walletSendGuard" aria-label="Wallet send local-only guard">
        <span>wallet-send only</span>
        <span>wallet submit deferred</span>
        <span>pending_state_only</span>
        <span>no implicit block production</span>
      </div>
      <div className="walletActions">
        <button type="button" onClick={onSend} disabled={sendDisabled}>
          Send Local
        </button>
        <span>{state.status}</span>
      </div>
      {errors.length > 0 ? (
        <ul className="validationList" aria-label="Local wallet send checks">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      ) : null}
      {state.status === "error" ? <p className="errorText">{state.error}</p> : null}
      {data ? (
        <dl className="detailList localWalletSendResult" aria-label="Local wallet send result">
          <dt>Status</dt>
          <dd>{data.status}</dd>
          <dt>Mutation</dt>
          <dd>{data.mutation}</dd>
          <dt>Tx Hash</dt>
          <dd className="mono truncate">{data.transaction.tx_hash}</dd>
          <dt>Local Request</dt>
          <dd className="mono truncate">{metadata?.local_request_id}</dd>
          <dt>Audit Event</dt>
          <dd className="mono truncate">{data.audit_event.event_id}</dd>
          <dt>Pending File</dt>
          <dd className="mono truncate">{data.pending_state.pending_file}</dd>
          <dt>Chain File</dt>
          <dd className="mono truncate">{data.chain_state.chain_file}</dd>
          <dt>Chain</dt>
          <dd>{data.chain_state.chain_unchanged ? "unchanged" : "changed"}</dd>
        </dl>
      ) : null}
    </div>
  );
}

// Key-safety marker note (see scripts/check-wallet-key-safety.mjs): the wallet is
// non-custodial — it signs with an ephemeral in-memory key that is never persisted
// or transmitted; only the public key and the signature are sent.
const NON_CUSTODIAL_SIGNING_NOTE =
  "This wallet is non-custodial: it signs with an ephemeral in-memory Ed25519 key that is never persisted or transmitted — only the public key and the signature are sent to the server.";

function NonCustodialSignSubmitPanel({ apiBaseUrl }: { apiBaseUrl: string }) {
  // The server signed-submit endpoint is private-devnet + test-sender only.
  const chainId = "xriq-devnet";
  const [to, setTo] = useState(DEFAULT_RECIPIENT);
  const [amount, setAmount] = useState("5");
  const [fee, setFee] = useState("2");
  const [nonce, setNonce] = useState("0");
  const [expiresAtHeight, setExpiresAtHeight] = useState("100");
  const [status, setStatus] = useState<"idle" | "signing" | "done" | "error">("idle");
  const [result, setResult] = useState<Ed25519SignedSubmitAcceptedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSignAndSubmit() {
    setStatus("signing");
    setResult(null);
    setError(null);
    try {
      // Fresh ephemeral signer: the key is generated in memory, used once, and
      // never persisted or transmitted — only its public key and the signature
      // leave the wallet.
      const signer = await createEphemeralSigner();
      const fields: Ed25519TransferFields = {
        local_request_id: `local-signed-${Date.now()}`,
        version: "1",
        chain_id: chainId,
        from_address: SIGNED_SUBMIT_TEST_SENDER,
        to_address: to,
        amount_base_units: amount,
        fee_base_units: fee,
        nonce,
        expires_at_height: expiresAtHeight,
      };
      // 1) Ask the server for the canonical hash to sign (sends only the public key).
      const prepared = await prepareSignedSubmitSigningHash(
        apiBaseUrl,
        fields,
        signer.publicKeyHex,
      );
      // 1b) Recompute the canonical signing hash locally and refuse to sign unless it
      // matches the server's — so the wallet signs what it verified, not
      // server-dictated bytes (defends against a hostile/MITM server substituting a
      // different transaction).
      const expectedSigningHash = transactionSigningHashHex(fields, signer.publicKeyHex);
      if (expectedSigningHash !== prepared.transaction_signing_hash) {
        throw new Error(
          "server signing hash does not match the transaction fields — refusing to sign",
        );
      }
      // 2) Sign the hash locally with the ephemeral key.
      const signature = await signer.signHashHex(prepared.transaction_signing_hash);
      // 3) Submit the signed envelope (public key + signature only).
      const accepted = await submitEd25519SignedTransfer(
        apiBaseUrl,
        fields,
        signer.publicKeyHex,
        signature,
        prepared.transaction_signing_hash,
      );
      setResult(accepted);
      setStatus("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setStatus("error");
    }
  }

  const disabled = !LOCAL_WALLET_SIGNED_SUBMIT_UI_ENABLED || status === "signing";

  return (
    <div className="localWalletSignedSubmit" aria-label="Non-custodial ed25519 sign and submit">
      <div className="subHeading">
        <h3>Non-custodial ed25519 sign &amp; submit</h3>
        <span>
          {LOCAL_WALLET_SIGNED_SUBMIT_UI_ENABLED ? "feature switch on" : "feature switch off"}
        </span>
      </div>
      <p className="mutedText">{NON_CUSTODIAL_SIGNING_NOTE}</p>
      <div className="walletFields">
        <label>
          From (test sender)
          <input value={SIGNED_SUBMIT_TEST_SENDER} readOnly />
        </label>
        <label>
          To
          <input value={to} onChange={(event) => setTo(event.target.value)} />
        </label>
        <label>
          Amount
          <input value={amount} onChange={(event) => setAmount(event.target.value)} />
        </label>
        <label>
          Fee
          <input value={fee} onChange={(event) => setFee(event.target.value)} />
        </label>
        <label>
          Nonce
          <input value={nonce} onChange={(event) => setNonce(event.target.value)} />
        </label>
        <label>
          Expires at height
          <input
            value={expiresAtHeight}
            onChange={(event) => setExpiresAtHeight(event.target.value)}
          />
        </label>
      </div>
      <div className="walletActions">
        <button
          type="button"
          onClick={() => void handleSignAndSubmit()}
          disabled={disabled}
        >
          Sign &amp; Submit
        </button>
        <span>{status}</span>
      </div>
      {error ? <p className="errorText">{error}</p> : null}
      {result ? (
        <pre className="previewBox" aria-label="Signed submit result">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

function WalletActionGuards({
  guards,
  onCheck,
}: {
  guards: WalletActionGuardState;
  onCheck: () => void;
}) {
  const actions = Object.keys(ACTION_GUARD_EXPECTATIONS) as WalletMutationAction[];
  const isChecking = actions.some((action) => guards[action].status === "loading");

  return (
    <div className="walletActionGuards" aria-label="Wallet Action Guards">
      <div className="subHeading">
        <h3>Wallet Action Guards</h3>
        <span>disabled submit/send</span>
      </div>
      <div className="walletGuardButtons">
        {actions.map((action) => (
          <button key={action} type="button" disabled>
            {ACTION_GUARD_EXPECTATIONS[action].buttonLabel}
          </button>
        ))}
        <button type="button" onClick={onCheck} disabled={isChecking}>
          Check Guards
        </button>
      </div>
      <div className="miniTable">
        <table>
          <thead>
            <tr>
              <th>Action</th>
              <th>State</th>
              <th>Code</th>
              <th>Flag</th>
              <th>Mutation</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => {
              const expectation = ACTION_GUARD_EXPECTATIONS[action];
              const state = guards[action];
              const data = state.data;
              return (
                <tr key={action}>
                  <td>{expectation.label}</td>
                  <td>{data?.status ?? state.status}</td>
                  <td className="mono truncate">{data?.code ?? expectation.code}</td>
                  <td className="mono truncate">
                    {data?.required_enablement.explicit_flag ?? expectation.flag}
                  </td>
                  <td>{data?.mutation ?? "none"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {actions.map((action) =>
        guards[action].status === "error" ? (
          <p className="errorText" key={action}>
            {ACTION_GUARD_EXPECTATIONS[action].label}: {guards[action].error}
          </p>
        ) : null,
      )}
    </div>
  );
}

function WalletHistory({
  history,
}: {
  history: ApiState<AccountHistoryResponse>;
}) {
  const rows = history.data?.transactions ?? [];

  return (
    <div className="walletActivity walletApiHistory" aria-label="Wallet API History">
      <div className="subHeading">
        <h3>Wallet API History</h3>
        <span>api-backed confirmed history</span>
      </div>
      <div className="miniTable">
        <table>
          <thead>
            <tr>
              <th>Hash</th>
              <th>Direction</th>
              <th>Amount</th>
              <th>Fee</th>
              <th>Block</th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((row) => (
                <tr key={`${row.tx_hash}:${row.direction}`}>
                  <td className="mono truncate">{shortHash(row.tx_hash)}</td>
                  <td>{row.direction}</td>
                  <td>{row.amount_base_units}</td>
                  <td>{row.fee_base_units}</td>
                  <td>{row.block_height}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>
                  {history.status === "loading"
                    ? "Loading wallet API history"
                    : "No API wallet history"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {history.status === "error" ? (
        <p className="errorText">{history.error}</p>
      ) : null}
    </div>
  );
}

function WalletActivity({
  activeActivity,
  activityStatus,
  rows,
  onActivitySelect,
}: {
  activeActivity: WalletActivityRow | null;
  activityStatus: ApiState<WalletTransactionStatusResponse>;
  rows: WalletActivityRow[];
  onActivitySelect: (activityId: string) => void;
}) {
  const activeApiStatus =
    activityStatus.data?.tx_hash === activeActivity?.txHash ? activityStatus.data : null;

  return (
    <div className="walletActivity" aria-label="Wallet Activity">
      <div className="subHeading">
        <h3>Wallet Activity</h3>
        <span>read-only confirmed and pending</span>
      </div>
      <div className="miniTable walletActivityTable">
        <table>
          <thead>
            <tr>
              <th>Hash</th>
              <th>State</th>
              <th>Direction</th>
              <th>Amount</th>
              <th>Block</th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((row) => (
                <tr
                  key={row.id}
                  className={activeActivity?.id === row.id ? "selectedRow" : undefined}
                >
                  <td>
                    <button
                      className="rowButton"
                      type="button"
                      onClick={() => onActivitySelect(row.id)}
                    >
                      {shortHash(row.txHash)}
                    </button>
                  </td>
                  <td>{row.source}</td>
                  <td>{row.direction}</td>
                  <td>{row.amount}</td>
                  <td>{row.block}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>No wallet activity</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="walletActivityDetail">
        <div className="subHeading">
          <h3>Selected Wallet Activity</h3>
          <span>{activeActivity ? activeActivity.source : "idle"}</span>
        </div>
        {activeActivity ? (
          <dl className="detailList">
            <WalletDetail label="Hash" value={activeActivity.txHash} compact />
            <WalletDetail label="Status" value={activeActivity.status} />
            <WalletDetail label="Direction" value={activeActivity.direction} />
            <WalletDetail label="Counterparty" value={activeActivity.counterparty} compact />
            <WalletDetail label="Amount" value={activeActivity.amount} />
            <WalletDetail label="Fee" value={activeActivity.fee} />
            <WalletDetail label="Nonce" value={activeActivity.nonce} />
            <WalletDetail label="Pending Block" value={activeActivity.block} />
            <WalletDetail label="Transaction Index" value={activeActivity.transactionIndex} />
          </dl>
        ) : (
          <p className="mutedText">No wallet activity selected</p>
        )}
      </div>

      <div
        className="walletActivityDetail walletApiStatusDetail"
        aria-label="Wallet API Transaction Status"
      >
        <div className="subHeading">
          <h3>Wallet API Transaction Status</h3>
          <span>api-backed status</span>
        </div>
        {activeApiStatus ? (
          <dl className="detailList">
            <WalletDetail label="API Status" value={activeApiStatus.status} />
            <WalletDetail
              label="API Block Height"
              value={formatOptionalHeight(activeApiStatus.block_height)}
            />
            <WalletDetail
              label="API Block Hash"
              value={activeApiStatus.block_hash ?? "pending"}
              compact
            />
            <WalletDetail
              label="API Transaction Index"
              value={formatOptionalHeight(activeApiStatus.transaction_index)}
            />
            <WalletDetail label="API Warning" value={activeApiStatus.warning} compact />
          </dl>
        ) : (
          <p className="mutedText">
            {activeActivity ? "Loading wallet activity status" : "No API status selected"}
          </p>
        )}
        {activityStatus.status === "error" ? (
          <p className="errorText">{activityStatus.error}</p>
        ) : null}
      </div>
    </div>
  );
}

function WalletDetail({
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

function BalanceMetric({ label, value }: { label: string; value: bigint | null }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value === null ? "-" : value.toString()}</strong>
    </div>
  );
}

function validateDraft({
  fromAccount,
  fromAddress,
  toAddress,
  amount,
  fee,
  nonce,
  expiresAtHeight,
}: {
  fromAccount: AccountSummary | null;
  fromAddress: string;
  toAddress: string;
  amount: string;
  fee: string;
  nonce: string;
  expiresAtHeight: string;
}): DraftValidation {
  const errors: string[] = [];
  const amountValue = parseInteger(amount);
  const feeValue = parseInteger(fee);
  const nonceValue = parseInteger(nonce);
  const expiryValue =
    expiresAtHeight.trim() === "" ? 0n : parseInteger(expiresAtHeight);
  const balance = fromAccount ? parseInteger(fromAccount.balance_base_units) : null;
  const debit =
    amountValue === null || feeValue === null ? null : amountValue + feeValue;
  const remaining =
    balance === null || debit === null || debit > balance ? null : balance - debit;

  if (!fromAddress) {
    errors.push("Sender is required.");
  }
  if (!toAddress.trim()) {
    errors.push("Recipient is required.");
  }
  if (fromAddress && fromAddress === toAddress.trim()) {
    errors.push("Sender and recipient must differ.");
  }
  if (amountValue === null || amountValue <= 0n) {
    errors.push("Amount must be a positive integer.");
  }
  if (feeValue === null || feeValue < MIN_PRIVATE_DEVNET_FEE) {
    errors.push("Fee must be at least 2 base units.");
  }
  if (nonceValue === null) {
    errors.push("Nonce must be a non-negative integer.");
  }
  if (expiryValue === null) {
    errors.push("Expiry must be empty or a non-negative integer.");
  }
  if (balance !== null && debit !== null && debit > balance) {
    errors.push("Debit exceeds available balance.");
  }

  return { errors, balance, debit, remaining };
}

export function walletActivityRows(
  snapshot: ExplorerSnapshot | null,
  address: string,
): WalletActivityRow[] {
  if (!snapshot || !address) {
    return [];
  }

  const confirmed = snapshot.transactions.transactions
    .filter((transaction) => walletTransactionMatches(transaction, address))
    .map((transaction) => confirmedActivityRow(transaction, address));
  const pending = snapshot.mempool.entries
    .filter((entry) => walletPendingMatches(entry, address))
    .map((entry) => pendingActivityRow(entry, address));

  return [...pending, ...confirmed];
}

function walletTransactionMatches(transaction: TransactionSummary, address: string) {
  return transaction.from_address === address || transaction.to_address === address;
}

function walletPendingMatches(entry: MempoolEntry, address: string) {
  return entry.from_address === address || entry.to_address === address;
}

function confirmedActivityRow(transaction: TransactionSummary, address: string): WalletActivityRow {
  const direction = transaction.from_address === address ? "sent" : "received";
  const counterparty =
    direction === "sent" ? transaction.to_address : transaction.from_address;
  return {
    id: `confirmed:${transaction.tx_hash}:${direction}`,
    txHash: transaction.tx_hash,
    source: "confirmed",
    status: transaction.status,
    direction,
    amount: transaction.amount_base_units,
    fee: transaction.fee_base_units,
    nonce: transaction.nonce,
    block: transaction.block_height.toString(),
    transactionIndex: transaction.transaction_index.toString(),
    counterparty,
  };
}

function pendingActivityRow(entry: MempoolEntry, address: string): WalletActivityRow {
  const direction = entry.from_address === address ? "sent" : "received";
  const counterparty = direction === "sent" ? entry.to_address : entry.from_address;
  return {
    id: `pending:${entry.tx_hash}:${direction}`,
    txHash: entry.tx_hash,
    source: "pending",
    status: entry.status,
    direction,
    amount: entry.amount_base_units,
    fee: entry.fee_base_units,
    nonce: entry.nonce,
    block: "pending",
    transactionIndex: "pending",
    counterparty,
  };
}

function parseInteger(value: string): bigint | null {
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  return BigInt(trimmed);
}

function parseNullableInteger(value: string | null): bigint | null {
  return value === null ? null : parseInteger(value);
}

function defaultRecipient(accounts: AccountSummary[], fromAddress: string) {
  return (
    accounts.find((account) => account.address !== fromAddress)?.address ??
    DEFAULT_RECIPIENT
  );
}

function shortAddress(value: string) {
  return value.length > 18 ? `${value.slice(0, 12)}...${value.slice(-4)}` : value;
}

function shortHash(value: string) {
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}

function nextLocalWalletSendRequestId() {
  return `wallet-send-ui-${Date.now().toString(36)}`;
}

function formatOptionalHeight(value: number | null) {
  return value === null ? "pending" : value.toString();
}

function initialActionGuards(): WalletActionGuardState {
  return {
    submit: { status: "idle", data: null, error: null },
    send: { status: "idle", data: null, error: null },
  };
}

function validateActionRefusalContract(
  action: WalletMutationAction,
  data: WalletMutationRefusalResponse,
) {
  const expected = ACTION_GUARD_EXPECTATIONS[action];
  const errors: string[] = [];

  if (data.environment !== "private-devnet") {
    errors.push("environment must be private-devnet");
  }
  if (data.network !== "xriq-devnet") {
    errors.push("network must be xriq-devnet");
  }
  if (!data.endpoint.toLowerCase().includes(action)) {
    errors.push(`${expected.label} endpoint marker is missing`);
  }
  if (data.enabled !== false) {
    errors.push(`${expected.label} guard must be disabled`);
  }
  if (data.mutation !== "none") {
    errors.push(`${expected.label} mutation must be none`);
  }
  if (data.status !== "disabled") {
    errors.push(`${expected.label} status must be disabled`);
  }
  if (data.code !== expected.code) {
    errors.push(`${expected.label} code must be ${expected.code}`);
  }
  if (data.warning !== PREFLIGHT_WARNING) {
    errors.push(`${expected.label} warning must be ${PREFLIGHT_WARNING}`);
  }
  if (data.required_enablement.mode !== "local-private-devnet") {
    errors.push(`${expected.label} mode must be local-private-devnet`);
  }
  if (data.required_enablement.explicit_flag !== expected.flag) {
    errors.push(`${expected.label} flag must be ${expected.flag}`);
  }
  if (!data.required_enablement.audit_event_required) {
    errors.push(`${expected.label} audit event must be required`);
  }
  if (!data.required_enablement.test_identity_only) {
    errors.push(`${expected.label} must be test-identity-only`);
  }
  for (const field of [
    "from_address",
    "to_address",
    "amount_base_units",
    "fee_base_units",
    "nonce",
    "expires_at_height",
  ]) {
    if (!data.request_fields.includes(field)) {
      errors.push(`${expected.label} request field missing: ${field}`);
    }
  }

  return errors;
}
