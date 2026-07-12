import { FormEvent, useState } from "react";
import {
  ExplorerSnapshot,
  TestnetFaucetResponse,
  requestTestnetFaucet,
} from "./api";

// Testnet Faucet panel. Requests valueless test units for a public address.
// TEST-ONLY: the native unit has no monetary value. This page never handles
// wallet secrets; only a public address is entered, and signing stays
// server-side / CLI-only. The faucet is available only when connected to a
// testnet node (xriq-testnet) running as serve-private with --network testnet.

const TESTNET_NETWORK = "xriq-testnet";
const ADDRESS_PREFIX = "xriqdev1";
const ADDRESS_MIN_LENGTH = ADDRESS_PREFIX.length + 16;

type FaucetState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: TestnetFaucetResponse }
  | { status: "error"; error: string };

function validateAddress(address: string): string | null {
  if (!address.startsWith(ADDRESS_PREFIX)) {
    return "Address must start with xriqdev1.";
  }
  if (address.length < ADDRESS_MIN_LENGTH) {
    return "Address is too short.";
  }
  if (!/^[a-z0-9]+$/.test(address)) {
    return "Address must be lowercase letters and digits only.";
  }
  return null;
}

export function TestnetFaucetPanel({
  apiBaseUrl,
  snapshot,
}: {
  apiBaseUrl: string;
  snapshot: ExplorerSnapshot | null;
}) {
  const [address, setAddress] = useState("");
  const [state, setState] = useState<FaucetState>({ status: "idle" });

  const network = snapshot?.network.network ?? TESTNET_NETWORK;
  const isTestnet = network === TESTNET_NETWORK;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = address.trim();
    const validationError = validateAddress(trimmed);
    if (validationError) {
      setState({ status: "error", error: validationError });
      return;
    }
    setState({ status: "loading" });
    try {
      const result = await requestTestnetFaucet(apiBaseUrl, trimmed);
      setState({ status: "success", result });
    } catch (error) {
      setState({
        status: "error",
        error: error instanceof Error ? error.message : "Faucet request failed",
      });
    }
  }

  return (
    <section className="panel faucetPanel">
      <div className="panelTitle">
        <h2>Testnet Faucet</h2>
        <span>{network}</span>
      </div>
      <p className="mutedText">
        Valueless test units — TEST-ONLY, no monetary value. Only a public
        address is entered here; this page never handles wallet secrets.
      </p>
      {!isTestnet ? (
        <p className="mutedText">
          Connect to a testnet node (xriq-testnet) to request test units.
        </p>
      ) : null}
      <form className="faucetForm" onSubmit={handleSubmit}>
        <label htmlFor="faucetAddress">Recipient address</label>
        <input
          id="faucetAddress"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="xriqdev1..."
          spellCheck={false}
        />
        <button type="submit" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Requesting" : "Request test units"}
        </button>
      </form>
      {state.status === "error" ? (
        <p className="errorText">{state.error}</p>
      ) : null}
      {state.status === "success" ? (
        <dl className="detailList">
          <dt>Chain</dt>
          <dd>{state.result.chain_id}</dd>
          <dt>Dispensed</dt>
          <dd>{state.result.amount_base_units}</dd>
          <dt>Recipient balance</dt>
          <dd>{state.result.recipient_balance_base_units}</dd>
          <dt>Block</dt>
          <dd>{state.result.block_height}</dd>
        </dl>
      ) : null}
    </section>
  );
}
