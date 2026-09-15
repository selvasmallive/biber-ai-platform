import { useRef, useState } from "react";

import { open, seal, type Sealed } from "../crypto";

interface Props {
  period: { start: string; end: string };
  province: string;
  facts: Record<string, string>;
  onRestore: (
    period: { start: string; end: string },
    province: string,
    facts: Record<string, string>,
  ) => void;
}

/// The file version, separate from the envelope's. The envelope describes how
/// the bytes were encrypted; this describes what they mean once decrypted.
const BACKUP_VERSION = 1;

interface Backup {
  version: number;
  saved: string;
  period: { start: string; end: string };
  province: string;
  facts: Record<string, string>;
}

/// Taking the work away.
///
/// A web product that holds the only copy of a return has quietly made itself
/// impossible to leave, and a corporation cannot accept that for a tax filing
/// it has to keep for six years. So the work is exportable, as a single
/// encrypted file the user holds.
///
/// It is encrypted rather than plain JSON because the alternative is a
/// financial statement sitting in a downloads folder. The passphrase never
/// reaches us, and there is no recovery — which is worth saying before someone
/// commits, not after.
export function Backup({ period, province, facts, onRestore }: Props) {
  const [passphrase, setPassphrase] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const save = async () => {
    if (passphrase.length < 8) {
      setStatus("Choose a passphrase of at least 8 characters.");
      return;
    }

    setBusy(true);
    try {
      const backup: Backup = {
        version: BACKUP_VERSION,
        saved: new Date().toISOString(),
        period,
        province,
        facts,
      };

      const sealed = await seal(JSON.stringify(backup), passphrase);
      const blob = new Blob([JSON.stringify(sealed)], {
        type: "application/octet-stream",
      });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `freshet-t2-${period.end}.freshet`;
      a.click();
      URL.revokeObjectURL(url);

      setStatus("Saved. Keep the passphrase — it cannot be recovered.");
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  };

  const load = async (file: File) => {
    setBusy(true);
    try {
      const sealed: Sealed = JSON.parse(await file.text());
      const backup: Backup = JSON.parse(await open(sealed, passphrase));

      if (backup.version !== BACKUP_VERSION) {
        setStatus("That file was written by a newer version of Freshet.");
        return;
      }

      onRestore(backup.period, backup.province, backup.facts);
      setStatus(`Opened the return saved ${backup.saved.slice(0, 10)}.`);
    } catch (e) {
      // `open` already says the useful thing for a wrong passphrase. A parse
      // failure means the file was not one of ours, which is worth
      // distinguishing rather than blaming the passphrase for.
      setStatus(
        e instanceof SyntaxError
          ? "That file is not a Freshet backup."
          : String(e).replace(/^Error:\s*/, ""),
      );
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return (
    <div className="card backup">
      <h2>Save a copy</h2>
      <p className="blurb">
        Encrypted in this browser, with a passphrase we never see. There is no
        way to recover it if you forget it.
      </p>

      <label className="field">
        <span className="label">Passphrase</span>
        <input
          type="password"
          autoComplete="new-password"
          value={passphrase}
          onChange={(e) => setPassphrase(e.target.value)}
        />
      </label>

      <div className="row buttons">
        <button onClick={save} disabled={busy}>
          Save to a file
        </button>
        <button
          className="secondary"
          onClick={() => fileInput.current?.click()}
          disabled={busy || passphrase.length === 0}
        >
          Open a file
        </button>
      </div>

      <input
        ref={fileInput}
        type="file"
        accept=".freshet,application/octet-stream"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void load(file);
        }}
      />

      {status && <p className="note">{status}</p>}
    </div>
  );
}
