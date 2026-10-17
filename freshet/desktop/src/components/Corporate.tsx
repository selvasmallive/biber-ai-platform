import { useCallback, useEffect, useMemo, useState } from "react";

import {
  computeT2,
  errorText,
  loadReturn,
  money,
  saveT2,
  t2FilingGate,
  whenLocal,
} from "../api";
import type { FilingGate, ReturnSummary, T2Input, T2View } from "../types";
import { SECTIONS } from "../../../shared/t2-interview";
import {
  PRINT_STYLES,
  printDocument,
  ReturnDocumentView,
  type ReturnDocument,
} from "../../../shared/return-document";

/// The corporate return.
///
/// Shares its question list with the browser build — `shared/t2-interview.ts`
/// — rather than carrying a copy. The labels are presentation and could
/// reasonably differ between the two; the fact keys cannot, and a Rust test
/// checks that file against the form definitions in both directions. A second
/// copy here would sit outside that check, which is precisely how nine
/// missing fields went unnoticed the first time.

/// A fiscal year ending on the last day of last month: the common case, and
/// visibly wrong for anyone it does not fit, which beats a blank field a user
/// might leave blank.
function defaultPeriod(): { start: string; end: string } {
  const now = new Date();
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 0));
  const start = new Date(
    Date.UTC(end.getUTCFullYear() - 1, end.getUTCMonth(), end.getUTCDate() + 1),
  );
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { start: iso(start), end: iso(end) };
}

interface Props {
  provinces: string[];
  /// Every saved return, personal and corporate. Filtered here rather than by
  /// the caller so the two lists cannot disagree about which is which.
  saved: ReturnSummary[];
  onSaved: (summary: ReturnSummary) => void;
}

export default function Corporate({ provinces, saved, onSaved }: Props) {
  const [period, setPeriod] = useState(defaultPeriod);
  const [province, setProvince] = useState("on");
  const [facts, setFacts] = useState<Record<string, string>>({});
  const [result, setResult] = useState<T2View | null>(null);
  const [gate, setGate] = useState<FilingGate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string>(SECTIONS[0].id);
  const [label, setLabel] = useState("Untitled corporation");
  const [openId, setOpenId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Only corporate entries. A T2's facts are GIFI codes and a T1's are slip
  // boxes; loading one into the other would fill the screen with zeroes and
  // look like a working return.
  const corporate = saved.filter((r) => r.period !== null);

  const input: T2Input = useMemo(
    () => ({
      period_start: period.start,
      period_end: period.end,
      province,
      facts,
    }),
    [period, province, facts],
  );

  const set = useCallback((fact: string, value: string) => {
    setFacts((f) => ({ ...f, [fact]: value }));
  }, []);

  useEffect(() => {
    let cancelled = false;

    computeT2(input)
      .then((r) => {
        if (cancelled) return;
        setResult(r);
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        setResult(null);
        // An impossible fiscal period is the user's to fix, so it is shown
        // rather than logged. It is also the only error this screen produces
        // that is not about the return's contents.
        setError(errorText(e));
      });

    return () => {
      cancelled = true;
    };
  }, [input]);

  // The gate is asked separately and only when there is something to gate.
  // It reads the licence, so it is not worth calling on every keystroke of a
  // return that cannot be filed yet anyway.
  useEffect(() => {
    if (!result || result.has_errors) {
      setGate(null);
      return;
    }

    let cancelled = false;
    t2FilingGate(input)
      .then((g) => !cancelled && setGate(g))
      .catch(() => !cancelled && setGate(null));

    return () => {
      cancelled = true;
    };
  }, [input, result]);

  const store = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const summary = await saveT2({
        id: openId,
        label,
        province,
        period_start: period.start,
        period_end: period.end,
        facts,
      });
      setOpenId(summary.id);
      onSaved(summary);
    } catch (e) {
      setSaveError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const reopen = async (id: string) => {
    setSaveError(null);
    try {
      const stored = await loadReturn(id);
      if (!stored.period) {
        // Defensive: the list is already filtered, so reaching this means the
        // vault and the filter disagree, and filling the corporate screen with
        // personal facts would be worse than refusing.
        setSaveError("That saved return is a personal return, not a corporate one.");
        return;
      }
      setLabel(stored.label);
      setProvince(stored.province);
      setPeriod({ start: stored.period.start, end: stored.period.end });
      setFacts(stored.facts);
      setOpenId(stored.id);
    } catch (e) {
      setSaveError(errorText(e));
    }
  };

  // The paper is built from the same result and the same gate the screen is
  // showing. Nothing about the document is recomputed, so it cannot disagree
  // with what the user just reviewed.
  const document_: ReturnDocument | null = result && {
    kind: "T2",
    label,
    province,
    period: `${period.start} to ${period.end}`,
    lines: result.lines,
    diagnostics: result.diagnostics,
    warnings: [],
    canFile: gate?.can_file ?? false,
    blockedBy: gate?.blocked_by ?? [],
    preparedAt: new Date(),
  };

  return (
    <div className="corporate">
      <style>{PRINT_STYLES}</style>
      <section className="card">
        <h2>Fiscal period</h2>
        <p className="blurb">
          A corporation does not have a tax year in the way a person does — it
          has whatever period falls between one year end and the next.
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
              onChange={(e) => setPeriod((p) => ({ ...p, end: e.target.value }))}
            />
          </label>
          <label>
            Province
            <select
              value={province}
              onChange={(e) => setProvince(e.target.value)}
            >
              {provinces.map((p) => (
                <option key={p} value={p}>
                  {p.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>

        {result && (
          <p className="note">
            {result.period_days} days
            {result.is_short_year &&
              " — a short year, so the business limit and capital cost allowance are prorated"}
          </p>
        )}
      </section>

      {error && (
        <div className="card error" role="alert">
          <strong>That period will not work.</strong>
          <p>{error}</p>
        </div>
      )}

      {SECTIONS.map((section) => (
        <section key={section.id} className="card">
          <button
            type="button"
            className="disclosure"
            aria-expanded={open === section.id}
            onClick={() => setOpen(open === section.id ? "" : section.id)}
          >
            {section.title}
          </button>

          {open === section.id && (
            <>
              {section.blurb && <p className="blurb">{section.blurb}</p>}
              <div className="fields">
                {section.fields.map((f) =>
                  f.kind === "flag" ? (
                    <label key={f.fact} className="field flag">
                      <span className="label">
                        <input
                          type="checkbox"
                          checked={facts[f.fact] === "1"}
                          onChange={(e) =>
                            set(f.fact, e.target.checked ? "1" : "0")
                          }
                        />
                        {f.label}
                      </span>
                      {f.hint && <span className="hint">{f.hint}</span>}
                    </label>
                  ) : (
                    <label key={f.fact} className="field">
                      <span className="label">{f.label}</span>
                      <input
                        // Text, not number: a number input silently discards a
                        // pasted "$1,234.56" and swallows the scroll wheel over
                        // a focused field. The engine parses what was typed.
                        type="text"
                        inputMode="decimal"
                        autoComplete="off"
                        value={facts[f.fact] ?? ""}
                        placeholder="0.00"
                        onChange={(e) => set(f.fact, e.target.value)}
                      />
                      {f.hint && <span className="hint">{f.hint}</span>}
                    </label>
                  ),
                )}
              </div>
            </>
          )}
        </section>
      ))}

      <section className="card">
        <h2>Saving</h2>
        <div className="row">
          <label style={{ flex: 1 }}>
            Name
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </label>
          <button type="button" onClick={store} disabled={saving}>
            {saving ? "Saving…" : openId ? "Save" : "Save a copy"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={printDocument}
            disabled={!result}
          >
            Print
          </button>
        </div>

        <p className="note">
          Encrypted on this machine. A corporate return is a whole set of
          financial statements, so it is worth saving before you close the app.
        </p>

        {saveError && (
          <p className="note" role="alert" style={{ color: "var(--bad, #9b2c28)" }}>
            {saveError}
          </p>
        )}

        {corporate.length > 0 && (
          <>
            <h3>Saved corporate returns</h3>
            <ul className="saved-list">
              {corporate.map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => reopen(r.id)}>
                    {r.label}
                  </button>
                  <span className="note">
                    {r.period?.start} to {r.period?.end} · {whenLocal(r.updated_unix)}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {result && (
        <section className="card summary">
          <h2>Summary</h2>
          <dl>
            {(
              [
                ["Net income per the statements", result.accounting_income],
                ["Net income for tax purposes", result.net_income_for_tax],
                ["Taxable income", result.taxable_income],
                ["Small business deduction", result.small_business_deduction],
                ["Federal Part I tax", result.federal_tax],
                ["Provincial tax", result.provincial_tax],
                ["Total tax payable", result.total_tax],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="line">
                <dt>{label}</dt>
                <dd>{money(value)}</dd>
              </div>
            ))}
          </dl>

          <p className={Number(result.balance) > 0 ? "owing" : "refund"}>
            {Number(result.balance) > 0
              ? `The corporation owes ${money(result.balance)}.`
              : Number(result.balance) < 0
                ? `The corporation is owed ${money(String(-Number(result.balance)))}.`
                : "Nothing owing."}
          </p>

          {result.diagnostics.length > 0 && (
            <div className="diagnostics">
              <h3>Checks</h3>
              <ul>
                {result.diagnostics.map((d) => (
                  <li key={d.id} className={d.severity}>
                    <strong>{d.message}</strong>
                    {d.help && <span>{d.help}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {gate && !gate.can_file && (
            <div className="gate">
              <h3>Filing</h3>
              <p>
                This return cannot be filed yet
                {gate.blocked_by.length > 0 ? ":" : "."}
              </p>
              <ul>
                {gate.blocked_by.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <p className="note">
                The arithmetic above is still correct for what was entered.
              </p>
            </div>
          )}
        </section>
      )}

      {document_ && <ReturnDocumentView doc={document_} />}
    </div>
  );
}
