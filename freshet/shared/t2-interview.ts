//! What the T2 interview asks for, in every channel that has one.
//!
//! Shared between the desktop app and the browser build rather than copied
//! into each. The labels and hints are presentation and could reasonably
//! differ; the **fact keys** cannot. They are the join between a text box and
//! a line on the return, and a wrong one is the worst defect this product can
//! have — nothing errors, the engine finds no fact under `gifi.800`, reads
//! zero, and computes a return that is internally consistent, professionally
//! formatted, and wrong.
//!
//! `crates/freshet-taxdata/tests/t2_interview.rs` reads this file from Rust
//! and checks the keys against the form definitions in both directions. It
//! caught nine missing fields the first time it ran. A second copy for the
//! desktop would be outside that check and free to drift, which is how the
//! nine got missed in the first place.

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
///
/// The set is GIFI-Short's (CRA form T1178), which is a published subset aimed
/// at corporations under a million in revenue and assets. The labels are CRA's
/// own wording, lightly punctuated for reading on screen; the codes are exact.
export const SECTIONS: Section[] = [
  {
    id: "revenue",
    title: "Revenue",
    blurb:
      "From the financial statements, before any tax adjustment. The return starts here rather than at taxable income, because that is the order the work actually happens in.",
    fields: [
      { fact: "gifi.8000", label: "Trade sales of goods and services (8000)" },
      { fact: "gifi.8090", label: "Investment revenue (8090)" },
      { fact: "gifi.8095", label: "Dividend income (8095)" },
      { fact: "gifi.8120", label: "Commission revenue (8120)" },
      { fact: "gifi.8140", label: "Rental revenue (8140)" },
      {
        fact: "gifi.8210",
        label: "Realized gains and losses on disposal of assets (8210)",
        hint: "The accounting gain. Tax treats dispositions separately, through capital cost allowance and capital gains.",
      },
      { fact: "gifi.8230", label: "Other revenue (8230)" },
    ],
  },
  {
    id: "cost-of-sales",
    title: "Cost of sales",
    blurb:
      "Opening inventory plus what was bought and the direct costs of producing it, less what was still on hand at the year end.",
    fields: [
      { fact: "gifi.8300", label: "Opening inventory (8300)" },
      {
        fact: "gifi.8320",
        label: "Purchases and cost of materials (8320)",
        hint: "A corporation that tracks cost of sales directly can enter it here and leave both inventories blank.",
      },
      { fact: "gifi.8340", label: "Direct wages (8340)" },
      { fact: "gifi.8350", label: "Benefits on direct wages (8350)" },
      { fact: "gifi.8360", label: "Trades and sub-contracts (8360)" },
      {
        fact: "gifi.8500",
        label: "Closing inventory (8500)",
        hint: "Entered as a positive figure and subtracted: what is still on hand was not sold.",
      },
    ],
  },
  {
    id: "operating",
    title: "Operating expenses",
    fields: [
      { fact: "gifi.8520", label: "Advertising and promotion (8520)" },
      {
        fact: "gifi.8523",
        label: "Meals and entertainment (8523)",
        hint: "Half of this is added back on Schedule 1 automatically.",
      },
      { fact: "gifi.8570", label: "Amortization of intangible assets (8570)" },
      { fact: "gifi.8590", label: "Bad debt expense (8590)" },
      { fact: "gifi.8620", label: "Employee benefits (8620)" },
      {
        fact: "gifi.8670",
        label: "Amortization of tangible assets (8670)",
        hint: "Added back in full, and replaced by capital cost allowance.",
      },
      { fact: "gifi.8690", label: "Insurance (8690)" },
      { fact: "gifi.8710", label: "Interest and bank charges (8710)" },
      { fact: "gifi.8760", label: "Business taxes, licences and memberships (8760)" },
      { fact: "gifi.8810", label: "Office expenses (8810)" },
      { fact: "gifi.8860", label: "Professional fees (8860)" },
      { fact: "gifi.8910", label: "Rental (8910)" },
      { fact: "gifi.8960", label: "Repairs and maintenance (8960)" },
      { fact: "gifi.9060", label: "Salaries and wages (9060)" },
      { fact: "gifi.9110", label: "Sub-contracts (9110)" },
      { fact: "gifi.9130", label: "Supplies (9130)" },
      { fact: "gifi.9150", label: "Computer-related expenses (9150)" },
      { fact: "gifi.9180", label: "Property taxes (9180)" },
      { fact: "gifi.9270", label: "Other expenses (9270)" },
    ],
  },
  {
    id: "income-taxes",
    title: "Income taxes and extraordinary items",
    blurb:
      "Income tax is not deductible in computing income for tax purposes, so whatever the accounts charged comes straight back on Schedule 1.",
    fields: [
      { fact: "gifi.9975", label: "Extraordinary items (9975)" },
      { fact: "gifi.9990", label: "Current income taxes (9990)" },
      {
        fact: "gifi.9995",
        label: "Future (deferred) income tax provision (9995)",
        hint: "Added back with the current provision. Neither is deductible.",
      },
    ],
  },
  {
    id: "assets",
    title: "Balance sheet — assets",
    blurb:
      "At the year end. Accumulated amortization is entered as a positive figure and subtracted for you, the way it appears on a statement.",
    fields: [
      { fact: "gifi.1000", label: "Cash and deposits (1000)" },
      { fact: "gifi.1060", label: "Accounts receivable (1060)" },
      {
        fact: "gifi.1061",
        label: "Allowance for doubtful accounts (1061)",
        hint: "Positive; subtracted.",
      },
      { fact: "gifi.1120", label: "Inventories (1120)" },
      { fact: "gifi.1180", label: "Short-term investments (1180)" },
      { fact: "gifi.1240", label: "Loans and notes receivable (1240)" },
      { fact: "gifi.1300", label: "Due from shareholders or directors (1300)" },
      { fact: "gifi.1480", label: "Other current assets (1480)" },
      { fact: "gifi.1600", label: "Land (1600)" },
      { fact: "gifi.1680", label: "Buildings (1680)" },
      {
        fact: "gifi.1681",
        label: "Accumulated amortization of buildings (1681)",
        hint: "Positive; subtracted.",
      },
      { fact: "gifi.1740", label: "Machinery and equipment (1740)" },
      {
        fact: "gifi.1741",
        label: "Accumulated amortization of machinery and equipment (1741)",
        hint: "Positive; subtracted.",
      },
      { fact: "gifi.1787", label: "Furniture and fixtures (1787)" },
      {
        fact: "gifi.1788",
        label: "Accumulated amortization of furniture and fixtures (1788)",
        hint: "Positive; subtracted.",
      },
      { fact: "gifi.1900", label: "Other tangible capital assets (1900)" },
      {
        fact: "gifi.1901",
        label: "Accumulated amortization of other tangible capital assets (1901)",
        hint: "Positive; subtracted.",
      },
      { fact: "gifi.2010", label: "Intangible assets (2010)" },
      {
        fact: "gifi.2011",
        label: "Accumulated amortization of intangible assets (2011)",
        hint: "Positive; subtracted.",
      },
      { fact: "gifi.2420", label: "Other long-term assets (2420)" },
    ],
  },
  {
    id: "liabilities",
    title: "Balance sheet — liabilities and equity",
    blurb:
      "Freshet checks that the statements balance and says so if they do not.",
    fields: [
      { fact: "gifi.2600", label: "Bank overdraft (2600)" },
      { fact: "gifi.2620", label: "Amounts payable and accrued liabilities (2620)" },
      { fact: "gifi.2680", label: "Taxes payable (2680)" },
      { fact: "gifi.2700", label: "Short-term debt (2700)" },
      { fact: "gifi.2780", label: "Due to shareholders or directors (2780)" },
      { fact: "gifi.2920", label: "Current portion of long-term liability (2920)" },
      { fact: "gifi.2960", label: "Other current liabilities (2960)" },
      { fact: "gifi.3140", label: "Long-term debt (3140)" },
      { fact: "gifi.3240", label: "Future (deferred) income taxes (3240)" },
      { fact: "gifi.3320", label: "Other long-term liabilities (3320)" },
      { fact: "gifi.3500", label: "Common shares (3500)" },
      { fact: "gifi.3520", label: "Preferred shares (3520)" },
      { fact: "gifi.3540", label: "Contributed and other surplus (3540)" },
      { fact: "gifi.3600", label: "Retained earnings or deficit (3600)" },
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
