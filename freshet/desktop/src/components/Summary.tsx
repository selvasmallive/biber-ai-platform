import { useEffect, useState } from "react";

import { ccaPlan, filingGate, licenceStatus, money, rrspPlan } from "../api";
import type {
  CcaPlan,
  ComputeInput,
  FilingGate,
  LicenceView,
  ReturnView,
  RrspPlan,
} from "../types";

interface Props {
  result: ReturnView | null;
  input: ComputeInput;
}

function RrspPlanner({ input }: { input: ComputeInput }) {
  const [plan, setPlan] = useState<RrspPlan | null>(null);

  useEffect(() => {
    rrspPlan(input, null)
      .then(setPlan)
      .catch(() => setPlan(null));
  }, [input]);

  if (!plan || plan.points.length === 0) return null;

  // Every fourth step keeps the table readable without losing the shape.
  const shown = plan.points.filter((_, i) => (i + 1) % 4 === 0);

  return (
    <section style={{ marginTop: 26 }}>
      <h2>If you contribute more to an RRSP</h2>
      <p className="hint">
        Measured by re-running your whole return at each level, so bracket edges
        and the Ontario surtax are included rather than assumed away. Room shown
        is estimated from this year's income until you import it from CRA.
      </p>

      {plan.sweet_spot && plan.sweet_spot_saving && (
        <div className="notice info">
          <strong>
            {money(plan.sweet_spot)} would save you {money(plan.sweet_spot_saving)}
          </strong>
          That is the last dollar earning your top rate. Contributing beyond it
          still helps, but each further dollar is worth less.
        </div>
      )}

      {plan.to_break_even && (
        <div className="notice info">
          <strong>{money(plan.to_break_even)} would clear your balance owing</strong>
          Check this against your real deduction limit before contributing.
        </div>
      )}

      <table className="lines">
        <thead>
          <tr>
            <th>Contribution</th>
            <th style={{ textAlign: "right" }}>Tax saved</th>
            <th style={{ textAlign: "right" }}>Per dollar</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((p) => (
            <tr key={p.contribution}>
              <td className="amt" style={{ textAlign: "left" }}>
                {money(p.contribution)}
              </td>
              <td className="amt">{money(p.tax_saved)}</td>
              <td className="amt">{p.saving_rate}¢</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function CcaPlanner({ input }: { input: ComputeInput }) {
  const [plan, setPlan] = useState<CcaPlan | null>(null);

  useEffect(() => {
    ccaPlan(input)
      .then(setPlan)
      .catch(() => setPlan(null));
  }, [input]);

  if (!plan || plan.points.length === 0) return null;

  const banked = Number(plan.banked_at_best) > 0;

  return (
    <section style={{ marginTop: 26 }}>
      <h2>How much depreciation to claim</h2>
      <p className="hint">
        Capital cost allowance is optional. Claiming less leaves the balance in
        the pool for a later year — worth doing when this year's income is
        already covered by your personal amounts. Each level below was computed
        by running the whole return.
      </p>

      <div className="notice info">
        <strong>
          Claiming {money(plan.best_claim)} of {money(plan.maximum)} gives the
          best result this year — {money(plan.best_refund)}
        </strong>
        {banked
          ? `That leaves ${money(plan.banked_at_best)} in the pool for a future year, when your income may be taxed at a higher rate.`
          : "Claiming the full amount is best this year."}
      </div>

      {plan.tax_zero_at !== null && (
        <div className="notice warn">
          <strong>Tax already reaches zero at {money(plan.tax_zero_at)}</strong>
          Beyond that, more depreciation buys no further tax saving this year. It
          can still raise income-tested credits, so it is not automatically
          wasted — but it is the point worth thinking about before claiming more.
        </div>
      )}

      <table className="lines">
        <thead>
          <tr>
            <th>Claim</th>
            <th style={{ textAlign: "right" }}>Tax</th>
            <th style={{ textAlign: "right" }}>Refundable credits</th>
            <th style={{ textAlign: "right" }}>Result</th>
          </tr>
        </thead>
        <tbody>
          {plan.points
            .filter((_, i) => i % 4 === 0 || i === plan.points.length - 1)
            .map((p) => (
              <tr key={p.claim}>
                <td className="amt" style={{ textAlign: "left" }}>
                  {money(p.claim)}
                </td>
                <td className="amt">{money(p.total_tax)}</td>
                <td className="amt">{money(p.refundable_credits)}</td>
                <td className="amt">{money(p.refund)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </section>
  );
}

/**
 * Four independent locks stand between a computed return and a filed one. They
 * are shown separately and always, because "cannot file" without a reason is
 * the single most infuriating thing tax software does.
 */
function FilingStatus({ input, result }: { input: ComputeInput; result: ReturnView }) {
  const [gate, setGate] = useState<FilingGate | null>(null);
  const [licence, setLicence] = useState<LicenceView | null>(null);

  useEffect(() => {
    filingGate(input)
      .then(setGate)
      .catch(() => setGate(null));

    licenceStatus(input.tax_year)
      .then(setLicence)
      .catch(() => setLicence(null));
  }, [input]);

  if (!gate) return null;

  const locks: [boolean, string, string][] = [
    [
      gate.data_verified,
      "Tax data verified",
      "Every parameter behind this return has been checked against a CRA publication.",
    ],
    [
      gate.return_sound,
      "Return is sound",
      "No blocking errors in the review.",
    ],
    [
      gate.year_certified,
      gate.in_scope
        ? `CRA certified for ${input.tax_year}`
        : `CRA certified for ${input.province.toUpperCase()}`,
      gate.in_scope
        ? "Nothing is certified yet. CRA issues the confirmation letter after " +
          "the certification tests pass, and no return can be filed before then."
        : "Freshet is seeking certification for Ontario only. Returns for " +
          "other provinces can be prepared, checked and printed, but will not " +
          "be filed from this release.",
    ],
    [
      gate.licensed,
      "Licensed to file",
      "Preparing is free. Filing needs a licence key — enter it under Settings.",
    ],
  ];

  return (
    <section style={{ marginBottom: 20 }}>
      {/* Only when something has actually changed for the user. A licence with
          months left says nothing here — the date lives in Settings, and
          repeating it on the screen people look at every day is how warnings
          get tuned out. */}
      {!gate.in_scope && (
        <div className="notice warn">
          <strong>
            {input.province.toUpperCase()} returns cannot be filed from this
            release
          </strong>
          Freshet is seeking CRA certification for Ontario first. Everything
          here still works — you can prepare, check and print a{" "}
          {input.province.toUpperCase()} return — but it cannot be transmitted,
          and its tax data has not been verified yet.
        </div>
      )}

      {licence?.standing_urgent && licence.standing_note && (
        <div className="notice warn">
          <strong>About your licence</strong>
          {licence.standing_note}
        </div>
      )}

      <div className={`notice ${gate.can_file ? "info" : "warn"}`}>
        <strong>
          {gate.can_file
            ? "This return is ready to file"
            : "This return cannot be filed yet"}
        </strong>
        {gate.can_file
          ? "All four checks pass."
          : "Each check below is independent — all four must pass."}
        <ul>
          {locks.map(([ok, label, why]) => (
            <li key={label}>
              {ok ? "✓" : "✗"} {label}
              {!ok && <div style={{ color: "var(--muted)", fontSize: 12 }}>{why}</div>}
            </li>
          ))}
        </ul>
      </div>

      {result.warnings.length > 0 && (
        <details>
          <summary className="hint" style={{ cursor: "pointer" }}>
            {result.warnings.length} unverified parameter
            {result.warnings.length === 1 ? "" : "s"}
          </summary>
          <ul className="hint">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

export default function Summary({ result, input }: Props) {
  if (!result) {
    return (
      <div className="pane-body">
        <p className="hint">Computing…</p>
      </div>
    );
  }

  const s = result.summary;

  const counts = {
    error: result.diagnostics.filter((d) => d.severity === "error").length,
    warning: result.diagnostics.filter((d) => d.severity === "warning").length,
  };

  return (
    <div className="pane-body">
      {result.diagnostics.length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h2>Review</h2>
          <p className="hint">
            {counts.error > 0
              ? `${counts.error} thing${counts.error === 1 ? "" : "s"} must be fixed before this return can be filed.`
              : counts.warning > 0
                ? "Nothing blocking. These are worth a second look."
                : "Nothing blocking."}
          </p>

          {result.diagnostics.map((d) => (
            <div
              key={d.id}
              className={`notice ${d.severity === "error" ? "danger" : d.severity === "warning" ? "warn" : "info"}`}
            >
              <strong>{d.message}</strong>
              {d.help}
            </div>
          ))}
        </section>
      )}

      <FilingStatus input={input} result={result} />

      <div className="stat-grid">
        <div className="stat">
          <div className="k">Total income</div>
          <div className="v">{money(s.total_income)}</div>
        </div>
        <div className="stat">
          <div className="k">Taxable income</div>
          <div className="v">{money(s.taxable_income)}</div>
        </div>
        <div className="stat">
          <div className="k">Federal tax</div>
          <div className="v">{money(s.federal_tax)}</div>
        </div>
        <div className="stat">
          <div className="k">{result.province.toUpperCase()} tax</div>
          <div className="v">{money(s.provincial_tax)}</div>
        </div>
        {Number(s.refundable_credits) > 0 && (
          <div className="stat">
            <div className="k">Refundable credits</div>
            <div className="v">{money(s.refundable_credits)}</div>
          </div>
        )}
        <div className="stat">
          <div className="k">Average rate</div>
          <div className="v">{s.average_rate}%</div>
        </div>
        <div className="stat">
          <div className="k">Marginal rate</div>
          <div className="v">{s.marginal_rate}%</div>
        </div>
      </div>

      <p className="hint">
        Your marginal rate is what the next dollar costs — measured by actually
        re-running the return with $1,000 more income, so surtaxes and
        phase-outs are included rather than assumed away.
      </p>

      <RrspPlanner input={input} />
      <CcaPlanner input={input} />

      <h2 style={{ marginTop: 26 }}>Every line</h2>
      <p className="hint">
        In the order the engine resolved them, which is also the order that
        explains them.
      </p>

      <table className="lines">
        <thead>
          <tr>
            <th>Line</th>
            <th>Description</th>
            <th style={{ textAlign: "right" }}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {result.lines.map((l) => (
            <tr key={l.id}>
              <td className="id">{l.id}</td>
              <td>
                {l.label}
                {l.note && (
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 2 }}>
                    {l.note}
                  </div>
                )}
              </td>
              <td className="amt">{money(l.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
