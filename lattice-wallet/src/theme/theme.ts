// Dark, high-contrast design tokens. "Lattice" — a secure grid; the accent evokes the
// lattice-based math behind post-quantum cryptography.
export const colors = {
  bg: '#0B0E14',
  surface: '#131824',
  surfaceAlt: '#1B2233',
  border: '#26304A',
  text: '#EAF0FF',
  textDim: '#9AA7C2',
  textFaint: '#5E6B85',
  accent: '#6E8BFF', // lattice blue
  accentSoft: '#2A3557',
  success: '#3FD08A',
  danger: '#FF6B6B',
  warning: '#FFC65C',
  pq: '#B98BFF', // post-quantum violet
};

export const spacing = (n: number) => n * 4;

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
};

export const font = {
  h1: { fontSize: 30, fontWeight: '700' as const, color: colors.text },
  h2: { fontSize: 22, fontWeight: '700' as const, color: colors.text },
  h3: { fontSize: 17, fontWeight: '600' as const, color: colors.text },
  body: { fontSize: 15, fontWeight: '400' as const, color: colors.text },
  dim: { fontSize: 14, fontWeight: '400' as const, color: colors.textDim },
  mono: {
    fontSize: 13,
    fontFamily: undefined as string | undefined, // system monospace set per-platform
    color: colors.textDim,
  },
};
