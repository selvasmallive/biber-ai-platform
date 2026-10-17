import { useCallback, useEffect, useMemo, useState } from "react";

import { capabilities, computeT2 } from "./engine";
import type { Capabilities, Computed } from "./types";
import { SECTIONS } from "../../shared/t2-interview";
import { Interview } from "./components/Interview";
import { Summary } from "./components/Summary";
import { Transmit } from "./components/Transmit";
import { Backup } from "./components/Backup";
import {
  PRINT_STYLES,
  printDocument,
  ReturnDocumentView,
  type ReturnDocument,
} from "../../shared/return-document";

/// A fiscal year ending on the last day of last month is the common case and a
/// harmless default: it is visibly wrong for anyone it does not fit, which is
/// better than a blank field that a user might leave blank.
function defaultPeriod(): { start: string; end: string } {
  const now = new Date();
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 0));
  const start = new Date(
    Date.UTC(end.getUTCFullYear() - 1, end.getUTCMonth(), end.getUTCDate() + 1),
  );
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { start: iso(start), end: iso(end) };
}

export default function App() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [period, setPeriod] = useState(defaultPeriod);
  const [province, setProvince] = useState("on");
  const [facts, setFacts] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Computed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    capabilities()
      .then((c) => {
        setCaps(c);
        setReady(true);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const set = useCallback((fact: string, value: string) => {
    setFacts((f) => ({ ...f, [fact]: value }));
  }, []);

  // Recompute on every keystroke. It costs microseconds and it happens in the
  // page, so there is no round trip to debounce and no reason to make the user
  // press a button to see what they just changed.
  useEffect(() => {
    if (!ready) return;

    let cancelled = false;
    computeT2(period, province, facts)
      .then((r) => {
        if (!cancelled) {
          setResult(r);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setResult(null);
          setError(String(e).replace(/^Error:\s*/, ""));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [ready, period, province, facts]);

  const days = useMemo(() => {
    const a = Date.parse(period.start);
    const b = Date.parse(period.end);
    if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
    return Math.round((b - a) / 86_400_000) + 1;
  }, [period]);

  // The browser has no filing gate of its own — that lives on the server and
  // is only consulted at transmission. So the paper states what the page
  // actually knows: whether the data is sound, and that nothing is certified.
  // Claiming more would put a document on someone's desk that implies a
  // standing the product does not have.
  const printable: ReturnDocument | null = result && {
    kind: "T2",
    label: "Corporate return",
    province,
    period: `${period.start} to ${period.end}`,
    lines: result.lines,
    diagnostics: result.diagnostics,
    warnings: result.warnings,
    canFile: false,
    blockedBy: [
      ...(result.warnings.length > 0
        ? [
            `${result.warnings.length} figure(s) used here have not been checked against a published source.`,
          ]
        : []),
      ...(result && !result.certified_to_file
        ? [
            "Freshet is not yet certified by the CRA to transmit corporate returns.",
          ]
        : []),
    ],
    preparedAt: new Date(),
  };

  return (
    <div className="app">
      <style>{PRINT_STYLES}</style>
      <header>
        <h1>Freshet <span>T2</span></h1>
        <p className="posture">
          This return is being calculated in your browser. Nothing you type here
          is sent anywhere until you choose to file or save it.
        </p>
      </header>

      <main>
        <section className="card period">
          <h2>Fiscal period</h2>
          <p className="blurb">
            A corporation does not have a tax year in the way a person does — it
            has whatever period falls between one year end and the next. If it
            crosses a calendar boundary, rates are apportioned by day.
          </p>
          <div className="row">
            <label>
              First day
              <input
                type="date"
                value={period.start}
                onChange={(e) =>
                  setPeriod((p) => ({ ...p, start: e.target.value }))
                }
              />
            </label>
            <label>
              Last day
              <input
                type="date"
                value={period.end}
                onChange={(e) =>
                  setPeriod((p) => ({ ...p, end: e.target.value }))
                }
              />
            </label>
            <label>
              Province
              <select
                value={province}
                onChange={(e) => setProvince(e.target.value)}
              >
                {(caps?.t2_provinces ?? ["on"]).map((p) => (
                  <option key={p} value={p}>
                    {p.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {days !== null && (
            <p className="note">
              {days} days{days < 365 ? " — a short year, so the business limit and capital cost allowance are prorated" : ""}
            </p>
          )}
        </section>

        {error && (
          <div className="card error" role="alert">
            <strong>That period will not work.</strong>
            <p>{error}</p>
          </div>
        )}

        {SECTIONS.map((s) => (
          <Interview key={s.id} section={s} facts={facts} onChange={set} />
        ))}
      </main>

      <aside>
        {result && <Summary result={result} />}
        <Backup
          period={period}
          province={province}
          facts={facts}
          onRestore={(p, prov, f) => {
            setPeriod(p);
            setProvince(prov);
            setFacts(f);
          }}
        />
        {result && (
          <div className="card">
            <h2>On paper</h2>
            <p className="blurb">
              A working copy for review. It is not a CRA form, and it says so.
            </p>
            <button onClick={printDocument}>Print this return</button>
          </div>
        )}
        {result && (
          <Transmit
            result={result}
            period={period}
            province={province}
            facts={facts}
          />
        )}
      </aside>

      {printable && <ReturnDocumentView doc={printable} />}
    </div>
  );
}
