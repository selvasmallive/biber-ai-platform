// Local activity log — records transactions the user sends FROM this wallet, on-device
// only. This gives basic "what did I just do" history with zero third-party calls (the
// privacy-first default). Full history is available via explorer deep links or the
// opt-in indexer setting.
import { loadJson, saveJson } from './storage';

export interface ActivityEntry {
  chainId: string;
  hash: string;
  to: string;
  amount: string; // human-formatted, incl. symbol
  timestamp: number;
  kind: 'send' | 'token-send';
  tokenSymbol?: string;
}

const KEY = 'lattice.activity.v1';
const MAX = 200;

export async function loadActivity(): Promise<ActivityEntry[]> {
  return loadJson<ActivityEntry[]>(KEY, []);
}

export async function recordActivity(entry: ActivityEntry): Promise<void> {
  const list = await loadActivity();
  list.unshift(entry);
  await saveJson(KEY, list.slice(0, MAX));
}

export async function activityForChain(chainId: string): Promise<ActivityEntry[]> {
  return (await loadActivity()).filter((e) => e.chainId === chainId);
}
