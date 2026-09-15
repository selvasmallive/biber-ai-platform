import type { Section } from "../../../shared/t2-interview";

interface Props {
  section: Section;
  facts: Record<string, string>;
  onChange: (fact: string, value: string) => void;
}

export function Interview({ section, facts, onChange }: Props) {
  return (
    <section className="card">
      <h2>{section.title}</h2>
      {section.blurb && <p className="blurb">{section.blurb}</p>}

      <div className="fields">
        {section.fields.map((f) =>
          f.kind === "flag" ? (
            <label key={f.fact} className="field flag">
              <span className="label">
                <input
                  type="checkbox"
                  checked={facts[f.fact] === "1"}
                  // Stored as the string the engine reads, rather than as a
                  // boolean converted somewhere later. One representation.
                  onChange={(e) => onChange(f.fact, e.target.checked ? "1" : "0")}
                />
                {f.label}
              </span>
              {f.hint && <span className="hint">{f.hint}</span>}
            </label>
          ) : (
          <label key={f.fact} className="field">
            <span className="label">{f.label}</span>
            <input
              // `text`, not `number`. A number input silently discards a
              // pasted "$1,234.56" and swallows the scroll wheel over a
              // focused field, which has cost people real money elsewhere.
              // The engine parses what was typed.
              type="text"
              inputMode="decimal"
              autoComplete="off"
              value={facts[f.fact] ?? ""}
              placeholder="0.00"
              onChange={(e) => onChange(f.fact, e.target.value)}
            />
            {f.hint && <span className="hint">{f.hint}</span>}
          </label>
          ),
        )}
      </div>
    </section>
  );
}
