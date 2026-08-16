// Pure deep-link parsing — extract a WalletConnect `wc:` pairing URI from an inbound URL.
// Kept dependency-free so it is unit-testable without the WalletConnect/native stack.
export function extractWcUri(url: string): string | null {
  const trimmed = url.trim();
  if (trimmed.startsWith('wc:')) return trimmed;
  // lattice://wc?uri=<url-encoded wc: uri>  (the standard mobile hand-off)
  const q = trimmed.indexOf('?');
  if (q >= 0) {
    for (const part of trimmed.slice(q + 1).split('&')) {
      const eq = part.indexOf('=');
      if (eq < 0) continue;
      if (part.slice(0, eq) === 'uri') {
        const decoded = decodeURIComponent(part.slice(eq + 1));
        if (decoded.startsWith('wc:')) return decoded;
      }
    }
  }
  // Fallback: a raw wc: URI embedded anywhere in the link.
  const m = trimmed.match(/wc:[^\s"'&]+/);
  return m ? decodeURIComponent(m[0]) : null;
}
