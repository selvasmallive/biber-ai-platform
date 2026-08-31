//! The bridge between the webview and the engine.
//!
//! Every provider call leaves from here, never from the frontend. That is
//! deliberate: it means the consent and redaction checks in `freshet-advisor`
//! sit on the only path to the network, and no amount of frontend code can go
//! around them.

use std::collections::BTreeMap;

use freshet_advisor::{Advisor, Consent, Provider, ProviderConfig, Turn};
use freshet_autofill::{
    apply, reconcile, CraAutofill, Disposition, FixtureSource, SlipSource,
};
use freshet_couple::{optimize, Household, Spouse};
use freshet_engine::{compute, Assessment, Date, Decimal, FactSet, Period, Severity};
use freshet_license::{Activation, Credential, LicenceError};
use serde::{Deserialize, Serialize};
use tauri::State;

use crate::state::{key_ref_for, read_key, write_key, AppState, SettingsView, VaultState};

// -- return computation ---------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
pub struct ComputeInput {
    pub tax_year: u16,
    pub province: String,
    /// Raw strings straight from the interview fields, keyed by fact name.
    pub facts: BTreeMap<String, String>,
}

#[derive(Debug, Serialize)]
pub struct LineView {
    pub id: String,
    pub label: String,
    pub value: String,
    pub note: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SummaryView {
    pub total_income: String,
    pub net_income: String,
    pub taxable_income: String,
    pub federal_tax: String,
    pub provincial_tax: String,
    pub total_tax: String,
    pub withheld: String,
    /// Paid whether or not tax is owing — CPP/EI overpayments and the Ontario
    /// CARE credit.
    pub refundable_credits: String,
    /// Positive means money back.
    pub refund: String,
    pub is_refund: bool,
    pub average_rate: String,
    /// Tax on the next dollar earned, as a percentage. This is the number that
    /// makes advice concrete: it turns "consider an RRSP" into "$1,000 in saves
    /// you $296".
    pub marginal_rate: String,
}

#[derive(Debug, Serialize)]
pub struct DiagnosticView {
    pub id: String,
    /// `"error"`, `"warning"`, or `"info"`.
    pub severity: String,
    pub message: String,
    pub help: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ReturnView {
    pub tax_year: u16,
    pub province: String,
    pub summary: SummaryView,
    pub lines: Vec<LineView>,
    /// Problems with the software (unverified tax data).
    pub warnings: Vec<String>,
    /// Problems with the return, worst first.
    pub diagnostics: Vec<DiagnosticView>,
    pub has_errors: bool,
    /// Whether CRA has certified this product for this tax year. Independent of
    /// whether the return itself is sound.
    pub certified_to_file: bool,
    pub filable: bool,
}

fn severity_str(s: Severity) -> &'static str {
    match s {
        Severity::Error => "error",
        Severity::Warning => "warning",
        Severity::Info => "info",
    }
}

/// Tolerate what people actually type: `$85,000.00`, `85 000`, `85000`.
fn parse_money(raw: &str) -> Option<Decimal> {
    let cleaned: String = raw
        .chars()
        .filter(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();

    if cleaned.is_empty() {
        return None;
    }
    Decimal::from_str_exact(&cleaned).ok()
}

fn assess(input: &ComputeInput) -> Result<Assessment, String> {
    let forms =
        freshet_taxdata::t1_forms(input.tax_year, &input.province).map_err(|e| e.to_string())?;
    let packs =
        freshet_taxdata::packs(input.tax_year, &input.province).map_err(|e| e.to_string())?;

    let mut facts = FactSet::new();
    for (key, raw) in &input.facts {
        if let Some(value) = parse_money(raw) {
            facts.set(key.clone(), value);
        }
    }

    compute(&forms, &packs, &facts).map_err(|e| e.to_string())
}

fn line(a: &Assessment, id: &str) -> Decimal {
    a.get(id).unwrap_or(Decimal::ZERO)
}

/// Render for the UI with exactly two places, so columns line up and a rate of
/// zero reads as `0.00` rather than `0`.
fn dp2(v: Decimal) -> String {
    let mut v = v;
    v.rescale(2);
    v.to_string()
}

/// Measure the marginal rate empirically rather than looking up a bracket:
/// clawbacks, surtaxes and phase-outs all bend the true rate away from the
/// headline bracket, and re-running the engine is microseconds.
fn marginal_rate(input: &ComputeInput, base_tax: Decimal) -> Decimal {
    const STEP: i64 = 1000;
    const KEY: &str = "t4.employment_income";

    let mut probe = input.clone();
    let current = probe.facts.get(KEY).and_then(|s| parse_money(s)).unwrap_or(Decimal::ZERO);
    probe
        .facts
        .insert(KEY.to_string(), (current + Decimal::from(STEP)).to_string());

    match assess(&probe) {
        Ok(bumped) => ((line(&bumped, "summary.total_tax") - base_tax) / Decimal::from(STEP)
            * Decimal::from(100))
        .round_dp(2),
        Err(_) => Decimal::ZERO,
    }
}

#[tauri::command]
pub fn compute_return(input: ComputeInput) -> Result<ReturnView, String> {
    let a = assess(&input)?;
    let certified = freshet_taxdata::is_certified(input.tax_year, &input.province);

    let total_income = line(&a, "fed.15000");
    let total_tax = line(&a, "summary.total_tax");
    let balance = line(&a, "summary.balance");

    let average_rate = if total_income.is_zero() {
        Decimal::ZERO
    } else {
        (total_tax / total_income * Decimal::from(100)).round_dp(2)
    };

    Ok(ReturnView {
        tax_year: a.tax_year,
        province: a.province.clone(),
        summary: SummaryView {
            total_income: dp2(total_income),
            net_income: dp2(line(&a, "fed.23600")),
            taxable_income: dp2(line(&a, "fed.26000")),
            federal_tax: dp2(line(&a, "fed.42000")),
            provincial_tax: dp2(line(&a, "on.42800")),
            total_tax: dp2(total_tax),
            withheld: dp2(line(&a, "fed.43700")),
            refundable_credits: dp2(line(&a, "summary.refundable_credits")),
            refund: dp2(-balance),
            is_refund: balance.is_sign_negative(),
            average_rate: dp2(average_rate),
            marginal_rate: dp2(marginal_rate(&input, total_tax)),
        },
        lines: a
            .audit
            .iter()
            .map(|e| LineView {
                id: e.id.clone(),
                label: e.label.clone(),
                value: dp2(e.value),
                note: e.note.clone(),
            })
            .collect(),
        diagnostics: a
            .diagnostics
            .iter()
            .map(|d| DiagnosticView {
                id: d.id.clone(),
                severity: severity_str(d.severity).to_string(),
                message: d.message.clone(),
                help: d.help.clone(),
            })
            .collect(),
        has_errors: a.has_errors(),
        certified_to_file: certified,
        // Three independent gates: our tax data must be verified, the return
        // must have no errors, and CRA must have certified this product for
        // this specific tax year.
        filable: a.is_filable() && certified,
        warnings: {
            let mut w = a.warnings.clone();
            if !certified {
                w.push(format!(
                    "not certified by CRA to file {}: this return can be modelled but not transmitted",
                    a.tax_year
                ));
            }
            w
        },
    })
}

#[tauri::command]
pub fn supported() -> serde_json::Value {
    serde_json::json!({
        "years": freshet_taxdata::SUPPORTED_YEARS,
        "provinces": freshet_taxdata::supported_provinces(),
    })
}

// -- settings -------------------------------------------------------------

#[tauri::command]
pub fn get_settings(state: State<'_, AppState>) -> SettingsView {
    state.view()
}

#[tauri::command]
pub fn set_provider(
    state: State<'_, AppState>,
    provider: Provider,
    api_key: Option<String>,
) -> Result<SettingsView, String> {
    let key_ref = key_ref_for(&provider);

    if let (Some(r), Some(key)) = (key_ref.as_ref(), api_key.as_ref()) {
        write_key(r, key.trim())?;
    }

    {
        let mut settings = state.settings.lock().unwrap();

        // Changing provider invalidates consent: the user agreed to disclose to
        // a specific recipient, not to whoever is configured later.
        let changed = settings
            .provider
            .as_ref()
            .is_none_or(|c| c.provider.label() != provider.label());
        if changed {
            settings.consent = None;
        }

        settings.provider = Some(ProviderConfig {
            provider,
            key_ref,
            max_tokens: 2048,
        });
    }

    state.save()?;
    Ok(state.view())
}

#[tauri::command]
pub fn grant_consent(state: State<'_, AppState>) -> Result<SettingsView, String> {
    {
        let mut settings = state.settings.lock().unwrap();
        let config = settings
            .provider
            .as_ref()
            .ok_or("configure a model provider first")?;

        settings.consent = Some(Consent {
            provider_label: config.provider.label(),
            granted_at_unix: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs() as i64)
                .unwrap_or(0),
        });
    }

    state.save()?;
    Ok(state.view())
}

#[tauri::command]
pub fn revoke_consent(state: State<'_, AppState>) -> Result<SettingsView, String> {
    state.settings.lock().unwrap().consent = None;
    state.save()?;
    Ok(state.view())
}

// -- advisor --------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct ChatInput {
    pub compute: ComputeInput,
    pub history: Vec<Turn>,
    pub message: String,
}

#[derive(Debug, Serialize)]
pub struct ChatReply {
    pub reply: String,
    /// Categories of PII stripped before sending, so the UI can tell the user
    /// what was caught rather than silently swallowing it.
    pub redacted: Vec<String>,
    pub remote: bool,
}

#[tauri::command]
pub async fn advisor_chat(
    state: State<'_, AppState>,
    input: ChatInput,
) -> Result<ChatReply, String> {
    let assessment = assess(&input.compute)?;

    // Take everything needed off the lock before any await: a std MutexGuard is
    // not Send and must not straddle a suspension point.
    let (config, consent) = {
        let settings = state.settings.lock().unwrap();
        (
            settings
                .provider
                .clone()
                .ok_or("configure a model provider in Settings first")?,
            settings.consent.clone(),
        )
    };

    let advisor = Advisor::new(config);

    let prepared = advisor
        .prepare(
            &assessment,
            &input.history,
            &input.message,
            consent.as_ref(),
        )
        .map_err(|e| e.to_string())?;

    let api_key = advisor
        .config
        .key_ref
        .as_ref()
        .and_then(read_key);

    let req = advisor
        .request(&prepared, api_key.as_deref())
        .map_err(|e| e.to_string())?;

    let mut builder = reqwest::Client::new().post(&req.url);
    for (name, value) in &req.headers {
        builder = builder.header(name, value);
    }

    let response = builder
        .json(&req.body)
        .send()
        .await
        .map_err(|e| format!("could not reach {}: {e}", advisor.config.provider.label()))?;

    let status = response.status();
    let body: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("unreadable response from the provider: {e}"))?;

    if !status.is_success() {
        let detail = body["error"]["message"]
            .as_str()
            .unwrap_or("no detail supplied");
        return Err(format!("{} returned {status}: {detail}", advisor.config.provider.label()));
    }

    let reply = extract_reply(&body)
        .ok_or_else(|| format!("could not find a reply in the provider response: {body}"))?;

    Ok(ChatReply {
        reply,
        redacted: prepared
            .redacted
            .iter()
            .map(|k| format!("{k:?}"))
            .collect(),
        remote: prepared.remote,
    })
}

/// Anthropic returns `content[].text`; OpenAI-compatible endpoints return
/// `choices[0].message.content`.
fn extract_reply(body: &serde_json::Value) -> Option<String> {
    if let Some(text) = body["content"][0]["text"].as_str() {
        return Some(text.to_string());
    }
    body["choices"][0]["message"]["content"]
        .as_str()
        .map(str::to_string)
}

// -- coupled returns ------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct HouseholdInput {
    pub your_label: String,
    pub partner_label: String,
    pub partner_facts: BTreeMap<String, String>,
}

#[derive(Debug, Serialize)]
pub struct SpouseResultView {
    pub label: String,
    pub net_income: String,
    pub spouse_amount: String,
    pub age_amount: String,
    pub pension_amount: String,
    /// Schedule 2 amounts received from the other spouse.
    pub transferred_in: String,
    /// Tuition that neither return could use and which must carry forward.
    pub tuition_carryforward: String,
    pub total_tax: String,
    pub refund: String,
    pub is_refund: bool,
    pub medical_claimed: String,
    pub donations_claimed: String,
}

#[derive(Debug, Serialize)]
pub struct DecisionView {
    pub item: String,
    pub chose: String,
    pub saved: String,
    /// True when the rules fixed the answer and nothing was optimized.
    pub mandatory: bool,
    pub why: String,
}

#[derive(Debug, Serialize)]
pub struct CoupleView {
    pub you: SpouseResultView,
    pub partner: SpouseResultView,
    pub combined_tax: String,
    pub combined_refund: String,
    pub combined_is_refund: bool,
    pub decisions: Vec<DecisionView>,
    /// Combined tax saved against the worst allocation considered.
    pub saving_vs_worst: String,
    pub allocations_considered: usize,
    /// Dollars of pension income moved, and which way. Empty label when none.
    pub pension_split_amount: String,
    pub pension_split_rate: String,
    pub pension_split_from: String,
    /// Who the child care deduction fell to. Empty when there is none.
    pub childcare_claimed_by: String,
}

fn spouse_view(label: &str, a: &Assessment) -> SpouseResultView {
    let balance = a.get("summary.balance").unwrap_or(Decimal::ZERO);

    SpouseResultView {
        label: label.to_string(),
        net_income: dp2(a.get("fed.23600").unwrap_or(Decimal::ZERO)),
        spouse_amount: dp2(a.get("fed.30300").unwrap_or(Decimal::ZERO)),
        age_amount: dp2(a.get("fed.30100").unwrap_or(Decimal::ZERO)),
        pension_amount: dp2(a.get("fed.31400").unwrap_or(Decimal::ZERO)),
        transferred_in: dp2(a.get("fed.32600").unwrap_or(Decimal::ZERO)),
        tuition_carryforward: dp2(a.get("fed.tuition_carryforward").unwrap_or(Decimal::ZERO)),
        total_tax: dp2(a.get("summary.total_tax").unwrap_or(Decimal::ZERO)),
        refund: dp2(-balance),
        is_refund: balance.is_sign_negative(),
        medical_claimed: dp2(a.get("fed.33099").unwrap_or(Decimal::ZERO)),
        donations_claimed: dp2(a.get("fed.34900").unwrap_or(Decimal::ZERO)),
    }
}

/// Compute both returns and choose the allocation with the lowest combined tax.
#[tauri::command]
pub fn couple_optimize(
    input: ComputeInput,
    household: HouseholdInput,
) -> Result<CoupleView, String> {
    let forms =
        freshet_taxdata::t1_forms(input.tax_year, &input.province).map_err(|e| e.to_string())?;
    let packs =
        freshet_taxdata::packs(input.tax_year, &input.province).map_err(|e| e.to_string())?;

    // Household-level amounts are entered once, on the primary return, rather
    // than asked for twice with two chances to disagree.
    let shared = |key: &str| {
        input
            .facts
            .get(key)
            .and_then(|v| parse_money(v))
            .unwrap_or(Decimal::ZERO)
    };

    let hh = Household {
        a: Spouse {
            label: household.your_label.clone(),
            facts: input.facts.clone(),
        },
        b: Spouse {
            label: household.partner_label.clone(),
            facts: household.partner_facts,
        },
        medical_expenses: shared("medical.expenses_claimed"),
        donations: shared("donations.claimed"),
        childcare: shared("childcare.expenses_claimed"),
        dependants: input
            .facts
            .iter()
            .filter(|(k, _)| k.starts_with("dependants.") || k.starts_with("dependant."))
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect(),
    };

    let hh_childcare = hh.childcare;
    let best = optimize(&forms, &packs, &hh).map_err(|e| e.to_string())?;
    let combined_balance = best.best.combined_balance;

    Ok(CoupleView {
        you: spouse_view(&household.your_label, &best.best.a),
        partner: spouse_view(&household.partner_label, &best.best.b),
        combined_tax: dp2(best.best.combined_tax),
        combined_refund: dp2(-combined_balance),
        combined_is_refund: combined_balance.is_sign_negative(),
        decisions: best
            .decisions
            .iter()
            .map(|d| DecisionView {
                item: d.item.clone(),
                chose: d.chose.clone(),
                saved: dp2(d.saved),
                mandatory: d.mandatory,
                why: d.why.clone(),
            })
            .collect(),
        saving_vs_worst: dp2(best.saving_vs_worst),
        allocations_considered: best.considered,
        pension_split_amount: dp2(best.best.pension_split_amount),
        pension_split_rate: dp2(
            (best.best.allocation.pension_split_rate * Decimal::from(100)).round_dp(0),
        ),
        pension_split_from: if best.best.allocation.splits() {
            match best.best.allocation.pension_from {
                freshet_couple::Claimant::A => household.your_label.clone(),
                freshet_couple::Claimant::B => household.partner_label.clone(),
            }
        } else {
            String::new()
        },
        childcare_claimed_by: if hh_childcare > Decimal::ZERO {
            match best.best.childcare_claimed_by {
                freshet_couple::Claimant::A => household.your_label.clone(),
                freshet_couple::Claimant::B => household.partner_label.clone(),
            }
        } else {
            String::new()
        },
    })
}

// -- RRSP planner ---------------------------------------------------------

const RRSP_KEY: &str = "rrsp.deduction_claimed";

#[derive(Debug, Serialize)]
pub struct RrspPoint {
    pub contribution: String,
    pub tax_saved: String,
    /// Cents saved per dollar contributed, between this point and the last.
    pub saving_rate: String,
}

#[derive(Debug, Serialize)]
pub struct RrspPlan {
    pub room: String,
    pub points: Vec<RrspPoint>,
    /// Contribution that brings the balance owing to zero, if reachable.
    pub to_break_even: Option<String>,
    /// The last dollar that still saves at the top rate. Beyond this the
    /// contribution has dropped you into a lower bracket and each further
    /// dollar is worth less.
    pub sweet_spot: Option<String>,
    pub sweet_spot_saving: Option<String>,
}

fn tax_and_balance(input: &ComputeInput, rrsp: Decimal) -> Result<(Decimal, Decimal), String> {
    let mut probe = input.clone();
    probe.facts.insert(RRSP_KEY.to_string(), rrsp.to_string());
    let a = assess(&probe)?;
    Ok((line(&a, "summary.total_tax"), line(&a, "summary.balance")))
}

/// Model what further RRSP contributions would be worth.
///
/// The answer is measured by re-running the whole return at each level rather
/// than multiplying by a bracket rate: the real curve bends at bracket edges,
/// at the Ontario surtax thresholds, and wherever an income-tested amount
/// phases in. A bracket-rate estimate is confidently wrong exactly where the
/// decision matters.
#[tauri::command]
pub fn rrsp_plan(input: ComputeInput, room: Option<String>) -> Result<RrspPlan, String> {
    const STEPS: u32 = 20;

    let already = input
        .facts
        .get(RRSP_KEY)
        .and_then(|s| parse_money(s))
        .unwrap_or(Decimal::ZERO);

    // Prefer the room CRA reported; otherwise approximate from this year's
    // income, which is all we can know without an import.
    let employment = input
        .facts
        .get("t4.employment_income")
        .and_then(|s| parse_money(s))
        .unwrap_or(Decimal::ZERO);

    let room = room
        .and_then(|r| parse_money(&r))
        .unwrap_or_else(|| (employment * Decimal::new(18, 2)).round_dp(2));

    if room <= Decimal::ZERO {
        return Ok(RrspPlan {
            room: dp2(Decimal::ZERO),
            points: Vec::new(),
            to_break_even: None,
            sweet_spot: None,
            sweet_spot_saving: None,
        });
    }

    let (base_tax, _) = tax_and_balance(&input, already)?;
    let step = (room / Decimal::from(STEPS)).round_dp(2);

    let mut points = Vec::new();
    let mut previous = (already, base_tax);
    let mut top_rate: Option<Decimal> = None;
    let mut sweet_spot = None;
    let mut sweet_spot_saving = None;

    for i in 1..=STEPS {
        let contribution = (step * Decimal::from(i)).round_dp(2);
        let (tax, _) = tax_and_balance(&input, already + contribution)?;

        let delta_contribution = already + contribution - previous.0;
        let rate = if delta_contribution.is_zero() {
            Decimal::ZERO
        } else {
            ((previous.1 - tax) / delta_contribution * Decimal::from(100)).round_dp(2)
        };

        // The first segment sets the top rate; the sweet spot is the last
        // contribution still earning it.
        match top_rate {
            None => {
                top_rate = Some(rate);
                sweet_spot = Some(contribution);
                sweet_spot_saving = Some(base_tax - tax);
            }
            Some(top) if rate >= top => {
                sweet_spot = Some(contribution);
                sweet_spot_saving = Some(base_tax - tax);
            }
            _ => {}
        }

        points.push(RrspPoint {
            contribution: dp2(contribution),
            tax_saved: dp2(base_tax - tax),
            saving_rate: dp2(rate),
        });

        previous = (already + contribution, tax);
    }

    // Smallest contribution that clears the balance owing, to the cent.
    let mut break_even = None;
    if tax_and_balance(&input, already)?.1 > Decimal::ZERO {
        let (mut lo, mut hi) = (Decimal::ZERO, room);
        if tax_and_balance(&input, already + hi)?.1 <= Decimal::ZERO {
            for _ in 0..40 {
                let mid = ((lo + hi) / Decimal::TWO).round_dp(2);
                if tax_and_balance(&input, already + mid)?.1 > Decimal::ZERO {
                    lo = mid;
                } else {
                    hi = mid;
                }
            }
            break_even = Some(dp2(hi));
        }
    }

    Ok(RrspPlan {
        room: dp2(room),
        points,
        to_break_even: break_even,
        sweet_spot: sweet_spot.map(dp2),
        sweet_spot_saving: sweet_spot_saving.map(dp2),
    })
}

// -- licensing ------------------------------------------------------------

const PRODUCT_T1: &str = "freshet-t1";
const PRODUCT_T2: &str = "freshet-t2";

/// The product this build's T1 paths refer to. A T2 licence names
/// [`PRODUCT_T2`] and the two must never be interchangeable.
const PRODUCT: &str = PRODUCT_T1;

/// Whether this build carries the built-in development licences.
///
/// Surfaced to the UI on purpose. If a build ever ships with them compiled in,
/// it says so on screen rather than quietly accepting them.
const DEV_LICENCES_COMPILED_IN: bool = cfg!(feature = "dev-licences");

/// What this product files.
///
/// A T1 is filed for a calendar year, so the tax year names it exactly. T2 is
/// the case that does not fit — a corporation files for a fiscal period ending
/// on any date — which is why `Filing` is an enum and why this function exists
/// rather than the conversion being inlined at each call site.
/// What is being filed, in the terms a licence is written in.
///
/// A T1 covers a calendar year and a T2 a fiscal period ending on a date, and a
/// licence for one must not unlock the other. This used to return a tax year
/// unconditionally, which was right while the T1 was the only product and
/// silently wrong the moment the T2 existed: a corporate return would have been
/// checked against a calendar year it does not have.
fn filing_for(what: &Filed) -> freshet_license::Filing {
    match what {
        Filed::T1 { tax_year } => freshet_license::Filing::TaxYear(*tax_year),
        // Coverage is expressed as a range of period end dates, so the end is
        // what decides whether a licence covers this return.
        Filed::T2 { period } => {
            freshet_license::Filing::PeriodEnding(period.end.to_days() * 86_400)
        }
    }
}

/// A return, identified the way its own return type identifies itself.
#[derive(Debug, Clone, Copy)]
pub enum Filed {
    T1 { tax_year: u16 },
    T2 { period: Period },
}

impl Filed {
    /// The product code a licence must name to unlock this return.
    fn product(&self) -> &'static str {
        match self {
            Filed::T1 { .. } => PRODUCT_T1,
            Filed::T2 { .. } => PRODUCT_T2,
        }
    }

    /// The tax year whose parameters and certification apply.
    ///
    /// For a corporation that is the year its fiscal period ends, which is also
    /// the year CRA certifies the return against.
    fn tax_year(&self) -> u16 {
        match self {
            Filed::T1 { tax_year } => *tax_year,
            Filed::T2 { period } => period.end.year as u16,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct LicenceView {
    pub present: bool,
    pub key: Option<String>,
    pub licensee: Option<String>,
    /// `"Licensed"`, `"Development licence"`, `"CRA certification licence"`.
    pub kind: Option<String>,
    /// "the 2025 and 2026 tax years", or a fiscal period range for a T2.
    pub coverage: Option<String>,
    /// "up to 5 returns", "one return", "unlimited returns".
    pub allowance: Option<String>,
    /// How many are left, or `None` for a professional licence — who should
    /// see "unlimited", not a number counting down from four billion.
    pub returns_left: Option<u32>,
    pub returns_filed: u32,
    /// Whether this licence permits filing the year currently open.
    pub entitled: bool,
    pub explanation: String,
    pub dev_licences_compiled_in: bool,

    /// When filing stops being covered. `None` never expires.
    ///
    /// Shown from the day a licence is installed rather than sprung eleven
    /// months later. A date someone has seen all along cannot ambush them.
    pub expires_unix: Option<i64>,

    /// A sentence about the expiry, or `None` when there is nothing worth
    /// saying. Absence is deliberate: a countdown running from day one is
    /// nagging, and nagging is what makes people stop reading warnings.
    pub standing_note: Option<String>,

    /// Whether that note deserves visual weight rather than passing mention.
    pub standing_urgent: bool,
}

fn no_licence(explanation: &str) -> LicenceView {
    LicenceView {
        present: false,
        key: None,
        licensee: None,
        kind: None,
        coverage: None,
        allowance: None,
        returns_left: None,
        returns_filed: 0,
        entitled: false,
        explanation: explanation.to_string(),
        dev_licences_compiled_in: DEV_LICENCES_COMPILED_IN,
        expires_unix: None,
        standing_note: None,
        standing_urgent: false,
    }
}

fn describe(token: &str, tax_year: u16, already_filed: u32) -> LicenceView {
    let licence = match freshet_license::verify(token) {
        Ok(l) => l,
        Err(e) => return no_licence(&e.to_string()),
    };

    let now = freshet_store::now_unix();
    let entitlement = licence.check(
        PRODUCT_T1,
        &filing_for(&Filed::T1 { tax_year }),
        already_filed,
        now,
    );
    let standing = freshet_license::standing(licence.issued_unix, licence.expires_unix, now);

    LicenceView {
        present: true,
        key: freshet_license::LicenceKey::parse(&licence.key)
            .ok()
            .map(|k| k.formatted()),
        licensee: Some(licence.licensee.clone()),
        kind: Some(licence.kind.label().to_string()),
        coverage: Some(licence.coverage.describe()),
        allowance: Some(licence.allowance.describe()),
        returns_left: licence.allowance.remaining(already_filed),
        returns_filed: already_filed,
        entitled: entitlement.granted(),
        explanation: entitlement.explain(),
        dev_licences_compiled_in: DEV_LICENCES_COMPILED_IN,
        expires_unix: licence.expires_unix,
        standing_note: freshet_license::standing::describe(standing),
        // A licence inside its grace period or past it has a real consequence
        // attached. One that merely has a date approaching does not, and
        // dressing the two the same teaches people to ignore both.
        standing_urgent: matches!(
            standing,
            freshet_license::Standing::InGrace { .. } | freshet_license::Standing::Ended
        ),
    }
}

fn stored_licence(state: &State<'_, AppState>) -> Option<String> {
    state.settings.lock().unwrap().licence.clone()
}

/// How many returns have been filed under the current licence.
///
/// Read from the persisted ledger keyed by licence key, so switching licences
/// does not inherit another licence's count and reinstalling does not silently
/// carry one over.
///
/// This number is advisory. It is what the app shows and what it checks before
/// attempting a transmission, but for a counted licence the binding count comes
/// from the issuer at transmission time — a count kept on the customer's own
/// machine can be reset, and pretending otherwise would be security theatre.
fn returns_filed(state: &State<'_, AppState>) -> u32 {
    let settings = state.settings.lock().unwrap();

    let Some(token) = settings.licence.as_deref() else {
        return 0;
    };

    // Straight from the signed payload rather than a separately stored key, so
    // the count can never be attributed to the wrong licence.
    let Ok(licence) = freshet_license::verify(token) else {
        return 0;
    };

    settings.filings.get(&licence.key).copied().unwrap_or(0)
}

#[tauri::command]
pub fn licence_status(state: State<'_, AppState>, tax_year: u16) -> LicenceView {
    match stored_licence(&state) {
        Some(token) => describe(&token, tax_year, returns_filed(&state)),
        None => no_licence(
            "No licence. You can prepare a complete return without one; filing needs a licence key.",
        ),
    }
}

/// Turn whatever the user supplied into a signed licence.
///
/// This function is the entire network policy for licensing, which is why it is
/// pure and separately tested. `verify_online` is the *only* thing that permits
/// a request to leave the machine, and it is false unless the user ticked a box
/// this time — it is a per-attempt argument, not a stored preference, so there
/// is no way for consent given once to quietly persist.
///
/// The order matters. A self-contained licence and a built-in licence are both
/// resolved before the online branch is even considered, so those paths cannot
/// reach the network even when the user has permitted it.
fn resolve_licence(input: &str, verify_online: bool) -> Result<String, LicenceError> {
    let credential = Credential::classify(input)?;

    let key = match credential {
        // Already a licence: this is the whole of it. No server exists as far
        // as this branch is concerned.
        Credential::Licence(token) => return Ok(token),
        Credential::Key(key) => key,
    };

    #[cfg(feature = "dev-licences")]
    if let Some(built) = freshet_license::dev::find(&key) {
        return Ok(built.token);
    }

    if !verify_online {
        return Err(LicenceError::KeyNeedsActivation);
    }

    freshet_license::WebActivation {
        base_url: "https://freshettax.ca".into(),
    }
    .activate(&key)
}

/// Install a licence.
///
/// Accepts either form without being told which: a signed licence pasted from
/// the purchase email, or a licence key. Only the key form can involve the
/// network, and only when `verify_online` is set.
#[tauri::command]
pub fn install_licence(
    state: State<'_, AppState>,
    input: String,
    verify_online: bool,
    tax_year: u16,
) -> Result<LicenceView, String> {
    let token = resolve_licence(&input, verify_online).map_err(|e| e.to_string())?;

    // Never store something that does not verify.
    freshet_license::verify(&token).map_err(|e| e.to_string())?;

    state.settings.lock().unwrap().licence = Some(token.clone());
    state.save()?;

    Ok(describe(&token, tax_year, returns_filed(&state)))
}

/// Install a licence from the file it was emailed as.
///
/// Offline by construction: a file cannot be a key that needs exchanging, so
/// there is no `verify_online` argument to get wrong.
#[tauri::command]
pub fn install_licence_file(
    state: State<'_, AppState>,
    path: String,
    tax_year: u16,
) -> Result<LicenceView, String> {
    let contents = std::fs::read_to_string(&path)
        .map_err(|e| format!("could not read {path}: {e}"))?;

    let token = resolve_licence(&contents, false).map_err(|e| e.to_string())?;
    freshet_license::verify(&token).map_err(|e| e.to_string())?;

    state.settings.lock().unwrap().licence = Some(token.clone());
    state.save()?;

    Ok(describe(&token, tax_year, returns_filed(&state)))
}

#[tauri::command]
pub fn remove_licence(state: State<'_, AppState>, tax_year: u16) -> Result<LicenceView, String> {
    state.settings.lock().unwrap().licence = None;
    state.save()?;
    Ok(licence_status(state, tax_year))
}

// -- the filing gate ------------------------------------------------------

/// Everything standing between a prepared return and transmitting it.
///
/// Three locks, deliberately independent and separately reported. "You cannot
/// file" is useless; "your licence covers 2025, not 2026" is actionable, and a
/// person hitting a paywall deserves to know it is a paywall rather than
/// suspecting their return is broken.
#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct FilingGate {
    pub can_file: bool,
    /// Our tax data has been verified against its sources.
    pub data_verified: bool,
    /// The return has no errors of its own.
    pub return_sound: bool,
    /// CRA has certified this product for this tax year and jurisdiction.
    pub year_certified: bool,
    /// Whether this jurisdiction is even inside the certification application.
    ///
    /// Distinct from `year_certified` so the app can tell someone "not yet"
    /// rather than "not ever, in this release". Those deserve different wording.
    pub in_scope: bool,
    /// A licence permits filing this year.
    pub licensed: bool,
    /// One line per closed lock, in the words to show.
    pub blocked_by: Vec<String>,
}

/// Pure so it can be tested without a running app.
fn evaluate_gate(
    a: &Assessment,
    filed: Filed,
    province: &str,
    licence_token: Option<&str>,
    already_filed: u32,
) -> FilingGate {
    let tax_year = filed.tax_year();
    let data_verified = a.warnings.is_empty();
    let return_sound = !a.has_errors();
    let in_scope = freshet_taxdata::in_certification_scope(province);
    let year_certified = freshet_taxdata::is_certified(tax_year, province);

    let (licensed, licence_reason) = match licence_token {
        None => (
            false,
            Some("Filing needs a licence key. Preparing this return is free.".to_string()),
        ),
        Some(token) => match freshet_license::verify(token) {
            Err(e) => (false, Some(e.to_string())),
            Ok(l) => {
                let e = l.check(
                    filed.product(),
                    &filing_for(&filed),
                    already_filed,
                    freshet_store::now_unix(),
                );
                (e.granted(), (!e.granted()).then(|| e.explain()))
            }
        },
    };

    let mut blocked_by = Vec::new();
    if !data_verified {
        blocked_by.push(format!(
            "{} tax parameters have not been verified against their sources.",
            a.warnings.len()
        ));
    }
    if !return_sound {
        blocked_by.push("The return has errors that must be fixed.".to_string());
    }
    if !year_certified {
        // Two different situations, and conflating them wastes someone's time:
        // one resolves when the certification letter arrives, the other does
        // not resolve in this release at all.
        blocked_by.push(if in_scope {
            format!("Freshet is not yet CRA-certified to file {tax_year}.")
        } else {
            format!(
                "Freshet is not certified to file {} returns. This release covers                  Ontario only; other jurisdictions can be prepared and printed,                  but not filed.",
                province.to_uppercase()
            )
        });
    }
    if let Some(reason) = licence_reason {
        blocked_by.push(reason);
    }

    FilingGate {
        can_file: data_verified && return_sound && year_certified && licensed,
        data_verified,
        return_sound,
        year_certified,
        in_scope,
        licensed,
        blocked_by,
    }
}

#[tauri::command]
pub fn filing_gate(state: State<'_, AppState>, input: ComputeInput) -> Result<FilingGate, String> {
    let a = assess(&input)?;
    let token = stored_licence(&state);
    let filed = returns_filed(&state);

    Ok(evaluate_gate(&a, Filed::T1 { tax_year: input.tax_year }, &input.province, token.as_deref(), filed))
}

// -- capital cost allowance planner ---------------------------------------

const CCA_LIMIT_CLAIM: &str = "cca.limit_claim";
const CCA_CLAIMED: &str = "cca.claimed";

#[derive(Debug, Serialize)]
pub struct CcaPoint {
    pub claim: String,
    pub total_tax: String,
    pub refundable_credits: String,
    /// Positive means money back.
    pub refund: String,
}

#[derive(Debug, Serialize)]
pub struct CcaPlan {
    pub maximum: String,
    pub points: Vec<CcaPoint>,
    /// The claim that leaves the most in your pocket this year.
    pub best_claim: String,
    pub best_refund: String,
    /// How much would stay in the pool for later years at that claim.
    pub banked_at_best: String,
    /// The smallest claim that already drives tax to zero. Beyond it, further
    /// CCA buys no tax saving this year — though it may still raise
    /// income-tested benefits, which is why it is reported rather than assumed
    /// to be the answer.
    pub tax_zero_at: Option<String>,
}

/// Model what different capital cost allowance claims are worth.
///
/// CCA is discretionary, and the trade-off runs both ways. Claiming more cuts
/// taxable income, but once tax is already nil the deduction buys nothing this
/// year — while *also* cutting net income, which raises income-tested credits
/// like the Workers Benefit and CARE. Only running the whole return at each
/// level settles it.
#[tauri::command]
pub fn cca_plan(input: ComputeInput) -> Result<CcaPlan, String> {
    const STEPS: u32 = 20;

    let maximum = line(&assess(&input)?, "fed.cca_maximum");
    if maximum <= Decimal::ZERO {
        return Ok(CcaPlan {
            maximum: dp2(Decimal::ZERO),
            points: Vec::new(),
            best_claim: dp2(Decimal::ZERO),
            best_refund: dp2(Decimal::ZERO),
            banked_at_best: dp2(Decimal::ZERO),
            tax_zero_at: None,
        });
    }

    let at = |claim: Decimal| -> Result<(Decimal, Decimal, Decimal), String> {
        let mut probe = input.clone();
        probe.facts.insert(CCA_LIMIT_CLAIM.into(), "1".into());
        probe.facts.insert(CCA_CLAIMED.into(), claim.to_string());

        let a = assess(&probe)?;
        Ok((
            line(&a, "summary.total_tax"),
            line(&a, "summary.refundable_credits"),
            line(&a, "summary.balance"),
        ))
    };

    let step = (maximum / Decimal::from(STEPS)).round_dp(2);
    let mut points = Vec::new();
    let mut best = (Decimal::ZERO, Decimal::MAX);
    let mut tax_zero_at = None;

    for i in 0..=STEPS {
        let claim = if i == STEPS {
            maximum
        } else {
            (step * Decimal::from(i)).round_dp(2)
        };

        let (tax, credits, balance) = at(claim)?;

        if balance < best.1 {
            best = (claim, balance);
        }
        if tax_zero_at.is_none() && tax.is_zero() {
            tax_zero_at = Some(claim);
        }

        points.push(CcaPoint {
            claim: dp2(claim),
            total_tax: dp2(tax),
            refundable_credits: dp2(credits),
            refund: dp2(-balance),
        });
    }

    Ok(CcaPlan {
        maximum: dp2(maximum),
        points,
        best_claim: dp2(best.0),
        best_refund: dp2(-best.1),
        banked_at_best: dp2(maximum - best.0),
        tax_zero_at: tax_zero_at.map(dp2),
    })
}

// -- Auto-fill my return --------------------------------------------------

#[derive(Debug, Serialize)]
pub struct ContributionView {
    pub slip_type: String,
    pub issuer: String,
    pub box_label: String,
    pub amount: String,
}

#[derive(Debug, Serialize)]
pub struct ProposalView {
    pub fact_key: String,
    pub description: String,
    pub total: String,
    pub from: Vec<ContributionView>,
    /// `"new"`, `"matches"`, or `"conflict"`.
    pub disposition: String,
    /// Present only for a conflict: what the user already had.
    pub current: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct RoomView {
    pub label: String,
    pub amount: String,
    pub as_of: String,
    /// The caution that must be shown wherever the figure is.
    pub advisory: String,
}

#[derive(Debug, Serialize)]
pub struct UnmappedView {
    pub slip_type: String,
    pub issuer: String,
    pub box_label: String,
    pub description: String,
    pub amount: String,
}

#[derive(Debug, Serialize)]
pub struct ImportPreview {
    pub source_label: String,
    pub slip_count: usize,
    pub proposals: Vec<ProposalView>,
    pub rooms: Vec<RoomView>,
    pub unmapped: Vec<UnmappedView>,
}

fn source_for(name: &str, tax_year: u16) -> Box<dyn SlipSource> {
    match name {
        "sample" => Box::new(FixtureSource),
        _ => Box::new(CraAutofill { tax_year }),
    }
}

/// Fetch from CRA (or the sample source) and reconcile against the return.
///
/// Nothing is written here. The result is a set of proposals the user decides
/// on, because CRA is explicit that Auto-fill does not move responsibility off
/// the filer.
#[tauri::command]
pub fn autofill_import(
    state: State<'_, AppState>,
    input: ComputeInput,
    source: String,
) -> Result<ImportPreview, String> {
    let data = source_for(&source, input.tax_year)
        .fetch(input.tax_year)
        .map_err(|e| e.to_string())?;

    let proposals = reconcile(&data, &input.facts);

    let preview = ImportPreview {
        source_label: data.source_label.clone(),
        slip_count: data.slip_count(),

        proposals: proposals
            .iter()
            .map(|p| {
                let (disposition, current) = match &p.disposition {
                    Disposition::New => ("new", None),
                    Disposition::Matches => ("matches", None),
                    Disposition::Conflict { current } => ("conflict", Some(dp2(*current))),
                };

                ProposalView {
                    fact_key: p.fact_key.clone(),
                    description: p.description.clone(),
                    total: dp2(p.total),
                    from: p
                        .from
                        .iter()
                        .map(|c| ContributionView {
                            slip_type: c.slip_type.clone(),
                            issuer: c.issuer.clone(),
                            box_label: c.box_label.clone(),
                            amount: dp2(c.amount),
                        })
                        .collect(),
                    disposition: disposition.to_string(),
                    current,
                }
            })
            .collect(),

        rooms: data
            .rooms
            .iter()
            .map(|r| RoomView {
                label: r.kind.label().to_string(),
                amount: dp2(r.amount),
                as_of: r.as_of.clone(),
                advisory: r.advisory(),
            })
            .collect(),

        unmapped: data
            .slips
            .iter()
            .flat_map(|s| {
                s.boxes
                    .iter()
                    .filter(|b| b.fact_key.is_none())
                    .map(move |b| UnmappedView {
                        slip_type: s.slip_type.clone(),
                        issuer: s.issuer.clone(),
                        box_label: b.box_label.clone(),
                        description: b.description.clone(),
                        amount: dp2(b.amount),
                    })
            })
            .collect(),
    };

    *state.last_import.lock().unwrap() = Some(data);
    Ok(preview)
}

/// Apply the accepted proposals, returning the updated fact map.
///
/// Uses the cached response rather than calling CRA again.
#[tauri::command]
pub fn autofill_apply(
    state: State<'_, AppState>,
    input: ComputeInput,
    accept: Vec<String>,
) -> Result<BTreeMap<String, String>, String> {
    let guard = state.last_import.lock().unwrap();
    let data = guard
        .as_ref()
        .ok_or("there is no import to apply — run the import again")?;

    let proposals = reconcile(data, &input.facts);
    Ok(apply(&input.facts, &proposals, &accept))
}

// -- persistence ----------------------------------------------------------

#[derive(Debug, Serialize)]
pub struct ReturnSummary {
    pub id: String,
    pub label: String,
    pub tax_year: u16,
    pub province: String,
    pub updated_unix: i64,
}

#[derive(Debug, Serialize)]
pub struct StoredReturnView {
    pub id: String,
    pub label: String,
    pub tax_year: u16,
    pub province: String,
    pub facts: BTreeMap<String, String>,
}

#[derive(Debug, Serialize)]
pub struct StorageStatus {
    pub available: bool,
    pub error: Option<String>,
    pub path: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct SaveInput {
    /// `None` creates a new return; `Some` updates in place.
    pub id: Option<String>,
    pub label: String,
    pub tax_year: u16,
    pub province: String,
    pub facts: BTreeMap<String, String>,
}

fn with_vault<T>(
    state: &State<'_, AppState>,
    f: impl FnOnce(&mut VaultState) -> Result<T, String>,
) -> Result<T, String> {
    let mut guard = state.vault.lock().unwrap();

    let vault = guard.as_mut().ok_or_else(|| {
        state
            .vault_error
            .clone()
            .unwrap_or_else(|| "encrypted storage is unavailable".to_string())
    })?;

    f(vault)
}

fn summarize(vault: &VaultState) -> Vec<ReturnSummary> {
    vault
        .vault
        .by_recency()
        .into_iter()
        .map(|r| ReturnSummary {
            id: r.id.clone(),
            label: r.label.clone(),
            tax_year: r.tax_year,
            province: r.province.clone(),
            updated_unix: r.updated_unix,
        })
        .collect()
}

#[tauri::command]
pub fn storage_status(state: State<'_, AppState>) -> StorageStatus {
    let guard = state.vault.lock().unwrap();

    StorageStatus {
        available: guard.is_some(),
        error: state.vault_error.clone(),
        path: guard
            .as_ref()
            .map(|v| v.store.path().display().to_string()),
    }
}

#[tauri::command]
pub fn list_returns(state: State<'_, AppState>) -> Result<Vec<ReturnSummary>, String> {
    with_vault(&state, |v| Ok(summarize(v)))
}

#[tauri::command]
pub fn save_return(
    state: State<'_, AppState>,
    input: SaveInput,
) -> Result<ReturnSummary, String> {
    with_vault(&state, |v| {
        let id = v.vault.upsert(
            input.id,
            input.label,
            input.tax_year,
            input.province,
            input.facts,
        );

        // Write through on every save. A tax session is minutes of typing that
        // nobody wants to repeat, and the payload is small enough that batching
        // would buy nothing but risk.
        v.flush()?;

        let saved = v.vault.get(&id).ok_or("the return vanished after saving")?;
        Ok(ReturnSummary {
            id: saved.id.clone(),
            label: saved.label.clone(),
            tax_year: saved.tax_year,
            province: saved.province.clone(),
            updated_unix: saved.updated_unix,
        })
    })
}

#[tauri::command]
pub fn load_return(state: State<'_, AppState>, id: String) -> Result<StoredReturnView, String> {
    with_vault(&state, |v| {
        let r = v
            .vault
            .get(&id)
            .ok_or("that return is no longer in the vault")?;

        Ok(StoredReturnView {
            id: r.id.clone(),
            label: r.label.clone(),
            tax_year: r.tax_year,
            province: r.province.clone(),
            facts: r.facts.clone(),
        })
    })
}

#[tauri::command]
pub fn delete_return(
    state: State<'_, AppState>,
    id: String,
) -> Result<Vec<ReturnSummary>, String> {
    with_vault(&state, |v| {
        if !v.vault.remove(&id) {
            return Err("that return is no longer in the vault".into());
        }
        v.flush()?;
        Ok(summarize(v))
    })
}

// -- the T2 ----------------------------------------------------------------

#[derive(Debug, Clone, Deserialize)]
pub struct T2Input {
    /// The fiscal period, as `YYYY-MM-DD`.
    ///
    /// Dates rather than a tax year, because a corporation does not have one:
    /// its year is whatever falls between one year-end and the next.
    pub period_start: String,
    pub period_end: String,
    pub province: String,
    pub facts: BTreeMap<String, String>,
}

fn parse_date(raw: &str) -> Result<Date, String> {
    let parts: Vec<&str> = raw.trim().split('-').collect();
    if parts.len() != 3 {
        return Err(format!("{raw} is not a date in YYYY-MM-DD form"));
    }

    let num = |s: &str, what: &str| {
        s.parse::<i64>()
            .map_err(|_| format!("{raw} has a {what} that is not a number"))
    };

    Date::new(
        num(parts[0], "year")? as i32,
        num(parts[1], "month")? as u32,
        num(parts[2], "day")? as u32,
    )
    .map_err(|e| e.to_string())
}

impl T2Input {
    fn period(&self) -> Result<Period, String> {
        Period::new(parse_date(&self.period_start)?, parse_date(&self.period_end)?)
            .map_err(|e| e.to_string())
    }
}

fn assess_t2(input: &T2Input) -> Result<(Assessment, Period), String> {
    let period = input.period()?;
    let forms = freshet_taxdata::t2_forms(&input.province).map_err(|e| e.to_string())?;

    let mut facts = FactSet::new();
    for (key, raw) in &input.facts {
        if let Some(value) = parse_money(raw) {
            facts.set(key.clone(), value);
        }
    }

    // A period crossing a calendar boundary draws on both years, so a rate
    // that moved between them can be apportioned by days. The engine refuses
    // to guess from one year, which is why this branches rather than always
    // taking the closing year.
    let assessment = if period.straddles() {
        let packs = freshet_taxdata::t2_period_packs(period, &input.province)
            .map_err(|e| e.to_string())?;
        freshet_engine::compute_across(&forms, &packs, &facts).map_err(|e| e.to_string())?
    } else {
        let packs = freshet_taxdata::t2_packs(period.end.year as u16, &input.province)
            .map_err(|e| e.to_string())?;
        freshet_engine::compute_for_period(&forms, &packs, &facts, period)
            .map_err(|e| e.to_string())?
    };

    Ok((assessment, period))
}

#[derive(Debug, Serialize)]
pub struct T2View {
    pub period_days: i64,
    pub is_short_year: bool,
    pub straddles: bool,
    pub accounting_income: String,
    pub net_income_for_tax: String,
    pub taxable_income: String,
    pub small_business_deduction: String,
    pub federal_tax: String,
    pub provincial_tax: String,
    pub total_tax: String,
    pub balance: String,
    pub lines: Vec<LineView>,
    pub diagnostics: Vec<DiagnosticView>,
    pub has_errors: bool,
    pub filable: bool,
}

#[tauri::command]
pub fn compute_t2(input: T2Input) -> Result<T2View, String> {
    let (a, period) = assess_t2(&input)?;

    Ok(T2View {
        period_days: period.days(),
        is_short_year: period.is_short(),
        straddles: period.straddles(),
        accounting_income: dp2(line(&a, "gifi.9999")),
        net_income_for_tax: dp2(line(&a, "t2.300")),
        taxable_income: dp2(line(&a, "t2.360")),
        small_business_deduction: dp2(line(&a, "t2.430")),
        federal_tax: dp2(line(&a, "t2.700")),
        provincial_tax: dp2(line(&a, "prov.tax")),
        total_tax: dp2(line(&a, "summary.total_tax")),
        balance: dp2(line(&a, "summary.balance")),
        // The audit trail, which carries labels and notes alongside the
        // values, in the order the engine resolved them.
        lines: a
            .audit
            .iter()
            .map(|e| LineView {
                id: e.id.clone(),
                label: e.label.clone(),
                value: dp2(e.value),
                note: e.note.clone(),
            })
            .collect(),
        diagnostics: a
            .diagnostics
            .iter()
            .map(|x| DiagnosticView {
                id: x.id.clone(),
                severity: severity_str(x.severity).to_string(),
                message: x.message.clone(),
                help: x.help.clone(),
            })
            .collect(),
        has_errors: a.has_errors(),
        filable: a.is_filable(),
    })
}

#[tauri::command]
pub fn t2_filing_gate(
    state: State<'_, AppState>,
    input: T2Input,
) -> Result<FilingGate, String> {
    let (a, period) = assess_t2(&input)?;
    let token = stored_licence(&state);

    Ok(evaluate_gate(
        &a,
        Filed::T2 { period },
        &input.province,
        token.as_deref(),
        returns_filed(&state),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn d(s: &str) -> Decimal {
        Decimal::from_str_exact(s).unwrap()
    }

    fn input_for(tax_year: u16, facts: &[(&str, &str)]) -> ComputeInput {
        ComputeInput {
            tax_year,
            province: "on".into(),
            facts: facts
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
        }
    }

    fn input(facts: &[(&str, &str)]) -> ComputeInput {
        ComputeInput {
            tax_year: 2025,
            province: "on".into(),
            facts: facts
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
        }
    }

    /// The same case as the engine's golden vector, taken through the command
    /// layer, so a mistake in the view mapping cannot hide behind a correct
    /// engine.
    #[test]
    fn the_salaried_case_survives_the_bridge() {
        let view = compute_return(input(&[
            ("t4.employment_income", "85000"),
            ("t4.cpp_contributions", "4034.10"),
            ("t4.cpp2_contributions", "396.00"),
            ("t4.ei_premiums", "1077.48"),
            ("t4.income_tax_deducted", "16000"),
            ("rrsp.deduction_claimed", "5000"),
        ]))
        .unwrap();

        assert_eq!(view.summary.total_income, "85000.00");
        assert_eq!(view.summary.taxable_income, "78926.00");
        assert_eq!(view.summary.federal_tax, "9542.46");
        // Ontario tax now carries the $750 health premium on top.
        assert_eq!(view.summary.provincial_tax, "4935.78");
        assert_eq!(view.summary.total_tax, "14478.24");
        assert_eq!(view.summary.refund, "1521.76");
        assert!(view.summary.is_refund);

        // Second federal bracket (20.5%) plus second Ontario bracket (9.15%),
        // measured rather than assumed.
        assert_eq!(view.summary.marginal_rate, "29.65");

        // The verification gate must survive the bridge too.
        assert!(!view.filable);
        assert!(!view.warnings.is_empty());
    }

    #[test]
    fn amounts_are_accepted_the_way_people_actually_type_them() {
        for typed in ["85000", "$85,000.00", "85 000", "85,000"] {
            let view = compute_return(input(&[("t4.employment_income", typed)])).unwrap();
            assert_eq!(view.summary.total_income, "85000.00", "rejected {typed:?}");
        }
    }

    #[test]
    fn a_blank_form_computes_zero_rather_than_failing() {
        let view = compute_return(input(&[])).unwrap();

        assert_eq!(view.summary.total_tax, "0.00");
        assert_eq!(view.summary.average_rate, "0.00");
        assert!(!view.summary.is_refund);
    }

    // -- RRSP planner -----------------------------------------------------

    #[test]
    fn the_first_rrsp_dollars_save_at_the_marginal_rate() {
        let facts = input(&[
            ("t4.employment_income", "85000"),
            ("t4.cpp_contributions", "4034.10"),
            ("t4.cpp2_contributions", "396.00"),
            ("t4.ei_premiums", "1077.48"),
        ]);

        let plan = rrsp_plan(facts.clone(), None).unwrap();

        assert_eq!(plan.points.len(), 20);
        // Second federal bracket plus second Ontario bracket.
        assert_eq!(plan.points[0].saving_rate, "29.65");
        // Room defaults to 18% of employment income when CRA has not told us.
        assert_eq!(plan.room, "15300.00");
    }

    #[test]
    fn saving_never_goes_backwards_as_the_contribution_grows() {
        let plan = rrsp_plan(
            input(&[("t4.employment_income", "250000")]),
            Some("100000".into()),
        )
        .unwrap();

        let saved: Vec<Decimal> = plan
            .points
            .iter()
            .map(|p| Decimal::from_str_exact(&p.tax_saved).unwrap())
            .collect();

        for pair in saved.windows(2) {
            assert!(
                pair[1] >= pair[0],
                "contributing more saved less: {} then {}",
                pair[0],
                pair[1]
            );
        }
    }

    #[test]
    fn the_saving_rate_falls_as_the_contribution_crosses_bracket_edges() {
        // A high earner contributing a lot drops through brackets, so the last
        // dollar cannot be worth as much as the first. This is exactly what a
        // flat bracket-rate estimate gets wrong.
        let plan = rrsp_plan(
            input(&[("t4.employment_income", "250000")]),
            Some("150000".into()),
        )
        .unwrap();

        let first = Decimal::from_str_exact(&plan.points[0].saving_rate).unwrap();
        let last = Decimal::from_str_exact(&plan.points.last().unwrap().saving_rate).unwrap();

        assert!(first > last, "rate did not fall: {first} then {last}");
    }

    #[test]
    fn the_sweet_spot_is_the_last_contribution_earning_the_top_rate() {
        let plan = rrsp_plan(
            input(&[("t4.employment_income", "250000")]),
            Some("150000".into()),
        )
        .unwrap();

        let spot = plan.sweet_spot.expect("a sweet spot should exist");
        assert!(plan.sweet_spot_saving.is_some());
        // It must be a real contribution, not the whole room.
        assert!(Decimal::from_str_exact(&spot).unwrap() < d("150000"));
    }

    #[test]
    fn break_even_actually_clears_the_balance() {
        let facts = input(&[("t4.employment_income", "85000")]);
        let plan = rrsp_plan(facts.clone(), Some("200000".into())).unwrap();

        let amount = plan.to_break_even.expect("break-even should be reachable");

        // Verify by recomputing rather than trusting the search.
        let mut checked = facts.clone();
        checked.facts.insert(RRSP_KEY.into(), amount.clone());
        let view = compute_return(checked).unwrap();

        assert!(!view.summary.is_refund || view.summary.refund == "0.00");
        assert_eq!(view.summary.total_tax, "0.00");
    }

    #[test]
    fn there_is_no_break_even_when_nothing_is_owing() {
        let plan = rrsp_plan(
            input(&[
                ("t4.employment_income", "85000"),
                ("t4.income_tax_deducted", "30000"),
            ]),
            None,
        )
        .unwrap();

        assert!(plan.to_break_even.is_none());
    }

    #[test]
    fn no_income_produces_an_empty_plan_rather_than_an_error() {
        let plan = rrsp_plan(input(&[]), None).unwrap();

        assert!(plan.points.is_empty());
        assert_eq!(plan.room, "0.00");
    }

    /// Being able to compute a year is not permission to file it. CRA certifies
    /// per tax year, so the product must refuse to transmit a year it does not
    /// hold a certification for — even one it models perfectly.
    #[test]
    fn the_cca_planner_sweeps_from_nothing_to_the_maximum() {
        let plan = cca_plan(input(&[
            ("self_employment.gross", "50000"),
            ("cca.class8.opening_ucc", "10000"),
        ]))
        .unwrap();

        assert_eq!(plan.maximum, "2000.00");
        assert_eq!(plan.points.len(), 21);
        assert_eq!(plan.points[0].claim, "0.00");
        assert_eq!(plan.points.last().unwrap().claim, "2000.00");

        // Whatever it recommends, the arithmetic has to agree with itself.
        let best = Decimal::from_str_exact(&plan.best_claim).unwrap();
        let banked = Decimal::from_str_exact(&plan.banked_at_best).unwrap();
        assert_eq!(best + banked, d("2000.00"));
    }

    #[test]
    fn claiming_more_never_leaves_you_worse_off_in_the_year() {
        // Not a tax truth in general, but it must hold here: the deduction
        // lowers taxable income and lowers net income, and both directions help
        // in the same year.
        let plan = cca_plan(input(&[
            ("self_employment.gross", "50000"),
            ("cca.class8.opening_ucc", "10000"),
        ]))
        .unwrap();

        let refunds: Vec<Decimal> = plan
            .points
            .iter()
            .map(|p| Decimal::from_str_exact(&p.refund).unwrap())
            .collect();

        for pair in refunds.windows(2) {
            assert!(pair[1] >= pair[0], "claiming more cost money: {pair:?}");
        }
    }

    #[test]
    fn a_return_with_no_depreciable_assets_gets_an_empty_plan() {
        let plan = cca_plan(input(&[("t4.employment_income", "60000")])).unwrap();

        assert_eq!(plan.maximum, "0.00");
        assert!(plan.points.is_empty());
        assert!(plan.tax_zero_at.is_none());
    }

    // -- the filing gate --------------------------------------------------

    #[test]
    fn every_lock_is_reported_separately_rather_than_a_flat_refusal() {
        // 2026, whose Ontario amounts are still unverified, so all three of the
        // non-return locks are shut at once.
        let a = assess(&input_for(2026, &[("t4.employment_income", "60000")])).unwrap();
        let gate = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", None, 0);

        assert!(!gate.can_file);
        // Nothing about this return is wrong; it is the surrounding state.
        assert!(gate.return_sound);
        assert!(!gate.data_verified);
        assert!(!gate.year_certified);
        assert!(!gate.licensed);
        assert_eq!(gate.blocked_by.len(), 3);
    }

    /// The locks move independently. 2025's data is fully verified while 2026's
    /// is not, and neither year is certified — so the data lock opens on its own
    /// without dragging the others with it.
    #[test]
    fn the_data_lock_opens_for_a_verified_year_and_not_for_an_unverified_one() {
        let facts = [("t4.employment_income", "60000")];

        let verified = assess(&input_for(2025, &facts)).unwrap();
        let unverified = assess(&input_for(2026, &facts)).unwrap();

        assert!(evaluate_gate(&verified, Filed::T1 { tax_year: 2025 }, "on", None, 0).data_verified);
        assert!(!evaluate_gate(&unverified, Filed::T1 { tax_year: 2026 }, "on", None, 0).data_verified);

        // Verified data is still not permission to file.
        assert!(!evaluate_gate(&verified, Filed::T1 { tax_year: 2025 }, "on", None, 0).can_file);
    }

    /// Ontario is inside the certification application and the other twelve are
    /// not. Both are blocked today, but for reasons that resolve differently —
    /// one when CRA sends a letter, the other not in this release at all.
    #[test]
    fn a_jurisdiction_outside_the_application_is_told_so_plainly() {
        let a = assess(&input_for(2026, &[("t4.employment_income", "60000")])).unwrap();

        let ontario = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", None, 0);
        let alberta = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "ab", None, 0);

        assert!(ontario.in_scope, "Ontario is the certification target");
        assert!(!alberta.in_scope);

        // Neither can file, but the wording differs.
        assert!(!ontario.can_file && !alberta.can_file);
        assert!(ontario.blocked_by.iter().any(|b| b.contains("not yet CRA-certified")));
        assert!(alberta
            .blocked_by
            .iter()
            .any(|b| b.contains("Ontario only") && b.contains("prepared and printed")));
    }

    /// Narrowing the application must not narrow what the software computes.
    /// An Albertan can still prepare, check and print their return; they simply
    /// cannot transmit it from this release.
    #[test]
    fn narrowing_certification_does_not_stop_a_return_being_prepared() {
        let a = assess(&input_for(2025, &[("t4.employment_income", "60000")])).unwrap();

        assert_eq!(a.get("fed.15000"), Some(Decimal::from(60_000)));
        assert!(!evaluate_gate(&a, Filed::T1 { tax_year: 2025 }, "ab", None, 0).can_file);
    }

    /// A person hitting a paywall should be told it is a paywall, not left
    /// wondering whether their return is broken.
    #[test]
    fn a_missing_licence_says_preparing_is_free() {
        let a = assess(&input(&[("t4.employment_income", "60000")])).unwrap();
        let gate = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", None, 0);

        assert!(gate
            .blocked_by
            .iter()
            .any(|b| b.contains("licence key") && b.contains("free")));
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_development_licence_opens_the_licence_lock_and_no_other() {
        let token = freshet_license::dev::licences()
            .into_iter()
            .next()
            .unwrap()
            .token;

        let a = assess(&input_for(2026, &[("t4.employment_income", "60000")])).unwrap();
        let gate = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(&token), 0);

        assert!(gate.licensed, "the development licence did not verify");
        // It grants a licence, not a certification and not verified data.
        assert!(!gate.can_file);
        assert!(!gate.year_certified);
        assert!(!gate.data_verified);
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_forged_licence_does_not_open_the_lock() {
        let a = assess(&input(&[("t4.employment_income", "60000")])).unwrap();

        for bogus in ["", "not-a-licence", "AAAA.BBBB"] {
            let gate = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(bogus), 0);
            assert!(!gate.licensed, "accepted {bogus:?}");
        }
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn exhausting_the_return_allowance_closes_the_licence_lock() {
        let built = freshet_license::dev::licences().into_iter().next().unwrap();
        let a = assess(&input(&[("t4.employment_income", "60000")])).unwrap();

        let fresh = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(&built.token), 0);
        let spent = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(&built.token), built.licence.allowance.remaining(0).expect("the built-in licence is counted"));

        assert!(fresh.licensed);
        assert!(!spent.licensed);
        assert!(spent.blocked_by.iter().any(|b| b.contains("all been filed")));
    }

    // -- the network policy ------------------------------------------------
    //
    // These are the tests that make "offline unless you ask" a property of the
    // build rather than a claim in a document. `WebActivation` is a stub that
    // always fails, so any path that reaches it is visible as an error naming
    // the activation service — which makes its *absence* a real assertion.

    fn reached_the_network(e: &LicenceError) -> bool {
        matches!(
            e,
            LicenceError::ActivationUnavailable
                | LicenceError::Unreachable(_)
                | LicenceError::Rejected(_)
        )
    }

    #[test]
    fn a_pasted_licence_never_reaches_the_network() {
        // Deliberately a licence that will not verify. Even so, resolution must
        // finish locally: an invalid licence is a local rejection, never a
        // reason to go and ask a server about it.
        let out = resolve_licence("bm90LWEtbGljZW5jZQ.c2ln", false).unwrap();
        assert_eq!(out, "bm90LWEtbGljZW5jZQ.c2ln");

        assert!(freshet_license::verify(&out).is_err());
    }

    #[test]
    fn an_unknown_key_offline_explains_itself_instead_of_contacting_anyone() {
        let key = freshet_license::LicenceKey::from_payload("ZZZZZZZZZZZZZZZZ").unwrap();
        let e = resolve_licence(&key.formatted(), false).unwrap_err();

        assert_eq!(e, LicenceError::KeyNeedsActivation);
        assert!(!reached_the_network(&e));

        let said = e.to_string();
        assert!(said.contains("does not contact any server"), "{said}");
        assert!(said.contains("purchase email"), "{said}");
    }

    #[test]
    fn only_ticking_the_box_permits_a_request_to_leave() {
        let key = freshet_license::LicenceKey::from_payload("ZZZZZZZZZZZZZZZZ").unwrap();

        let offline = resolve_licence(&key.formatted(), false).unwrap_err();
        let online = resolve_licence(&key.formatted(), true).unwrap_err();

        assert!(!reached_the_network(&offline));
        assert!(
            reached_the_network(&online),
            "opting in did not reach activation: {online}"
        );
    }

    /// The point of the built-in licences is that certification and development
    /// never wait on a purchase flow. Being asked to opt into a network call
    /// would defeat that, so they must resolve before the online branch exists.
    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_built_in_licence_resolves_offline_without_opting_in() {
        for built in freshet_license::dev::licences() {
            let key = freshet_license::LicenceKey::parse(&built.licence.key).unwrap();

            let token = resolve_licence(&key.formatted(), false)
                .unwrap_or_else(|e| panic!("{} needed the network: {e}", key.formatted()));

            assert_eq!(token, built.token);
            assert!(freshet_license::verify(&token).is_ok());
        }
    }

    // -- expiry, from the user's side --------------------------------------

    #[cfg(feature = "dev-licences")]
    fn expiring_at(expires: i64) -> String {
        let built = freshet_license::dev::licences().into_iter().next().unwrap();

        let mut licence = built.licence.clone();
        licence.expires_unix = Some(expires);

        freshet_license::sign(&licence, &freshet_license::dev::signing_key()).unwrap()
    }

    /// The most important property in the whole licensing design.
    ///
    /// Someone whose licence lapsed still owns their tax return. If expiry ever
    /// stopped a return opening or recalculating, the product would be holding
    /// a person's own data hostage over a renewal.
    #[cfg(feature = "dev-licences")]
    #[test]
    fn an_ended_licence_never_blocks_preparing_a_return() {
        let long_ago = freshet_store::now_unix() - 10 * 365 * 24 * 60 * 60;
        let token = expiring_at(long_ago);

        let a = assess(&input(&[("t4.employment_income", "60000")])).unwrap();
        let gate = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(&token), 0);

        // Filing is closed, and nothing else is.
        assert!(!gate.licensed);
        assert_eq!(
            a.get("fed.15000"),
            Some(Decimal::from(60_000)),
            "the return stopped computing when the licence ended"
        );

        let view = describe(&token, 2026, 0);
        assert!(view.present, "an ended licence should still be shown, not hidden");
        assert!(
            view.explanation.contains("print and export"),
            "the refusal must say what still works: {}",
            view.explanation
        );
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_licence_that_lapsed_yesterday_can_still_file() {
        let yesterday = freshet_store::now_unix() - 24 * 60 * 60;
        let token = expiring_at(yesterday);

        let a = assess(&input(&[("t4.employment_income", "60000")])).unwrap();
        assert!(
            evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(&token), 0).licensed,
            "a lapse of one day must not stand between someone and a deadline"
        );

        // And it says so rather than letting them find out later.
        let view = describe(&token, 2026, 0);
        assert!(view.standing_urgent);
        assert!(view.standing_note.unwrap().contains("grace period"));
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn expiry_is_announced_well_before_it_arrives() {
        let now = freshet_store::now_unix();
        let day = 24 * 60 * 60;

        let soon = describe(&expiring_at(now + 20 * day), 2026, 0);
        assert!(soon.entitled, "a licence with 20 days left still files");
        assert!(
            soon.standing_note.is_some(),
            "20 days out, the user was told nothing"
        );
        assert!(!soon.standing_urgent, "20 days out is not an emergency");

        // Far out, it stays quiet — a countdown from day one is nagging, and
        // nagging is how warnings get ignored.
        let distant = describe(&expiring_at(now + 300 * day), 2026, 0);
        assert!(distant.standing_note.is_none());
    }

    /// The date is available from the moment a licence is installed, so the UI
    /// can show it always rather than only once it is nearly too late.
    #[cfg(feature = "dev-licences")]
    #[test]
    fn the_expiry_date_is_visible_from_the_first_day() {
        let expires = freshet_store::now_unix() + 300 * 24 * 60 * 60;
        let view = describe(&expiring_at(expires), 2026, 0);

        assert_eq!(view.expires_unix, Some(expires));
    }

    /// A professional is shown "unlimited", never a number counting down.
    #[cfg(feature = "dev-licences")]
    #[test]
    fn an_unlimited_licence_reports_no_remaining_count() {
        let built = freshet_license::dev::licences().into_iter().next().unwrap();

        let mut licence = built.licence.clone();
        licence.allowance = freshet_license::Allowance::Unlimited;
        let token =
            freshet_license::sign(&licence, &freshet_license::dev::signing_key()).unwrap();

        let view = describe(&token, 2026, 4_000);

        assert_eq!(view.returns_left, None);
        assert_eq!(view.allowance.unwrap(), "unlimited returns");
        assert!(view.entitled, "an unlimited licence cannot be exhausted");
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_counted_licence_reports_what_is_left() {
        let built = freshet_license::dev::licences().into_iter().next().unwrap();

        let mut licence = built.licence.clone();
        licence.allowance = freshet_license::Allowance::Returns(5);
        let token =
            freshet_license::sign(&licence, &freshet_license::dev::signing_key()).unwrap();

        let view = describe(&token, 2026, 2);

        assert_eq!(view.returns_left, Some(3));
        assert_eq!(view.returns_filed, 2);
        assert_eq!(view.allowance.unwrap(), "up to 5 returns");
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn the_coverage_is_described_in_words_not_a_list_of_numbers() {
        let built = freshet_license::dev::licences().into_iter().next().unwrap();
        let view = describe(&built.token, 2026, 0);

        assert_eq!(view.coverage.unwrap(), "the 2025 and 2026 tax years");
    }

    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_perpetual_licence_is_never_chased_about_expiry() {
        let built = freshet_license::dev::licences().into_iter().next().unwrap();
        let view = describe(&built.token, 2026, 0);

        assert_eq!(view.expires_unix, None);
        assert!(view.standing_note.is_none());
        assert!(!view.standing_urgent);
    }

    // -- the T2 reaches the app --------------------------------------------

    fn t2_input(start: &str, end: &str, facts: &[(&str, &str)]) -> T2Input {
        T2Input {
            period_start: start.into(),
            period_end: end.into(),
            province: "on".into(),
            facts: facts
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
        }
    }

    #[test]
    fn a_corporate_return_computes_through_the_app() {
        let got = compute_t2(t2_input(
            "2025-01-01",
            "2025-12-31",
            &[("gifi.8000", "500000"), ("t2.active_business_income", "500000")],
        ))
        .unwrap();

        assert_eq!(got.period_days, 365);
        assert!(!got.is_short_year);
        assert!(!got.straddles);
        assert!(got.small_business_deduction.parse::<f64>().unwrap() > 0.0);
    }

    /// A corporation with an off-calendar year-end goes through the
    /// period-aware path, because one year of rates cannot express a change
    /// inside the period.
    #[test]
    fn a_straddling_fiscal_year_computes_rather_than_being_refused() {
        let got = compute_t2(t2_input(
            "2025-07-01",
            "2026-06-30",
            &[("gifi.8000", "500000")],
        ))
        .unwrap();

        assert!(got.straddles);
        assert_eq!(got.period_days, 365);
    }

    #[test]
    fn a_short_first_year_is_reported_as_short() {
        let got = compute_t2(t2_input("2025-09-15", "2025-12-31", &[("gifi.8000", "100000")]))
            .unwrap();

        assert_eq!(got.period_days, 108);
        assert!(got.is_short_year);
    }

    #[test]
    fn dates_that_are_not_dates_are_refused_clearly() {
        for (start, end, expect) in [
            ("2025-02-29", "2025-12-31", "no day 29"),
            ("not-a-date", "2025-12-31", "not a number"),
            ("2025-01-01", "2024-12-31", "cannot end"),
            ("2025-01-01", "2027-01-01", "53 weeks"),
        ] {
            let e = compute_t2(t2_input(start, end, &[])).unwrap_err();
            assert!(e.contains(expect), "{start}..{end} said: {e}");
        }
    }

    /// The seam this change existed to fix. A licence for personal tax must not
    /// unlock a corporate return, and the check now compares a fiscal period
    /// against the licence rather than a calendar year the corporation does not
    /// have.
    #[cfg(feature = "dev-licences")]
    #[test]
    fn a_t1_licence_does_not_unlock_a_corporate_return() {
        let token = freshet_license::dev::licences()
            .into_iter()
            .next()
            .unwrap()
            .token;

        let a = assess(&input_for(2026, &[("t4.employment_income", "60000")])).unwrap();

        let personal = evaluate_gate(&a, Filed::T1 { tax_year: 2026 }, "on", Some(&token), 0);
        let corporate = evaluate_gate(
            &a,
            Filed::T2 {
                period: Period::calendar(2026),
            },
            "on",
            Some(&token),
            0,
        );

        assert!(personal.licensed, "the development licence covers the T1");
        assert!(
            !corporate.licensed,
            "a T1 licence unlocked a corporate return"
        );
        assert!(corporate
            .blocked_by
            .iter()
            .any(|b| b.contains("freshet-t1")));
    }

    #[test]
    fn a_typo_is_caught_before_anything_is_contacted() {
        let good = freshet_license::LicenceKey::from_payload("ZZZZZZZZZZZZZZZZ").unwrap();
        let mangled = good.formatted().replace('Z', "Y");

        // Even with the online box ticked, a key that cannot be right locally
        // is not worth a round trip.
        let e = resolve_licence(&mangled, true).unwrap_err();
        assert!(!reached_the_network(&e), "{e}");
        assert!(e.to_string().contains("typo"), "{e}");
    }

    #[test]
    fn a_year_the_product_is_not_certified_for_cannot_be_filed() {
        for year in [2025u16, 2026] {
            let mut facts = input(&[("t4.employment_income", "60000")]);
            facts.tax_year = year;

            let view = compute_return(facts).unwrap();

            assert!(!view.certified_to_file, "{year} claimed a certification");
            assert!(!view.filable);
            assert!(
                view.warnings.iter().any(|w| w.contains("not certified")),
                "the user is not told why {year} cannot be filed"
            );
        }
    }

    #[test]
    fn an_unsupported_year_is_an_error_the_ui_can_show() {
        let mut bad = input(&[]);
        bad.tax_year = 2024;

        let err = compute_return(bad).unwrap_err();
        assert!(err.contains("2024"), "unhelpful message: {err}");
    }

    #[test]
    fn every_line_reaches_the_view_with_its_label() {
        let view = compute_return(input(&[("t4.employment_income", "60000")])).unwrap();

        assert!(view.lines.len() > 15, "only {} lines", view.lines.len());
        assert!(view.lines.iter().all(|l| !l.label.is_empty()));
        assert!(view.lines.iter().any(|l| l.id == "fed.30000"));
    }
}
