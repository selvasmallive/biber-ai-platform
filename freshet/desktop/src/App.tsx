import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  computeReturn,
  errorText,
  getSettings,
  listReturns,
  loadReturn,
  money,
  saveReturn,
  storageStatus,
  supported,
} from "./api";
import Advisor from "./components/Advisor";
import Import from "./components/Import";
import Interview from "./components/Interview";
import SavedReturns from "./components/SavedReturns";
import Settings from "./components/Settings";
import Spouse from "./components/Spouse";
import Summary from "./components/Summary";
import type {
  ComputeInput,
  ReturnSummary,
  ReturnView,
  SettingsView,
  StorageStatus,
} from "./types";

type Tab = "summary" | "import" | "spouse" | "advisor" | "saved" | "settings";
type SaveState = "idle" | "saving" | "saved" | "error";

const TABS: Tab[] = ["summary", "import", "spouse", "advisor", "saved", "settings"];

const TAB_LABELS: Record<Tab, string> = {
  summary: "Your return",
  import: "Import",
  spouse: "Spouse",
  advisor: "Advisor",
  saved: "Saved",
  settings: "Settings",
};

export default function App() {
  // The newest year with data, which is not the certification target: that is
  // 2027, and its amounts are not published yet. Corrected from `supported()`
  // as soon as it answers, so this initial value only shows for one frame.
  const [year, setYear] = useState(2026);
  const [province, setProvince] = useState("on");
  const [facts, setFacts] = useState<Record<string, string>>({});
  const [label, setLabel] = useState("Untitled return");
  const [options, setOptions] = useState({ years: [2026], provinces: ["on"] });
  const [result, setResult] = useState<ReturnView | null>(null);
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState<string | null>(null);

  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [saved, setSaved] = useState<ReturnSummary[]>([]);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  // Which stored return is open. A ref, not state: autosave must not re-fire
  // merely because the id changed after the first save.
  const openId = useRef<string | null>(null);
  const justLoaded = useRef(false);

  const input: ComputeInput = useMemo(
    () => ({ tax_year: year, province, facts }),
    [year, province, facts],
  );

  useEffect(() => {
    supported().then(setOptions).catch(() => undefined);
    getSettings().then(setSettings).catch(() => undefined);
    storageStatus()
      .then((s) => {
        setStorage(s);
        if (s.available) listReturns().then(setSaved).catch(() => undefined);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    // The engine is fast enough to run on every keystroke, but a short debounce
    // keeps the refund figure from flickering mid-number.
    const timer = setTimeout(() => {
      computeReturn(input)
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e) => setError(errorText(e)));
    }, 120);

    return () => clearTimeout(timer);
  }, [input]);

  useEffect(() => {
    if (!storage?.available) return;

    // Opening a return should not immediately rewrite it.
    if (justLoaded.current) {
      justLoaded.current = false;
      return;
    }

    // Don't litter the vault with empty returns the user never started.
    const started = Object.values(facts).some((v) => v.trim() !== "");
    if (!started) return;

    const timer = setTimeout(async () => {
      setSaveState("saving");
      try {
        const summary = await saveReturn({
          id: openId.current,
          label,
          tax_year: year,
          province,
          facts,
        });
        openId.current = summary.id;
        setSaveState("saved");
        setSaveError(null);
        setSaved(await listReturns());
      } catch (e) {
        setSaveState("error");
        setSaveError(errorText(e));
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [facts, label, year, province, storage]);

  const setFact = useCallback(
    (key: string, value: string) => setFacts((f) => ({ ...f, [key]: value })),
    [],
  );

  /// Several keys at once, for editors that derive facts from a list.
  const applyFacts = useCallback(
    (patch: Record<string, string>) => setFacts((f) => ({ ...f, ...patch })),
    [],
  );

  const openReturn = useCallback(async (id: string) => {
    const r = await loadReturn(id);
    justLoaded.current = true;
    openId.current = r.id;
    setLabel(r.label);
    setYear(r.tax_year);
    setProvince(r.province);
    setFacts(r.facts);
    setSaveState("saved");
    setTab("summary");
  }, []);

  const newReturn = useCallback(() => {
    justLoaded.current = true;
    openId.current = null;
    setFacts({});
    setLabel(`${year} return`);
    setSaveState("idle");
    setTab("summary");
  }, [year]);

  const summary = result?.summary;

  const saveLabel =
    saveState === "saving"
      ? "Saving…"
      : saveState === "saved"
        ? "Saved · encrypted"
        : saveState === "error"
          ? "Not saved"
          : "";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          Freshet <small>T1 · {year} · {province.toUpperCase()}</small>
        </div>

        <input
          className="label-input"
          value={label}
          aria-label="Return name"
          onChange={(e) => setLabel(e.target.value)}
        />

        {saveLabel && (
          <span className={`save-state ${saveState}`} title={saveError ?? undefined}>
            {saveLabel}
          </span>
        )}

        <div className="spacer" />

        {summary && (
          <div className={`headline ${summary.is_refund ? "refund" : "owing"}`}>
            <span className="caption">
              {summary.is_refund ? "Refund" : "Balance owing"}
            </span>
            <span className="amount">
              {money(summary.is_refund ? summary.refund : `-${summary.refund}`)}
            </span>
          </div>
        )}
      </header>

      <div className="columns">
        <section className="pane">
          <Interview
            year={year}
            province={province}
            facts={facts}
            options={options}
            onYear={setYear}
            onProvince={setProvince}
            onFact={setFact}
            onFacts={applyFacts}
          />
        </section>

        <section className="pane">
          <nav className="tabs">
            {TABS.map((t) => {
              const flagged =
                t === "summary" && result && result.diagnostics.length > 0;

              return (
                <button
                  key={t}
                  className={`tab ${tab === t ? "active" : ""}`}
                  onClick={() => setTab(t)}
                >
                  {TAB_LABELS[t]}
                  {t === "saved" && saved.length > 0 && ` (${saved.length})`}
                  {flagged && (
                    <span className={`dot ${result.has_errors ? "error" : "warn"}`} />
                  )}
                </button>
              );
            })}
          </nav>

          {error && (
            <div style={{ padding: "16px 20px 0" }}>
              <div className="notice danger">
                <strong>Could not compute this return</strong>
                {error}
              </div>
            </div>
          )}

          {tab === "summary" && <Summary result={result} input={input} />}

          {tab === "import" && (
            <Import
              input={input}
              onApply={(next) => {
                setFacts(next);
                setTab("summary");
              }}
            />
          )}

          {tab === "spouse" && <Spouse input={input} yourLabel={label} />}

          {tab === "advisor" && (
            <Advisor
              settings={settings}
              input={input}
              onSettings={setSettings}
              onOpenSettings={() => setTab("settings")}
            />
          )}

          {tab === "saved" && (
            <SavedReturns
              storage={storage}
              returns={saved}
              openId={openId.current}
              saveError={saveError}
              onOpen={openReturn}
              onNew={newReturn}
              onDeleted={(remaining, deletedId) => {
                setSaved(remaining);
                if (openId.current === deletedId) newReturn();
              }}
            />
          )}

          {tab === "settings" && (
            <Settings
              settings={settings}
              onSettings={setSettings}
              taxYear={input.tax_year}
            />
          )}
        </section>
      </div>
    </div>
  );
}
