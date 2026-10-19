/**
 * Shape of an inextensible catenary mooring line with a seabed-resting part.
 * Given the horizontal span X and vertical drop H from anchor to fairlead and
 * the line length L, solve for the catenary parameter a (= H_tension / w).
 * Returns points (horizontal distance from the anchor, height above seabed).
 */
export function catenaryPoints(X: number, H: number, L: number, n = 40): [number, number][] {
  const taut = Math.hypot(X, H);
  if (L <= taut + 1e-6) {
    return Array.from({ length: n + 1 }, (_, i) => [(X * i) / n, (H * i) / n]);
  }
  // span(a) = (L − s) + a·asinh(s/a), s = √(H² + 2Ha): increasing in a
  const span = (a: number) => {
    const s = Math.sqrt(H * H + 2 * H * a);
    return Math.min(s, L) === s ? L - s + a * Math.asinh(s / a) : NaN;
  };
  let lo = 1e-3;
  let hi = 1e6;
  for (let i = 0; i < 80; i++) {
    const mid = Math.sqrt(lo * hi);
    const v = span(mid);
    if (Number.isNaN(v) || v > X) hi = mid;
    else lo = mid;
  }
  const a = Math.sqrt(lo * hi);
  const s = Math.sqrt(H * H + 2 * H * a);
  if (s >= L) return Array.from({ length: n + 1 }, (_, i) => [(X * i) / n, (H * i) / n]);
  const bottom = L - s;
  const xs = a * Math.asinh(s / a);
  const pts: [number, number][] = [[0, 0]];
  const nb = Math.max(2, Math.round(n * (bottom / L)));
  for (let i = 1; i <= nb; i++) pts.push([(bottom * i) / nb, 0]);
  const ns = n - nb;
  for (let i = 1; i <= ns; i++) {
    const u = (xs * i) / ns;
    pts.push([bottom + u, a * (Math.cosh(u / a) - 1)]);
  }
  return pts;
}
