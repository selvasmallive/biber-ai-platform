import type { Computed } from "../types";

const KEY_LINES = [
  ["gifi.9999", "Net income per the statements"],
  ["t2.300", "Net income for tax purposes"],
  ["t2.360", "Taxable income"],
  ["t2.430", "Small business deduction"],
  ["t2.700", "Federal Part I tax"],
  ["prov.tax", "Provincial tax"],
  ["summary.total_tax", "Total tax payable"],
  ["summary.balance", "Balance owing"],
] as const;

const money = (raw: string): string => {
  const n = Number(raw);
  if (Number.isNaN(n)) return raw;
  return n.toLocaleString("en-CA", {
    style: "currency",
    currency: "CAD",
  });
};

export function Summary({ result }: { result: Computed }) {
  const find = (id: string) =>
    result.lines.find((l) => l.id === id)?.value ?? "0";

  const balance = Number(find("summary.balance"));

  return (
    <div className="card summary">
      <h2>Summary</h2>

      <dl>
        {KEY_LINES.map(([id, label]) => (
          <div key={id} className="line">
            <dt>{label}</dt>
            <dd>{money(find(id))}</dd>
          </div>
        ))}
      </dl>

      <p className={balance > 0 ? "owing" : "refund"}>
        {balance > 0
          ? `The corporation owes ${money(String(balance))}.`
          : balance < 0
            ? `The corporation is owed ${money(String(-balance))}.`
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
    </div>
  );
}
