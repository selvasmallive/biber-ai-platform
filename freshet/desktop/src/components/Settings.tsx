import { useEffect, useState } from "react";

import {
  errorText,
  installLicence,
  licenceStatus,
  removeLicence,
  revokeConsent,
  setProvider,
} from "../api";
import type { LicenceView, Provider, SettingsView } from "../types";

type Kind = Provider["kind"];

const PRESETS: Record<
  Kind,
  { label: string; model: string; baseUrl?: string; note: string }
> = {
  anthropic: {
    label: "Anthropic",
    model: "claude-opus-5",
    note: "Your key goes to the OS keychain and is sent only to api.anthropic.com.",
  },
  open_ai: {
    label: "OpenAI",
    model: "gpt-4o",
    note: "Your key goes to the OS keychain and is sent only to api.openai.com.",
  },
  biber: {
    label: "Biber gateway",
    model: "biber-1",
    baseUrl: "https://",
    note: "Any OpenAI-compatible endpoint you control. Point this at your Biber AI gateway.",
  },
  local: {
    label: "Local model",
    model: "llama3.1",
    baseUrl: "http://127.0.0.1:11434/v1",
    note: "Runs on this machine. Nothing leaves the device, so no consent is required and no key is needed.",
  },
};

/** A date a person can read, not a timestamp. */
const onDate = (unix: number): string =>
  new Date(unix * 1000).toLocaleDateString("en-CA", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

function Licence({ taxYear }: { taxYear: number }) {
  const [state, setState] = useState<LicenceView | null>(null);
  const [entry, setEntry] = useState("");
  const [online, setOnline] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    licenceStatus(taxYear).then(setState).catch(() => undefined);
  }, [taxYear]);

  const install = async () => {
    setFailure(null);
    try {
      setState(await installLicence(entry.trim(), online, taxYear));
      setEntry("");
      setOnline(false);
    } catch (e) {
      setFailure(errorText(e));
    }
  };

  return (
    <>
      <h2 style={{ marginTop: 28 }}>Licence</h2>
      <p className="hint">
        Preparing a return is free and always will be. Filing needs a licence,
        which is emailed to you when you buy. Paste it below — it is checked on
        this machine, and Freshet contacts nothing to do it.
      </p>

      {state?.dev_licences_compiled_in && (
        <div className="notice warn">
          <strong>This is a development build</strong>
          It accepts the built-in development and CRA-certification licences. A
          release build does not contain them at all.
        </div>
      )}

      {state?.present ? (
        <>
          <div className={`notice ${state.entitled ? "info" : "warn"}`}>
            <strong>
              {state.kind}
              {state.key && ` · ${state.key}`}
            </strong>
            {state.explanation}
            {state.coverage && (
              <div style={{ marginTop: 6 }}>
                Covers {state.coverage} · {state.allowance} · issued to{" "}
                {state.licensee}
              </div>
            )}
            {/* A professional sees the word, not a number counting down. */}
            {state.returns_left !== null && (
              <div style={{ marginTop: 6 }}>
                {state.returns_filed} filed · {state.returns_left} remaining
              </div>
            )}
            {/* Always shown, from the day the licence is installed. A date
                someone has seen all along cannot ambush them later. */}
            <div style={{ marginTop: 6 }}>
              {state.expires_unix
                ? `Covers filing until ${onDate(state.expires_unix)}`
                : "Does not expire"}
            </div>
          </div>

          {state.standing_note && (
            <div className={`notice ${state.standing_urgent ? "warn" : "info"}`}>
              {state.standing_note}
            </div>
          )}
          <button
            className="ghost"
            onClick={() =>
              void removeLicence(taxYear).then(setState).catch(() => undefined)
            }
          >
            Remove this licence
          </button>
        </>
      ) : (
        <>
          <div className="field">
            <label htmlFor="licenceEntry">Licence, or licence key</label>
            <textarea
              id="licenceEntry"
              rows={3}
              placeholder="Paste your licence here, or enter FRSH-XXXX-XXXX-XXXX-XXXX"
              value={entry}
              onChange={(e) => setEntry(e.target.value)}
            />
          </div>

          <label className="hint" style={{ display: "block", marginBottom: 10 }}>
            <input
              type="checkbox"
              checked={online}
              onChange={(e) => setOnline(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Verify this key online
            <div style={{ marginLeft: 24 }}>
              Only needed if you have a key but not the licence itself. Leave it
              off and nothing leaves this machine. Pasting a licence never
              contacts anyone either way.
            </div>
          </label>

          <button
            className="primary"
            disabled={!entry.trim()}
            onClick={() => void install()}
          >
            {online ? "Verify online and install" : "Install"}
          </button>
        </>
      )}

      {failure && (
        <div className="notice danger" style={{ marginTop: 14 }}>
          <strong>Could not activate</strong>
          {failure}
        </div>
      )}
    </>
  );
}

interface Props {
  settings: SettingsView | null;
  onSettings: (s: SettingsView) => void;
  taxYear: number;
}

export default function Settings({ settings, onSettings, taxYear }: Props) {
  const [kind, setKind] = useState<Kind>("anthropic");
  const [model, setModel] = useState(PRESETS.anthropic.model);
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  // Adopt whatever is already configured, once it arrives.
  useEffect(() => {
    const p = settings?.provider;
    if (!p) return;

    setKind(p.kind);
    setModel(p.model);
    if (p.kind === "biber" || p.kind === "local") setBaseUrl(p.base_url);
  }, [settings?.provider]);

  const preset = PRESETS[kind];
  const needsUrl = kind === "biber" || kind === "local";
  const needsKey = kind !== "local";

  const pick = (next: Kind) => {
    setKind(next);
    setModel(PRESETS[next].model);
    setBaseUrl(PRESETS[next].baseUrl ?? "");
    setStatus(null);
    setFailure(null);
  };

  const save = async () => {
    setStatus(null);
    setFailure(null);

    const provider: Provider = needsUrl
      ? ({ kind, model, base_url: baseUrl } as Provider)
      : ({ kind, model } as Provider);

    try {
      const view = await setProvider(provider, apiKey.trim() || null);
      onSettings(view);
      setApiKey("");
      setStatus(
        view.is_remote
          ? "Saved. You will be asked to consent before anything is sent."
          : "Saved. Nothing will leave this machine.",
      );
    } catch (e) {
      setFailure(errorText(e));
    }
  };

  return (
    <div className="pane-body">
      <h2>Model provider</h2>
      <p className="hint">
        Freshet is bring-your-own-key. Inference is never proxied through our
        servers, so your return is only ever seen by a provider you chose.
      </p>

      <div className="field">
        <label htmlFor="kind">Provider</label>
        <select id="kind" value={kind} onChange={(e) => pick(e.target.value as Kind)}>
          {(Object.keys(PRESETS) as Kind[]).map((k) => (
            <option key={k} value={k}>
              {PRESETS[k].label}
            </option>
          ))}
        </select>
      </div>

      <p className="hint">{preset.note}</p>

      <div className="field">
        <label htmlFor="model">Model</label>
        <input
          id="model"
          type="text"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
      </div>

      {needsUrl && (
        <div className="field">
          <label htmlFor="baseUrl">Base URL</label>
          <input
            id="baseUrl"
            type="text"
            value={baseUrl}
            placeholder="https://your-gateway/v1"
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </div>
      )}

      {needsKey && (
        <div className="field">
          <label htmlFor="apiKey">
            API key
            <span className="box">
              {settings?.has_key ? "one is already saved" : "not set"}
            </span>
          </label>
          <input
            id="apiKey"
            type="password"
            value={apiKey}
            placeholder={settings?.has_key ? "leave blank to keep the saved key" : "sk-…"}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>
      )}

      <button className="primary" onClick={() => void save()} disabled={!model.trim()}>
        Save
      </button>

      {status && (
        <div className="notice info" style={{ marginTop: 16 }}>
          {status}
        </div>
      )}
      {failure && (
        <div className="notice danger" style={{ marginTop: 16 }}>
          <strong>Could not save</strong>
          {failure}
        </div>
      )}

      <Licence taxYear={taxYear} />

      <h2 style={{ marginTop: 28 }}>Data sharing</h2>

      {settings?.consent_granted ? (
        <>
          <div className="notice info">
            <strong>Consent granted for {settings.provider_label}</strong>
            Line numbers and amounts from your return are sent with each
            question. Identifying details are stripped first.
          </div>
          <button
            className="ghost"
            onClick={() => void revokeConsent().then(onSettings).catch(() => undefined)}
          >
            Revoke consent
          </button>
        </>
      ) : (
        <div className="notice info">
          {settings?.is_remote
            ? "No consent given yet. Nothing has been sent, and the advisor will ask before it sends anything."
            : "A local model needs no consent, because nothing leaves this machine."}
        </div>
      )}
    </div>
  );
}
