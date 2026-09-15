import { invoke } from "@tauri-apps/api/core";

import type {
  ChatReply,
  CcaPlan,
  ComputeInput,
  FilingGate,
  LicenceView,
  CoupleView,
  HouseholdInput,
  ImportPreview,
  Provider,
  ReturnSummary,
  ReturnView,
  RrspPlan,
  SaveInput,
  SettingsView,
  T2Input,
  T2View,
  StorageStatus,
  StoredReturnView,
  Turn,
} from "./types";

export const computeReturn = (input: ComputeInput): Promise<ReturnView> =>
  invoke("compute_return", { input });

export const supported = (): Promise<{
  years: number[];
  provinces: string[];
  t2_provinces: string[];
}> => invoke("supported");

export const getSettings = (): Promise<SettingsView> => invoke("get_settings");

export const setProvider = (
  provider: Provider,
  apiKey: string | null,
): Promise<SettingsView> => invoke("set_provider", { provider, apiKey });

export const grantConsent = (): Promise<SettingsView> => invoke("grant_consent");

export const revokeConsent = (): Promise<SettingsView> => invoke("revoke_consent");

export const advisorChat = (
  compute: ComputeInput,
  history: Turn[],
  message: string,
): Promise<ChatReply> =>
  invoke("advisor_chat", { input: { compute, history, message } });

export const coupleOptimize = (
  input: ComputeInput,
  household: HouseholdInput,
): Promise<CoupleView> => invoke("couple_optimize", { input, household });

export const licenceStatus = (taxYear: number): Promise<LicenceView> =>
  invoke("licence_status", { taxYear });

/**
 * `verifyOnline` is the only thing in the app that permits a licensing request
 * to leave the machine, and it is passed per attempt rather than remembered.
 */
export const installLicence = (
  input: string,
  verifyOnline: boolean,
  taxYear: number,
): Promise<LicenceView> =>
  invoke("install_licence", { input, verifyOnline, taxYear });

export const installLicenceFile = (
  path: string,
  taxYear: number,
): Promise<LicenceView> => invoke("install_licence_file", { path, taxYear });

export const removeLicence = (taxYear: number): Promise<LicenceView> =>
  invoke("remove_licence", { taxYear });

export const filingGate = (input: ComputeInput): Promise<FilingGate> =>
  invoke("filing_gate", { input });

export const ccaPlan = (input: ComputeInput): Promise<CcaPlan> =>
  invoke("cca_plan", { input });

export const rrspPlan = (
  input: ComputeInput,
  room: string | null,
): Promise<RrspPlan> => invoke("rrsp_plan", { input, room });

export const autofillImport = (
  input: ComputeInput,
  source: "cra" | "sample",
): Promise<ImportPreview> => invoke("autofill_import", { input, source });

export const autofillApply = (
  input: ComputeInput,
  accept: string[],
): Promise<Record<string, string>> => invoke("autofill_apply", { input, accept });

export const storageStatus = (): Promise<StorageStatus> => invoke("storage_status");

export const listReturns = (): Promise<ReturnSummary[]> => invoke("list_returns");

export const saveReturn = (input: SaveInput): Promise<ReturnSummary> =>
  invoke("save_return", { input });

export const loadReturn = (id: string): Promise<StoredReturnView> =>
  invoke("load_return", { id });

export const deleteReturn = (id: string): Promise<ReturnSummary[]> =>
  invoke("delete_return", { id });

export const whenLocal = (unix: number): string =>
  new Date(unix * 1000).toLocaleString("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  });

const CAD = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
});

export const money = (raw: string): string => CAD.format(Number(raw) || 0);

/** Tauri command errors arrive as plain strings; anything else is a real bug. */
export const errorText = (e: unknown): string =>
  typeof e === "string" ? e : e instanceof Error ? e.message : String(e);

export const computeT2 = (input: T2Input): Promise<T2View> =>
  invoke("compute_t2", { input });

export const t2FilingGate = (input: T2Input): Promise<FilingGate> =>
  invoke("t2_filing_gate", { input });
