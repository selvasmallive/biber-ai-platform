import { useState } from "react";

import type { Computed } from "../types";

interface Props {
  result: Computed;
  period: { start: string; end: string };
  province: string;
  facts: Record<string, string>;
}

interface Verdict {
  allowed: boolean;
  reason: string;
  /// The server recomputed and got a different answer. This should never
  /// happen, and if it does the return must not go anywhere.
  disagreement?: { line: string; browser: string; server: string }[];
}

/// Filing, and the honest account of who decides.
///
/// The browser computed this return, and the browser also has an opinion about
/// whether it may be filed. That opinion is worth showing — it is what stops a
/// user filling in a whole return before discovering it cannot be sent — but
/// it decides nothing. A page can be edited by whoever is looking at it, so
/// entitlement, certification and the filing count are settled server-side.
///
/// The server does not take the computed figures on trust either. It runs the
/// same engine over the same facts and compares. If the two disagree, the
/// disagreement is the story and the transmission does not happen.
export function Transmit({ result, period, province, facts }: Props) {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [asking, setAsking] = useState(false);
  const [key, setKey] = useState("");

  // Split, because these are different sentences to a user. An unverified
  // figure is something that may yet be fixed; a missing certification is not.
  // They were one field, so the certification message below was unreachable
  // and the button was enabled when the text said it should not be.
  const dataProblem = !result.data_sound;
  const notCertified = !result.certified_to_file;
  const blockedHere = dataProblem || notCertified;

  const ask = async () => {
    setAsking(true);
    setVerdict(null);
    try {
      const response = await fetch("/api/web/file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          period_start: period.start,
          period_end: period.end,
          province,
          facts,
          // Sent only at transmission, and only then. Nothing about the
          // licence gates the calculation: a person is entitled to work out
          // what they owe before deciding whether to buy anything.
          key: key.trim() || null,
          // What the browser computed, so the server can check its own work
          // against it rather than simply replacing it.
          computed: Object.fromEntries(
            result.lines.map((l) => [l.id, l.value]),
          ),
        }),
      });
      setVerdict(await response.json());
    } catch {
      setVerdict({
        allowed: false,
        reason:
          "Freshet could not reach the filing service. Your return is untouched — nothing was sent.",
      });
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="card transmit">
      <h2>Filing</h2>

      {result.warnings.length > 0 && (
        <div className="unverified">
          <p>
            <strong>This return cannot be filed yet.</strong> Some of the
            figures Freshet used have not been checked against a published CRA
            or provincial source:
          </p>
          <ul>
            {result.warnings.slice(0, 6).map((w) => (
              <li key={w}>{w}</li>
            ))}
            {result.warnings.length > 6 && (
              <li>and {result.warnings.length - 6} more</li>
            )}
          </ul>
          <p className="note">
            The arithmetic above is still correct for what was entered. It is
            the parameters behind it that are not yet confirmed, and filing a
            return built on an unconfirmed rate is worse than not filing.
          </p>
        </div>
      )}

      <label className="field">
        <span className="label">Licence key</span>
        <input
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder="XXXXX-XXXXX-XXXXX-XXXXX"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <span className="hint">
          Needed to file, not to calculate. The key is checked when the return
          is sent, and a return that fails to send does not use one up.
        </span>
      </label>

      <button onClick={ask} disabled={asking || blockedHere}>
        {asking ? "Checking…" : "File this return"}
      </button>

      {blockedHere && (
        <p className="note">
          {dataProblem
            ? "Disabled while a figure used here is unverified. The service would refuse it in any case."
            : "Disabled because Freshet is not yet certified by the CRA for this return. The service would refuse it in any case."}
        </p>
      )}

      {verdict && (
        <div className={verdict.allowed ? "verdict ok" : "verdict no"}>
          <p>{verdict.reason}</p>
          {verdict.disagreement && verdict.disagreement.length > 0 && (
            <>
              <p>
                <strong>
                  Freshet will not file this. The calculation in your browser
                  and the calculation on the server do not agree, and until we
                  know why, neither answer should be sent to the CRA.
                </strong>
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Here</th>
                    <th>Server</th>
                  </tr>
                </thead>
                <tbody>
                  {verdict.disagreement.map((d) => (
                    <tr key={d.line}>
                      <td>{d.line}</td>
                      <td>{d.browser}</td>
                      <td>{d.server}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}
