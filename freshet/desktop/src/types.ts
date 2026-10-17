/** Mirrors the serde shapes in src-tauri. Keep in step with commands.rs. */

export type Provider =
  | { kind: "anthropic"; model: string }
  | { kind: "open_ai"; model: string }
  | { kind: "biber"; base_url: string; model: string }
  | { kind: "local"; base_url: string; model: string };

export interface SettingsView {
  provider: Provider | null;
  provider_label: string | null;
  has_key: boolean;
  is_remote: boolean;
  consent_granted: boolean;
}

export interface LineView {
  id: string;
  label: string;
  value: string;
  note: string | null;
}

export interface SummaryView {
  total_income: string;
  net_income: string;
  taxable_income: string;
  federal_tax: string;
  provincial_tax: string;
  total_tax: string;
  withheld: string;
  refundable_credits: string;
  refund: string;
  is_refund: boolean;
  average_rate: string;
  marginal_rate: string;
}

export type Severity = "error" | "warning" | "info";

export interface DiagnosticView {
  id: string;
  severity: Severity;
  message: string;
  help: string | null;
}

export interface ReturnView {
  tax_year: number;
  province: string;
  summary: SummaryView;
  lines: LineView[];
  warnings: string[];
  diagnostics: DiagnosticView[];
  has_errors: boolean;
  certified_to_file: boolean;
  filable: boolean;
}

export interface SpouseResultView {
  label: string;
  net_income: string;
  spouse_amount: string;
  age_amount: string;
  pension_amount: string;
  transferred_in: string;
  tuition_carryforward: string;
  total_tax: string;
  refund: string;
  is_refund: boolean;
  medical_claimed: string;
  donations_claimed: string;
}

export interface DecisionView {
  item: string;
  chose: string;
  saved: string;
  mandatory: boolean;
  why: string;
}

export interface CoupleView {
  you: SpouseResultView;
  partner: SpouseResultView;
  combined_tax: string;
  combined_refund: string;
  combined_is_refund: boolean;
  decisions: DecisionView[];
  saving_vs_worst: string;
  allocations_considered: number;
  pension_split_amount: string;
  pension_split_rate: string;
  pension_split_from: string;
  childcare_claimed_by: string;
}

export interface HouseholdInput {
  your_label: string;
  partner_label: string;
  partner_facts: Record<string, string>;
}

export interface LicenceView {
  present: boolean;
  key: string | null;
  licensee: string | null;
  kind: string | null;
  coverage: string | null;
  allowance: string | null;
  /** null for an unlimited licence — show the word, never a number. */
  returns_left: number | null;
  returns_filed: number;
  entitled: boolean;
  explanation: string;
  dev_licences_compiled_in: boolean;
  expires_unix: number | null;
  standing_note: string | null;
  standing_urgent: boolean;
}

export interface FilingGate {
  can_file: boolean;
  data_verified: boolean;
  return_sound: boolean;
  year_certified: boolean;
  in_scope: boolean;
  licensed: boolean;
  blocked_by: string[];
}

export interface CcaPoint {
  claim: string;
  total_tax: string;
  refundable_credits: string;
  refund: string;
}

export interface CcaPlan {
  maximum: string;
  points: CcaPoint[];
  best_claim: string;
  best_refund: string;
  banked_at_best: string;
  tax_zero_at: string | null;
}

export interface RrspPoint {
  contribution: string;
  tax_saved: string;
  saving_rate: string;
}

export interface RrspPlan {
  room: string;
  points: RrspPoint[];
  to_break_even: string | null;
  sweet_spot: string | null;
  sweet_spot_saving: string | null;
}

export interface ContributionView {
  slip_type: string;
  issuer: string;
  box_label: string;
  amount: string;
}

export interface ProposalView {
  fact_key: string;
  description: string;
  total: string;
  from: ContributionView[];
  disposition: "new" | "matches" | "conflict";
  current: string | null;
}

export interface RoomView {
  label: string;
  amount: string;
  as_of: string;
  advisory: string;
}

export interface UnmappedView {
  slip_type: string;
  issuer: string;
  box_label: string;
  description: string;
  amount: string;
}

export interface ImportPreview {
  source_label: string;
  slip_count: number;
  proposals: ProposalView[];
  rooms: RoomView[];
  unmapped: UnmappedView[];
}

export interface Turn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatReply {
  reply: string;
  redacted: string[];
  remote: boolean;
}

export interface ComputeInput {
  tax_year: number;
  province: string;
  facts: Record<string, string>;
}

export interface PeriodView {
  start: string;
  end: string;
}

export interface ReturnSummary {
  id: string;
  label: string;
  tax_year: number;
  province: string;
  updated_unix: number;
  /// Present for a corporate return.
  period: PeriodView | null;
}

export interface StoredReturnView {
  id: string;
  label: string;
  tax_year: number;
  province: string;
  facts: Record<string, string>;
  period: PeriodView | null;
}

export interface StorageStatus {
  available: boolean;
  error: string | null;
  path: string | null;
}

export interface SaveInput {
  /** null creates a new return; a string updates in place. */
  id: string | null;
  label: string;
  tax_year: number;
  province: string;
  facts: Record<string, string>;
}

/// A corporate return, keyed by fiscal period rather than tax year.
///
/// A corporation does not have a tax year the way a person does — it has
/// whatever falls between one year end and the next, which is why these are
/// dates and not a number.
export interface T2Input {
  period_start: string;
  period_end: string;
  province: string;
  facts: Record<string, string>;
}

export interface T2View {
  period_days: number;
  is_short_year: boolean;
  straddles: boolean;
  accounting_income: string;
  net_income_for_tax: string;
  taxable_income: string;
  small_business_deduction: string;
  federal_tax: string;
  provincial_tax: string;
  total_tax: string;
  balance: string;
  lines: LineView[];
  diagnostics: DiagnosticView[];
  has_errors: boolean;
  data_sound: boolean;
  certified_to_file: boolean;
  may_file: boolean;
}

export interface SaveT2Input {
  id: string | null;
  label: string;
  province: string;
  period_start: string;
  period_end: string;
  facts: Record<string, string>;
}
