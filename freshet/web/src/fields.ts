//! What the T2 interview asks for.
//!
//! Declared rather than laid out by hand, because the list is long and mostly
//! uniform, and because the fact keys have to match the form definitions
//! exactly — a typo here is a figure silently read as zero. `engine.test.ts`
//! checks every key below against the engine's own list for that reason.

export interface Field {
  fact: string;
  label: string;
  hint?: string;
  /// A yes/no, not an amount.
  ///
  /// The engine has no boolean: a flag is a fact that is one or zero, tested
  /// with `gte 1`. That is fine in the form language and a trap in an
  /// interview — a text box labelled like an amount, wired to a flag, turns
  /// "claim 50,000" into "claim something" and then claims nothing. So the
  /// kind is declared here and rendered as a checkbox.
  kind?: "flag";
}

export interface Section {
  id: string;
  title: string;
  blurb?: string;
  fields: Field[];
}

/// GIFI codes are the CRA's, not ours. Showing the code next to the label is
/// deliberate: an accountant transcribing from a trial balance is looking for
/// the number, and hiding it to look tidy makes the form slower to fill.
export const SECTIONS: Section[] = [
  {
    id: "income",
    title: "Income statement",
    blurb:
      "From the financial statements, before any tax adjustment. The return starts here rather than at taxable income, because that is the order the work actually happens in.",
    fields: [
      { fact: "gifi.8000", label: "Trade sales of goods and services (8000)" },
      { fact: "gifi.8090", label: "Investment revenue (8090)" },
      { fact: "gifi.8300", label: "Cost of sales (8300)" },
      { fact: "gifi.9060", label: "Salaries and wages (9060)" },
      { fact: "gifi.8520", label: "Advertising and promotion (8520)" },
      {
        fact: "gifi.8523",
        label: "Meals and entertainment (8523)",
        hint: "Half of this is added back on Schedule 1 automatically.",
      },
      {
        fact: "gifi.8670",
        label: "Amortization of tangible assets (8670)",
        hint: "Added back in full, and replaced by capital cost allowance.",
      },
      { fact: "gifi.8690", label: "Insurance (8690)" },
      { fact: "gifi.8710", label: "Interest and bank charges (8710)" },
      { fact: "gifi.8760", label: "Business taxes, licences and memberships (8760)" },
      { fact: "gifi.8860", label: "Professional fees (8860)" },
      { fact: "gifi.9270", label: "Other expenses (9270)" },
      {
        fact: "gifi.9990",
        label: "Current and deferred income taxes (9990)",
        hint: "Added back: income tax is not deductible in computing income.",
      },
    ],
  },
  {
    id: "balance",
    title: "Balance sheet",
    blurb:
      "Assets, liabilities and equity at the year end. Freshet checks that it balances and says so if it does not.",
    fields: [
      { fact: "gifi.1000", label: "Cash and deposits (1000)" },
      { fact: "gifi.1060", label: "Accounts receivable (1060)" },
      { fact: "gifi.1120", label: "Inventories (1120)" },
      { fact: "gifi.1600", label: "Capital assets at cost (1600)" },
      {
        fact: "gifi.1740",
        label: "Accumulated amortization (1740)",
        hint: "Enter as a positive number; it is subtracted for you.",
      },
      { fact: "gifi.2600", label: "Accounts payable and accrued liabilities (2600)" },
      { fact: "gifi.2700", label: "Loans and other long-term debt (2700)" },
      { fact: "gifi.3500", label: "Common shares (3500)" },
      { fact: "gifi.3600", label: "Retained earnings (3600)" },
    ],
  },
  {
    id: "cca",
    title: "Capital cost allowance",
    blurb:
      "Opening undepreciated capital cost, additions and dispositions by class. The half-year rule and the accelerated investment incentive are applied for you.",
    fields: [
      { fact: "cca.class8.opening_ucc", label: "Class 8 — opening UCC (20%)" },
      { fact: "cca.class8.additions", label: "Class 8 — additions" },
      { fact: "cca.class8.dispositions", label: "Class 8 — dispositions" },
      {
        fact: "cca.class8.all_disposed",
        label: "Class 8 — every asset in the class was disposed of",
        kind: "flag",
        hint: "A terminal loss is only available once the class is empty.",
      },
      { fact: "cca.class10.opening_ucc", label: "Class 10 — opening UCC (30%)" },
      { fact: "cca.class10.additions", label: "Class 10 — additions" },
      { fact: "cca.class10.dispositions", label: "Class 10 — dispositions" },
      {
        fact: "cca.class10.all_disposed",
        label: "Class 10 — every asset in the class was disposed of",
        kind: "flag",
      },
      {
        fact: "cca.class10_1.opening_ucc",
        label: "Class 10.1 — opening UCC (30%)",
        hint: "Passenger vehicles above the prescribed ceiling, one class each.",
      },
      { fact: "cca.class10_1.additions", label: "Class 10.1 — additions" },
      {
        fact: "cca.class10_1.dispositions",
        label: "Class 10.1 — dispositions",
        hint: "No terminal loss and no recapture arises on class 10.1, which is why there is no question about emptying it.",
      },
      { fact: "cca.class12.opening_ucc", label: "Class 12 — opening UCC (100%)" },
      { fact: "cca.class12.additions", label: "Class 12 — additions" },
      { fact: "cca.class12.dispositions", label: "Class 12 — dispositions" },
      {
        fact: "cca.class12.all_disposed",
        label: "Class 12 — every asset in the class was disposed of",
        kind: "flag",
      },
      { fact: "cca.class50.opening_ucc", label: "Class 50 — opening UCC (55%)" },
      { fact: "cca.class50.additions", label: "Class 50 — additions" },
      { fact: "cca.class50.dispositions", label: "Class 50 — dispositions" },
      {
        fact: "cca.class50.all_disposed",
        label: "Class 50 — every asset in the class was disposed of",
        kind: "flag",
      },
      {
        fact: "cca.limit_claim",
        label: "Claim less than the maximum",
        kind: "flag",
        hint: "Capital cost allowance is discretionary. Leave this off to claim the maximum.",
      },
      {
        fact: "cca.claimed",
        label: "Amount to claim",
        hint: "Only used when the box above is ticked. Anything above the maximum is reduced to it.",
      },
    ],
  },
  {
    id: "adjustments",
    title: "Tax adjustments",
    blurb:
      "Schedule 1 reconciles the accounting profit to income for tax purposes. Most of it is done from the figures above; these are the ones only you know.",
    fields: [
      {
        fact: "t2.active_business_income",
        label: "Active business income",
        hint: "Income eligible for the small business deduction. Leaving this blank claims no deduction — it does not mean all income is active.",
      },
      { fact: "t2.charitable_donations", label: "Charitable donations" },
      { fact: "t2.fines_and_penalties", label: "Fines and penalties" },
      { fact: "t2.club_dues", label: "Club dues and recreational facilities" },
      { fact: "t2.other_additions", label: "Other additions" },
      {
        fact: "t2.other_deductions",
        label: "Other deductions on Schedule 1",
        hint: "Deductions in arriving at net income for tax purposes, such as a reserve claimed this year.",
      },
      {
        fact: "t2.deductions",
        label: "Losses and other deductions from net income",
        hint: "Applied after net income to reach taxable income — non-capital loss carryforwards belong here, not above.",
      },
      { fact: "t2.instalments", label: "Instalments paid" },
    ],
  },
];

export const ALL_FACTS: string[] = SECTIONS.flatMap((s) =>
  s.fields.map((f) => f.fact),
);
