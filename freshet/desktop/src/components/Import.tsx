import { useState } from "react";

import { autofillApply, autofillImport, errorText, money } from "../api";
import type { ComputeInput, ImportPreview, ProposalView } from "../types";

interface Props {
  input: ComputeInput;
  onApply: (facts: Record<string, string>) => void;
}

/** Everything that would change, pre-ticked. Matches are nothing to decide. */
const changesIn = (preview: ImportPreview): ProposalView[] =>
  preview.proposals.filter((p) => p.disposition !== "matches");

export default function Import({ input, onApply }: Props) {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [accept, setAccept] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);

  const run = async (source: "cra" | "sample") => {
    setBusy(true);
    setFailure(null);
    setApplied(false);
    try {
      const got = await autofillImport(input, source);
      setPreview(got);
      // Conflicts start unticked: overwriting what someone typed is their call.
      setAccept(
        new Set(
          changesIn(got)
            .filter((p) => p.disposition === "new")
            .map((p) => p.fact_key),
        ),
      );
    } catch (e) {
      setPreview(null);
      setFailure(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const toggle = (key: string) =>
    setAccept((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const confirm = async () => {
    setBusy(true);
    try {
      onApply(await autofillApply(input, [...accept]));
      setApplied(true);
    } catch (e) {
      setFailure(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const changes = preview ? changesIn(preview) : [];
  const unchanged = preview ? preview.proposals.length - changes.length : 0;

  return (
    <div className="pane-body">
      <h2>Import from CRA</h2>
      <p className="hint">
        Auto-fill my return brings in the slips CRA already holds — T4s, T5s and
        the rest. You sign in to your own CRA account; Freshet never sees or
        stores your CRA password. Nothing is entered on your return until you
        confirm it below.
      </p>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="primary" disabled={busy} onClick={() => void run("cra")}>
          Import from CRA
        </button>
        <button className="ghost" disabled={busy} onClick={() => void run("sample")}>
          Preview with sample data
        </button>
      </div>

      {failure && (
        <div className="notice warn" style={{ marginTop: 16 }}>
          <strong>Import unavailable</strong>
          {failure}
          <p style={{ margin: "8px 0 0" }}>
            You can still see how the import works end to end with sample data.
          </p>
        </div>
      )}

      {preview && (
        <>
          <div className="notice info" style={{ marginTop: 20 }}>
            <strong>
              {preview.slip_count} slips from {preview.source_label}
            </strong>
            {changes.length} value{changes.length === 1 ? "" : "s"} to review
            {unchanged > 0 && `, ${unchanged} already matching what you entered`}.
            CRA does not have most slips until mid-March — anything missing here
            may simply not have reached them yet.
          </div>

          {changes.length > 0 && (
            <>
              <h2 style={{ marginTop: 22 }}>Proposed values</h2>
              <ul className="import-list">
                {changes.map((p) => (
                  <li key={p.fact_key} className={p.disposition}>
                    <label className="import-row">
                      <input
                        type="checkbox"
                        checked={accept.has(p.fact_key)}
                        onChange={() => toggle(p.fact_key)}
                      />
                      <span className="import-main">
                        <span className="import-label">
                          {p.description}
                          {p.disposition === "conflict" && (
                            <span className="tag conflict">differs</span>
                          )}
                        </span>

                        {p.from.length > 1 && (
                          <span className="import-detail">
                            {p.from
                              .map(
                                (c) =>
                                  `${money(c.amount)} from ${c.issuer} (${c.slip_type} box ${c.box_label})`,
                              )
                              .join(" + ")}
                          </span>
                        )}
                        {p.from.length === 1 && (
                          <span className="import-detail">
                            {p.from[0].issuer} · {p.from[0].slip_type} box{" "}
                            {p.from[0].box_label}
                          </span>
                        )}

                        {p.current !== null && (
                          <span className="import-detail">
                            You entered {money(p.current)} — accepting replaces it.
                          </span>
                        )}
                      </span>
                      <span className="import-amount">{money(p.total)}</span>
                    </label>
                  </li>
                ))}
              </ul>

              <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
                <button
                  className="primary"
                  disabled={busy || accept.size === 0}
                  onClick={() => void confirm()}
                >
                  Enter {accept.size} value{accept.size === 1 ? "" : "s"} on my return
                </button>
                {applied && <span className="save-state saved">Entered</span>}
              </div>
            </>
          )}

          {preview.unmapped.length > 0 && (
            <div className="notice warn" style={{ marginTop: 22 }}>
              <strong>CRA sent amounts this version cannot handle</strong>
              These are real amounts CRA already knows about. This build cannot
              place them on the return, so you must not file without dealing with
              them.
              <ul>
                {preview.unmapped.map((u) => (
                  <li key={`${u.slip_type}-${u.box_label}`}>
                    {u.slip_type} box {u.box_label} — {u.description}:{" "}
                    {money(u.amount)} from {u.issuer}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {preview.rooms.length > 0 && (
            <>
              <h2 style={{ marginTop: 24 }}>Contribution room</h2>
              <p className="hint">
                These are not entered on your return. They are what CRA had on
                file, and each carries the date it was computed.
              </p>
              {preview.rooms.map((r) => (
                <div className="room" key={r.label}>
                  <div className="room-head">
                    <span>{r.label}</span>
                    <span className="room-amount">{money(r.amount)}</span>
                  </div>
                  <div className="room-advisory">{r.advisory}</div>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
