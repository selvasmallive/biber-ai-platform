import { useEffect, useState } from "react";

import { coupleOptimize, errorText, money } from "../api";
import type { ComputeInput, CoupleView, SpouseResultView } from "../types";

const PARTNER_FIELDS: { key: string; label: string; box?: string; hint?: string }[] = [
  { key: "taxpayer.age", label: "Their age on December 31" },
  { key: "t4.employment_income", label: "Employment income", box: "box 14" },
  { key: "t4.cpp_contributions", label: "CPP contributions", box: "box 16" },
  { key: "t4.cpp2_contributions", label: "Second CPP contributions", box: "box 16A" },
  { key: "t4.ei_premiums", label: "EI premiums", box: "box 18" },
  { key: "t4.income_tax_deducted", label: "Income tax deducted", box: "box 22" },
  {
    key: "pension.own_eligible",
    label: "Eligible pension income",
    box: "line 11500",
    hint: "What they could split with you.",
  },
  { key: "tuition.fees", label: "Tuition fees", box: "T2202" },
  {
    key: "disability.claimed",
    label: "Disability amount",
    hint: "Enter 1 if they are approved for the disability tax credit.",
  },
];

function SpouseCard({ r }: { r: SpouseResultView }) {
  const notes = [
    Number(r.spouse_amount) > 0 && `${money(r.spouse_amount)} spousal amount`,
    Number(r.age_amount) > 0 && `${money(r.age_amount)} age amount`,
    Number(r.pension_amount) > 0 && `${money(r.pension_amount)} pension amount`,
    Number(r.transferred_in) > 0 && `${money(r.transferred_in)} transferred in`,
  ].filter(Boolean) as string[];

  return (
    <div className="stat">
      <div className="k">{r.label}</div>
      <div className="v">{money(r.is_refund ? r.refund : `-${r.refund}`)}</div>
      <div className="import-detail" style={{ marginTop: 6 }}>
        Net income {money(r.net_income)} · tax {money(r.total_tax)}
        {notes.length > 0 && (
          <>
            <br />
            {notes.join(" · ")}
          </>
        )}
      </div>
    </div>
  );
}

interface Props {
  input: ComputeInput;
  yourLabel: string;
}

export default function Spouse({ input, yourLabel }: Props) {
  const [enabled, setEnabled] = useState(false);
  const [partnerLabel, setPartnerLabel] = useState("My partner");
  const [partnerFacts, setPartnerFacts] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CoupleView | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  // Household amounts and the children are entered once, in the interview. The
  // backend reads them off the primary return; asking again here would invite
  // two different answers.
  const medical = input.facts["medical.expenses_claimed"] ?? "";
  const donations = input.facts["donations.claimed"] ?? "";
  const childcare = input.facts["childcare.expenses_claimed"] ?? "";

  useEffect(() => {
    if (!enabled) {
      setResult(null);
      return;
    }

    const timer = setTimeout(() => {
      coupleOptimize(input, {
        your_label: yourLabel || "You",
        partner_label: partnerLabel || "Partner",
        partner_facts: partnerFacts,
      })
        .then((r) => {
          setResult(r);
          setFailure(null);
        })
        .catch((e) => setFailure(errorText(e)));
    }, 200);

    return () => clearTimeout(timer);
  }, [enabled, input, yourLabel, partnerLabel, partnerFacts]);

  const carryforward =
    result &&
    Number(result.you.tuition_carryforward) + Number(result.partner.tuition_carryforward);

  return (
    <div className="pane-body">
      <h2>Spouse or common-law partner</h2>
      <p className="hint">
        A couple files two returns, not one — but several amounts can go on
        either, and pension income can be moved between them. Freshet computes
        both returns under every combination and keeps the one with the lowest{" "}
        <em>combined</em> tax.
      </p>

      <label className="check-row">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        I had a spouse or common-law partner on December 31
      </label>

      {enabled && (
        <>
          <div className="field" style={{ marginTop: 18 }}>
            <label htmlFor="partnerLabel">Their name</label>
            <input
              id="partnerLabel"
              type="text"
              value={partnerLabel}
              onChange={(e) => setPartnerLabel(e.target.value)}
            />
          </div>

          <h2 style={{ marginTop: 20 }}>Their return</h2>
          <p className="hint">Leave blank what does not apply.</p>

          {PARTNER_FIELDS.map((f) => (
            <div className="field" key={f.key}>
              <label htmlFor={`p-${f.key}`}>
                {f.label}
                {f.box && <span className="box">{f.box}</span>}
              </label>
              <input
                id={`p-${f.key}`}
                type="text"
                inputMode="decimal"
                placeholder={f.key === "taxpayer.age" ? "e.g. 67" : "0.00"}
                value={partnerFacts[f.key] ?? ""}
                onChange={(e) =>
                  setPartnerFacts((p) => ({ ...p, [f.key]: e.target.value }))
                }
              />
              {f.hint && (
                <p className="hint" style={{ margin: "6px 0 0" }}>
                  {f.hint}
                </p>
              )}
            </div>
          ))}

          <div className="notice info" style={{ marginTop: 18 }}>
            <strong>Shared amounts come from the interview</strong>
            Medical {money(medical || "0")} · donations {money(donations || "0")}{" "}
            · child care {money(childcare || "0")}, plus the dependants you
            listed. Enter the family total once and Freshet works out whose
            return each belongs on.
          </div>

          {failure && (
            <div className="notice danger">
              <strong>Could not compute the couple</strong>
              {failure}
            </div>
          )}

          {result && (
            <>
              <h2 style={{ marginTop: 24 }}>Together</h2>

              <div
                className={`headline ${result.combined_is_refund ? "refund" : "owing"}`}
                style={{ marginBottom: 14 }}
              >
                <span className="caption">
                  {result.combined_is_refund
                    ? "Combined refund"
                    : "Combined balance owing"}
                </span>
                <span className="amount">
                  {money(
                    result.combined_is_refund
                      ? result.combined_refund
                      : `-${result.combined_refund}`,
                  )}
                </span>
              </div>

              <div className="stat-grid">
                <SpouseCard r={result.you} />
                <SpouseCard r={result.partner} />
              </div>

              {Number(result.pension_split_amount) > 0 && (
                <div className="notice info">
                  <strong>
                    Split {result.pension_split_rate}% of{" "}
                    {result.pension_split_from}'s pension —{" "}
                    {money(result.pension_split_amount)}
                  </strong>
                  You both sign form T1032 and each report this figure: the
                  sender deducts it at line 21000, the receiver reports it at
                  line 11600.
                </div>
              )}

              {result.decisions.length > 0 ? (
                <>
                  <h2 style={{ marginTop: 20 }}>What we decided, and why</h2>
                  <p className="hint">
                    {result.allocations_considered} combinations were computed in
                    full. Choosing well saved {money(result.saving_vs_worst)}{" "}
                    against the worst of them.
                  </p>

                  {result.decisions.map((d) => (
                    <div className="notice info" key={d.item}>
                      <strong>
                        {d.item} → {d.chose}
                        {d.mandatory
                          ? " (required)"
                          : Number(d.saved) > 0 && ` (saves ${money(d.saved)})`}
                      </strong>
                      {d.why}
                    </div>
                  ))}
                </>
              ) : (
                <p className="hint" style={{ marginTop: 16 }}>
                  Nothing to allocate yet. Add medical expenses, donations or
                  pension income and Freshet will work out where they belong.
                </p>
              )}

              {carryforward !== null && carryforward > 0 && (
                <div className="notice warn" style={{ marginTop: 18 }}>
                  <strong>
                    {money(String(carryforward))} of tuition carries forward
                  </strong>
                  Neither return could use it and it is over the transfer cap.
                  Write it down — Freshet does not yet carry amounts between tax
                  years, so next year's return will need it entered by hand.
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
