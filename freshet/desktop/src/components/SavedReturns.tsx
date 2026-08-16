import { useState } from "react";

import { deleteReturn, errorText, whenLocal } from "../api";
import type { ReturnSummary, StorageStatus } from "../types";

interface Props {
  storage: StorageStatus | null;
  returns: ReturnSummary[];
  openId: string | null;
  saveError: string | null;
  onOpen: (id: string) => Promise<void>;
  onNew: () => void;
  onDeleted: (remaining: ReturnSummary[], deletedId: string) => void;
}

export default function SavedReturns({
  storage,
  returns,
  openId,
  saveError,
  onOpen,
  onNew,
  onDeleted,
}: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  if (storage && !storage.available) {
    return (
      <div className="pane-body">
        <div className="notice danger">
          <strong>Encrypted storage is unavailable</strong>
          {storage.error ?? "The vault could not be opened."}
          <p style={{ margin: "8px 0 0" }}>
            You can still prepare a return, but nothing will be saved. Close the
            app without copying your figures somewhere and they are gone.
          </p>
        </div>
      </div>
    );
  }

  const remove = async (id: string) => {
    setBusy(id);
    setFailure(null);
    try {
      onDeleted(await deleteReturn(id), id);
    } catch (e) {
      setFailure(errorText(e));
    } finally {
      setBusy(null);
      setConfirming(null);
    }
  };

  return (
    <div className="pane-body">
      <h2>Saved returns</h2>
      <p className="hint">
        Everything is encrypted on this machine with a key held in your{" "}
        {navigator.platform.startsWith("Mac") ? "macOS Keychain" : "Windows Credential Manager"}.
        Returns save themselves as you type.
      </p>

      <button className="primary" onClick={onNew}>
        Start a new return
      </button>

      {saveError && (
        <div className="notice danger" style={{ marginTop: 16 }}>
          <strong>The last autosave failed</strong>
          {saveError}
        </div>
      )}
      {failure && (
        <div className="notice danger" style={{ marginTop: 16 }}>
          {failure}
        </div>
      )}

      {returns.length === 0 ? (
        <p className="hint" style={{ marginTop: 20 }}>
          Nothing saved yet. A return appears here as soon as you enter an amount.
        </p>
      ) : (
        <ul className="saved-list">
          {returns.map((r) => (
            <li key={r.id} className={r.id === openId ? "open" : ""}>
              <div className="saved-main">
                <div className="saved-label">
                  {r.label}
                  {r.id === openId && <span className="saved-badge">open</span>}
                </div>
                <div className="saved-meta">
                  T1 · {r.tax_year} · {r.province.toUpperCase()} · saved{" "}
                  {whenLocal(r.updated_unix)}
                </div>
              </div>

              {confirming === r.id ? (
                <div className="saved-actions">
                  <button
                    className="ghost danger-text"
                    disabled={busy === r.id}
                    onClick={() => void remove(r.id)}
                  >
                    Delete permanently
                  </button>
                  <button className="ghost" onClick={() => setConfirming(null)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="saved-actions">
                  <button className="ghost" onClick={() => void onOpen(r.id)}>
                    Open
                  </button>
                  <button className="ghost" onClick={() => setConfirming(r.id)}>
                    Delete
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="notice warn" style={{ marginTop: 24 }}>
        <strong>There is no way to recover this vault</strong>
        The key lives only in your operating system's credential store. If that
        entry is lost — a wiped machine, a new user profile — the saved returns
        cannot be decrypted by us or by anyone else. Keep your slips and receipts.
      </div>

      {storage?.path && (
        <p className="hint" style={{ marginTop: 12, wordBreak: "break-all" }}>
          Vault file: {storage.path}
        </p>
      )}
    </div>
  );
}
