import { useEffect, useRef, useState } from "react";

import { advisorChat, errorText, grantConsent } from "../api";
import type { ComputeInput, SettingsView, Turn } from "../types";

type Msg = Turn & { redacted?: string[]; failed?: boolean };

/** Rust `Debug` names for PII kinds, made readable. */
const PII_LABELS: Record<string, string> = {
  Sin: "social insurance number",
  BusinessNumber: "business number",
  CreditCard: "card number",
  Email: "email address",
  Phone: "phone number",
  PostalCode: "postal code",
  DateOfBirth: "date",
};

const SUGGESTIONS = [
  "What is my biggest opportunity to save tax this year?",
  "How much more should I put into my RRSP, and what would it save me?",
  "Am I missing any credits I am entitled to?",
  "Explain my marginal rate in plain language.",
];

interface Props {
  settings: SettingsView | null;
  input: ComputeInput;
  onSettings: (s: SettingsView) => void;
  onOpenSettings: () => void;
}

export default function Advisor({ settings, input, onSettings, onOpenSettings }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [msgs, busy]);

  if (!settings?.provider) {
    return (
      <div className="pane-body">
        <div className="notice info">
          <strong>No model connected</strong>
          Bring your own key — Anthropic, OpenAI, your Biber gateway, or a local
          model running on this machine. Freshet never proxies your data through
          our servers.
        </div>
        <button className="primary" onClick={onOpenSettings}>
          Open settings
        </button>
      </div>
    );
  }

  if (!settings.has_key) {
    return (
      <div className="pane-body">
        <div className="notice warn">
          <strong>No API key saved for {settings.provider_label}</strong>
          Add it in settings. It goes into the operating system keychain, never
          into a config file.
        </div>
        <button className="primary" onClick={onOpenSettings}>
          Open settings
        </button>
      </div>
    );
  }

  if (settings.is_remote && !settings.consent_granted) {
    return (
      <div className="pane-body">
        <div className="notice warn">
          <strong>Consent needed before anything is sent</strong>
          <p style={{ margin: "8px 0" }}>
            To answer questions about your return, Freshet would send{" "}
            <strong>{settings.provider_label}</strong> the line numbers and
            amounts on this return, plus whatever you type in the chat.
          </p>
          <p style={{ margin: "8px 0" }}>
            It never sends your name, SIN, address, date of birth or account
            numbers. If any of those appear in something you type, they are
            stripped before the message leaves this machine, and if the check
            cannot strip them the message is not sent at all.
          </p>
          <p style={{ margin: "8px 0 0" }}>
            Providers commonly retain prompts for abuse monitoring. If you would
            rather nothing left this machine, switch to a local model in
            settings — that needs no consent at all.
          </p>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="primary"
            onClick={() => grantConsent().then(onSettings).catch(() => undefined)}
          >
            Send to {settings.provider_label}
          </button>
          <button className="ghost" onClick={onOpenSettings}>
            Use a local model instead
          </button>
        </div>
      </div>
    );
  }

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;

    const history: Turn[] = msgs
      .filter((m) => !m.failed)
      .map(({ role, content }) => ({ role, content }));

    setMsgs((m) => [...m, { role: "user", content: message }]);
    setDraft("");
    setBusy(true);

    try {
      const reply = await advisorChat(input, history, message);
      setMsgs((m) => {
        const next = [...m];
        // Attach the redaction record to the message it applied to.
        const last = next[next.length - 1];
        if (last?.role === "user" && reply.redacted.length) {
          next[next.length - 1] = { ...last, redacted: reply.redacted };
        }
        return [...next, { role: "assistant", content: reply.reply }];
      });
    } catch (e) {
      setMsgs((m) => [
        ...m,
        { role: "assistant", content: errorText(e), failed: true },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-log" ref={logRef}>
        {msgs.length === 0 && (
          <div className="empty">
            <p>
              Ask about your return. The advisor can see your line numbers and
              amounts — nothing that identifies you.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} style={{ display: "contents" }}>
            <div
              className={`bubble ${m.failed ? "error" : m.role}`}
            >
              {m.content}
            </div>
            {m.redacted?.length ? (
              <div className="redacted-tag">
                Removed before sending:{" "}
                {m.redacted.map((k) => PII_LABELS[k] ?? k).join(", ")}
              </div>
            ) : null}
          </div>
        ))}

        {busy && <div className="bubble assistant thinking">Thinking…</div>}
      </div>

      <div className="chat-input">
        <textarea
          value={draft}
          placeholder="Ask about deductions, credits, RRSP room…"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send(draft);
            }
          }}
        />
        <button
          className="primary"
          disabled={busy || !draft.trim()}
          onClick={() => void send(draft)}
        >
          Send
        </button>
      </div>
    </div>
  );
}
