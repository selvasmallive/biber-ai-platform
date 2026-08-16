import { useState } from "react";

import { money } from "../api";
import Dependants from "./Dependants";

interface Field {
  key: string;
  label: string;
  box?: string;
  hint?: string;
}

interface Step {
  title: string;
  heading: string;
  blurb: string;
  fields: Field[];
  /// Steps that need more than a list of money fields.
  custom?: "dependants";
}

/** Steps are data so that adding the rest of T1 is an edit here, not a refactor. */
const STEPS: Step[] = [
  {
    title: "About you",
    heading: "About you",
    blurb:
      "Your province is the one you lived in on December 31 of the tax year, which is not always where you worked.",
    fields: [],
  },
  {
    title: "Employment",
    heading: "Employment income",
    blurb:
      "Copy these straight off your T4. If you have more than one T4, add the boxes together for now.",
    fields: [
      { key: "t4.employment_income", label: "Employment income", box: "box 14" },
      { key: "t4.cpp_contributions", label: "CPP contributions", box: "box 16" },
      {
        key: "t4.cpp2_contributions",
        label: "Second CPP contributions",
        box: "box 16A",
        hint: "Only applies above the first earnings ceiling. Leave blank if the box is empty.",
      },
      { key: "t4.ei_premiums", label: "EI premiums", box: "box 18" },
      {
        key: "t4.income_tax_deducted",
        label: "Income tax deducted",
        box: "box 22",
        hint: "What your employer already sent to CRA on your behalf.",
      },
    ],
  },
  {
    title: "Other income",
    heading: "Other income",
    blurb: "Pension and investment income.",
    fields: [
      {
        key: "pension.own_eligible",
        label: "Eligible pension income",
        box: "line 11500",
        hint: "Registered pension plan payments at any age; RRIF and annuity income once you are 65. This is what can be split with a spouse.",
      },
      { key: "investment.interest", label: "Interest and investment income", box: "T5 box 13" },
    ],
  },
  {
    title: "Self-employment",
    heading: "Self-employment",
    blurb:
      "Business or professional income, from form T2125. Being self-employed means paying both halves of CPP — Freshet deducts one half and credits the other, which is what keeps you level with an employee.",
    fields: [
      { key: "self_employment.gross", label: "Gross business income", box: "line 13499" },
      {
        key: "self_employment.expenses",
        label: "Business expenses",
        hint: "Everything except depreciation on assets and the home office — those are on the next two steps. A loss is fine and reduces your other income.",
      },

      { key: "professional.gross", label: "Gross professional income", box: "line 13699" },
      { key: "professional.expenses", label: "Professional expenses" },

      { key: "farming.gross", label: "Gross farming income", box: "line 14099" },
      {
        key: "farming.expenses",
        label: "Farming expenses",
        hint: "The optional inventory adjustment and the cash method are not modelled.",
      },

      { key: "fishing.gross", label: "Gross fishing income", box: "line 14299" },
      { key: "fishing.expenses", label: "Fishing expenses" },
    ],
  },
  {
    title: "Assets",
    heading: "Depreciable assets",
    blurb:
      "Capital cost allowance is the tax word for depreciation. Each class has its own rate, and only half of anything bought this year enters the calculation — the half-year rule. Selling can produce recapture (income) or a terminal loss (a deduction), and Freshet works out which.",
    fields: [
      {
        key: "cca.class8.opening_ucc",
        label: "Class 8 opening balance",
        box: "20%",
        hint: "Furniture, fixtures and general equipment. The undepreciated balance carried forward from last year's return.",
      },
      { key: "cca.class8.additions", label: "Class 8 bought this year" },
      { key: "cca.class8.dispositions", label: "Class 8 sold this year" },
      {
        key: "cca.class8.all_disposed",
        label: "Class 8 is now empty",
        hint: "Enter 1 only if you sold the last asset in this class — that is what turns a leftover balance into a terminal loss.",
      },

      {
        key: "cca.class10.opening_ucc",
        label: "Class 10 opening balance",
        box: "30%",
        hint: "Most motor vehicles. A passenger vehicle costing more than the prescribed limit belongs in class 10.1 below instead.",
      },
      { key: "cca.class10.additions", label: "Class 10 bought this year" },
      { key: "cca.class10.dispositions", label: "Class 10 sold this year" },
      { key: "cca.class10.all_disposed", label: "Class 10 is now empty" },

      {
        key: "cca.class50.opening_ucc",
        label: "Class 50 opening balance",
        box: "55%",
        hint: "Computer hardware and systems software.",
      },
      { key: "cca.class50.additions", label: "Class 50 bought this year" },
      { key: "cca.class50.dispositions", label: "Class 50 sold this year" },
      { key: "cca.class50.all_disposed", label: "Class 50 is now empty" },

      {
        key: "cca.class12.opening_ucc",
        label: "Class 12 opening balance",
        box: "100%",
        hint: "Tools under the cost threshold, and software other than systems software.",
      },
      { key: "cca.class12.additions", label: "Class 12 bought this year" },
      { key: "cca.class12.dispositions", label: "Class 12 sold this year" },
      { key: "cca.class12.all_disposed", label: "Class 12 is now empty" },

      {
        key: "cca.class10_1.opening_ucc",
        label: "Class 10.1 opening balance",
        box: "30%",
        hint: "A passenger vehicle costing more than the prescribed limit. Its own pool, and uniquely it never produces recapture or a terminal loss however it is sold — so there is no 'now empty' box.",
      },
      {
        key: "cca.class10_1.additions",
        label: "Class 10.1 bought this year",
        hint: "Enter the full price. Freshet caps it at the prescribed limit; anything above that is simply not depreciable.",
      },
      { key: "cca.class10_1.dispositions", label: "Class 10.1 sold this year" },

      {
        key: "cca.limit_claim",
        label: "Claim less than the maximum",
        hint: "Enter 1 to choose your own amount. Capital cost allowance is optional — leaving some unclaimed keeps it in the pool for a later year, which is often better when this year's income is already covered by your personal amounts. The planner on the return summary shows the trade-off.",
      },
      { key: "cca.claimed", label: "Amount to claim" },
    ],
  },
  {
    title: "Home office",
    heading: "Business use of your home",
    blurb:
      "The business share of your household costs. It cannot create or deepen a business loss — anything over that limit carries forward to a future year instead of being lost.",
    fields: [
      {
        key: "home_office.expenses",
        label: "Household expenses for the year",
        hint: "Heat, electricity, insurance, maintenance, and either rent or mortgage interest and property tax.",
      },
      {
        key: "home_office.area_business",
        label: "Area used for business",
        box: "sq ft or m²",
      },
      {
        key: "home_office.area_total",
        label: "Total area of the home",
        box: "same units",
        hint: "The two areas set the share; only the ratio matters, so use whichever unit you measured in.",
      },
    ],
  },
  {
    title: "Deductions",
    heading: "Deductions",
    blurb:
      "Contributions made during the year or in the first 60 days after year end. You do not have to claim all of it this year, but this build assumes you do.",
    fields: [
      { key: "rrsp.deduction_claimed", label: "RRSP deduction claimed", box: "line 20800" },
    ],
  },
  {
    title: "Dependants",
    heading: "Dependants",
    blurb: "Children and others you support.",
    fields: [],
    custom: "dependants",
  },
  {
    title: "Credits",
    heading: "Credits and expenses",
    blurb:
      "Amounts that reduce the tax rather than the income. With a spouse, Freshet decides whose return each one belongs on.",
    fields: [
      {
        key: "medical.expenses_claimed",
        label: "Medical expenses",
        box: "line 33099",
        hint: "The family total. Only the part above 3% of net income counts, which is why it matters whose return it lands on.",
      },
      { key: "donations.claimed", label: "Charitable donations", box: "line 34900" },
      {
        key: "childcare.expenses_claimed",
        label: "Child care expenses",
        box: "line 21400",
        hint: "A deduction, not a credit. With a partner it must be claimed by whichever of you has the lower income — Freshet handles that, and will tell you when the two-thirds-of-income cap has trimmed the claim.",
      },
      {
        key: "tuition.fees",
        label: "Tuition fees",
        box: "T2202",
        hint: "Up to $5,000 of what you cannot use yourself can transfer to a spouse or parent; the rest carries forward.",
      },
      {
        key: "disability.claimed",
        label: "Disability amount",
        hint: "Enter 1 if you are approved for the disability tax credit, otherwise leave blank.",
      },
    ],
  },
  {
    title: "Review",
    heading: "Review",
    blurb: "Everything you have entered so far.",
    fields: [],
  },
];

const PROVINCES: Record<string, string> = {
  on: "Ontario",
  bc: "British Columbia",
  ab: "Alberta",
  qc: "Quebec",
};

interface Props {
  year: number;
  province: string;
  facts: Record<string, string>;
  options: { years: number[]; provinces: string[] };
  onYear: (year: number) => void;
  onProvince: (province: string) => void;
  onFact: (key: string, value: string) => void;
  onFacts: (patch: Record<string, string>) => void;
}

export default function Interview({
  year,
  province,
  facts,
  options,
  onYear,
  onProvince,
  onFact,
  onFacts,
}: Props) {
  const [at, setAt] = useState(0);
  const step = STEPS[at];

  const entered = STEPS.flatMap((s) => s.fields).filter(
    (f) => (facts[f.key] ?? "").trim() !== "",
  );

  return (
    <>
      <nav className="steps">
        {STEPS.map((s, i) => (
          <button
            key={s.title}
            className={`step ${i === at ? "active" : ""} ${i < at ? "done" : ""}`}
            onClick={() => setAt(i)}
          >
            {s.title}
          </button>
        ))}
      </nav>

      <div className="pane-body">
        <h2>{step.heading}</h2>
        <p className="hint">{step.blurb}</p>

        {at === 0 && (
          <div className="row">
            <div className="field">
              <label htmlFor="year">Tax year</label>
              <select
                id="year"
                value={year}
                onChange={(e) => onYear(Number(e.target.value))}
              >
                {options.years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="province">Province on December 31</label>
              <select
                id="province"
                value={province}
                onChange={(e) => onProvince(e.target.value)}
              >
                {options.provinces.map((p) => (
                  <option key={p} value={p}>
                    {PROVINCES[p] ?? p.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {at === 0 && (
          <div className="field">
            <label htmlFor="age">
              Your age on December 31
              <span className="box">unlocks the age amount at 65</span>
            </label>
            <input
              id="age"
              type="text"
              inputMode="numeric"
              placeholder="e.g. 42"
              value={facts["taxpayer.age"] ?? ""}
              onChange={(e) => onFact("taxpayer.age", e.target.value)}
            />
          </div>
        )}

        {step.custom === "dependants" && (
          <Dependants facts={facts} onFacts={onFacts} onFact={onFact} />
        )}

        {step.fields.map((f) => (
          <div className="field" key={f.key}>
            <label htmlFor={f.key}>
              {f.label}
              {f.box && <span className="box">{f.box}</span>}
            </label>
            <input
              id={f.key}
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={facts[f.key] ?? ""}
              onChange={(e) => onFact(f.key, e.target.value)}
            />
            {f.hint && <p className="hint" style={{ margin: "6px 0 0" }}>{f.hint}</p>}
          </div>
        ))}

        {at === STEPS.length - 1 && (
          <>
            {entered.length === 0 ? (
              <p className="hint">Nothing entered yet.</p>
            ) : (
              <table className="lines">
                <tbody>
                  {entered.map((f) => (
                    <tr key={f.key}>
                      <td>{f.label}</td>
                      <td className="amt">{money(facts[f.key])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div className="notice warn" style={{ marginTop: 20 }}>
              <strong>Not ready to file</strong>
              Freshet is not yet certified by CRA, and the {year} tax data in this
              build has not been verified against its sources. Use it to model
              and to plan, not to file.
            </div>
          </>
        )}
      </div>

      <div className="nav">
        <button
          className="ghost"
          disabled={at === 0}
          onClick={() => setAt((i) => Math.max(0, i - 1))}
        >
          Back
        </button>
        <div className="spacer" />
        <button
          className="primary"
          disabled={at === STEPS.length - 1}
          onClick={() => setAt((i) => Math.min(STEPS.length - 1, i + 1))}
        >
          Next
        </button>
      </div>
    </>
  );
}
