export const DEG = 180 / Math.PI;

export function fmt(v: number, digits = 2): string {
  if (!Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e6 || a < 1e-4)) return v.toExponential(1);
  return v.toFixed(digits);
}

export function pctChange(withTmd: number, without: number): number {
  return without !== 0 && Number.isFinite(without) ? (100 * (withTmd - without)) / Math.abs(without) : NaN;
}

export function fmtEuro(v: number): string {
  if (v >= 1e6) return `€${(v / 1e6).toFixed(2)} M`;
  return `€${Math.round(v / 1000)} k`;
}
