import { useEffect, useMemo, useState } from "react";
import { AccountSummary, ExplorerSnapshot } from "./api";

const DEFAULT_RECIPIENT = "xriqdev1bobbb00000000000";
const MIN_PRIVATE_DEVNET_FEE = 2n;
const PREVIEW_WARNING = "private-devnet-preview-only-no-signing-no-submit";

interface WalletShellProps {
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

export function WalletShell({
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
  }

  return (
    <section className="panel detailPanel widePanel walletPanel">
      <div className="panelTitle">
        <h2>Wallet Preview</h2>
        <span>{validation.errors.length === 0 ? "ready" : "check"}</span>
      </div>

      <div className="walletGrid">
        <div className="walletForm" aria-label="Private-devnet wallet transfer preview">
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
              onChange={(event) => setToAddress(event.target.value)}
              spellCheck={false}
            />
          </label>

          <div className="walletFields">
            <label>
              Amount
              <input
                inputMode="numeric"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </label>
            <label>
              Fee
              <input
                inputMode="numeric"
                value={fee}
                onChange={(event) => setFee(event.target.value)}
              />
            </label>
            <label>
              Nonce
              <input
                inputMode="numeric"
                value={nonce}
                onChange={(event) => setNonce(event.target.value)}
              />
            </label>
            <label>
              Expires
              <input
                inputMode="numeric"
                value={expiresAtHeight}
                onChange={(event) => setExpiresAtHeight(event.target.value)}
              />
            </label>
          </div>

          <div className="balanceStrip" aria-label="Transfer balance preview">
            <BalanceMetric label="Available" value={validation.balance} />
            <BalanceMetric label="Debit" value={validation.debit} />
            <BalanceMetric label="Remaining" value={validation.remaining} />
          </div>

          {validation.errors.length > 0 ? (
            <ul className="validationList" aria-label="Wallet preview checks">
              {validation.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          ) : (
            <p className="mutedText">Preview only. No signing or submission.</p>
          )}
        </div>

        <pre className="previewBox" aria-label="Wallet transfer draft preview">
          {JSON.stringify(preview, null, 2)}
        </pre>
      </div>
    </section>
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

function parseInteger(value: string): bigint | null {
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  return BigInt(trimmed);
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
