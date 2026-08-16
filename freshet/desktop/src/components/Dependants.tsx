interface Child {
  age: string;
  disabled: boolean;
  infirm: boolean;
}

function readChildren(facts: Record<string, string>): Child[] {
  const n = Number(facts["dependants.count"] ?? "0");
  if (!Number.isFinite(n) || n <= 0) return [];

  return Array.from({ length: n }, (_, i) => ({
    age: facts[`dependant.${i}.age`] ?? "",
    disabled: facts[`dependant.${i}.disabled`] === "1",
    infirm: facts[`dependant.${i}.infirm`] === "1",
  }));
}

/// Reduce the list to the aggregate counts the engine works in, and blank out
/// any rows left behind by a removal.
function toFacts(children: Child[], previousCount: number): Record<string, string> {
  const patch: Record<string, string> = {
    "dependants.count": String(children.length),
  };

  let under7 = 0;
  let sevenToSixteen = 0;
  let disabled = 0;
  let infirmMinor = 0;
  // Ontario's tax reduction counts children and impaired dependants on a
  // different basis from the child care limits, so they are counted separately
  // rather than reusing the age buckets.
  let minors = 0;
  let impaired = 0;

  children.forEach((c, i) => {
    patch[`dependant.${i}.age`] = c.age;
    patch[`dependant.${i}.disabled`] = c.disabled ? "1" : "0";
    patch[`dependant.${i}.infirm`] = c.infirm ? "1" : "0";

    const age = Number(c.age);
    const known = c.age.trim() !== "" && Number.isFinite(age);

    // A child eligible for the disability credit carries the $11,000 limit
    // *instead of* the age-based one, so they must not be counted twice.
    if (c.disabled) {
      disabled += 1;
    } else if (known) {
      if (age < 7) under7 += 1;
      else if (age <= 16) sevenToSixteen += 1;
    }

    if (c.infirm && known && age < 18) infirmMinor += 1;
    if (known && age < 18) minors += 1;
    if (c.infirm || c.disabled) impaired += 1;
  });

  for (let i = children.length; i < previousCount; i += 1) {
    patch[`dependant.${i}.age`] = "";
    patch[`dependant.${i}.disabled`] = "0";
    patch[`dependant.${i}.infirm`] = "0";
  }

  patch["dependants.count_under_7"] = String(under7);
  patch["dependants.count_7_to_16"] = String(sevenToSixteen);
  patch["dependants.count_disabled"] = String(disabled);
  patch["dependants.count_infirm_minor"] = String(infirmMinor);
  patch["dependants.count_minor"] = String(minors);
  patch["dependants.count_impaired"] = String(impaired);

  return patch;
}

interface Props {
  facts: Record<string, string>;
  onFacts: (patch: Record<string, string>) => void;
  onFact: (key: string, value: string) => void;
}

export default function Dependants({ facts, onFacts, onFact }: Props) {
  const children = readChildren(facts);
  const write = (next: Child[]) => onFacts(toFacts(next, children.length));

  const patch = (i: number, change: Partial<Child>) =>
    write(children.map((c, j) => (j === i ? { ...c, ...change } : c)));

  const claimsEligible = facts["dependants.eligible_dependant_claimed"] === "1";

  return (
    <>
      <p className="hint">
        Each child carries their own annual child care limit — $8,000 under 7,
        $5,000 from 7 to 16, $11,000 if they are eligible for the disability tax
        credit — and the limits add together.
      </p>

      {children.length === 0 ? (
        <p className="hint">No dependants added.</p>
      ) : (
        <ul className="child-list">
          {children.map((c, i) => (
            <li key={i}>
              <div className="child-age">
                <label htmlFor={`child-${i}`}>Age at December 31</label>
                <input
                  id={`child-${i}`}
                  type="text"
                  inputMode="numeric"
                  placeholder="e.g. 5"
                  value={c.age}
                  onChange={(e) => patch(i, { age: e.target.value })}
                />
              </div>

              <div className="child-flags">
                <label>
                  <input
                    type="checkbox"
                    checked={c.disabled}
                    onChange={(e) => patch(i, { disabled: e.target.checked })}
                  />
                  Disability tax credit
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={c.infirm}
                    onChange={(e) => patch(i, { infirm: e.target.checked })}
                  />
                  Infirm
                </label>
              </div>

              <button
                className="ghost"
                aria-label={`Remove dependant ${i + 1}`}
                onClick={() => write(children.filter((_, j) => j !== i))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        className="ghost"
        style={{ marginTop: 12 }}
        onClick={() => write([...children, { age: "", disabled: false, infirm: false }])}
      >
        Add a dependant
      </button>

      <h2 style={{ marginTop: 26 }}>Amount for an eligible dependant</h2>
      <p className="hint">
        For someone supporting a dependant without a spouse — a single parent,
        usually. It is the same size as the spousal amount and takes its place,
        so it does not apply if you had a partner on December 31.
      </p>

      <label className="check-row">
        <input
          type="checkbox"
          checked={claimsEligible}
          onChange={(e) =>
            onFact(
              "dependants.eligible_dependant_claimed",
              e.target.checked ? "1" : "0",
            )
          }
        />
        I supported a dependant and had no spouse or partner
      </label>

      {claimsEligible && (
        <div className="field" style={{ marginTop: 14 }}>
          <label htmlFor="dep-income">
            That dependant's net income
            <span className="box">reduces the amount</span>
          </label>
          <input
            id="dep-income"
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={facts["dependants.eligible_dependant_net_income"] ?? ""}
            onChange={(e) =>
              onFact("dependants.eligible_dependant_net_income", e.target.value)
            }
          />
        </div>
      )}
    </>
  );
}
