/** Rainflow cycle counting (ASTM E1049 three-point method) and damage-equivalent loads. */

export interface Cycle {
  range: number;
  mean: number;
  count: 0.5 | 1;
}

/** Reduce a signal to its turning points (local extrema). */
export function turningPoints(y: ArrayLike<number>): number[] {
  const out: number[] = [];
  for (let i = 0; i < y.length; i++) {
    const v = y[i];
    if (out.length < 2) {
      if (out.length === 1 && v === out[0]) continue;
      out.push(v);
      continue;
    }
    const a = out[out.length - 2];
    const b = out[out.length - 1];
    if ((b - a) * (v - b) > 0) out[out.length - 1] = v; // still monotone: extend
    else if (v !== b) out.push(v);
  }
  return out;
}

export function rainflow(y: ArrayLike<number>): Cycle[] {
  const tp = turningPoints(y);
  const stack: number[] = [];
  const cycles: Cycle[] = [];
  for (const p of tp) {
    stack.push(p);
    while (stack.length >= 3) {
      const x = Math.abs(stack[stack.length - 1] - stack[stack.length - 2]);
      const yr = Math.abs(stack[stack.length - 2] - stack[stack.length - 3]);
      if (x < yr) break;
      if (stack.length === 3) {
        cycles.push({ range: yr, mean: 0.5 * (stack[0] + stack[1]), count: 0.5 });
        stack.shift();
      } else {
        const a = stack[stack.length - 3];
        const b = stack[stack.length - 2];
        cycles.push({ range: yr, mean: 0.5 * (a + b), count: 1 });
        const last = stack.pop()!;
        stack.pop();
        stack.pop();
        stack.push(last);
      }
    }
  }
  for (let i = 0; i + 1 < stack.length; i++)
    cycles.push({ range: Math.abs(stack[i + 1] - stack[i]), mean: 0.5 * (stack[i] + stack[i + 1]), count: 0.5 });
  return cycles;
}

/**
 * Damage-equivalent load: the constant range that, applied at `refFreq` for
 * the signal duration, gives the same Miner damage with S–N slope m.
 *   DEL = (Σ nᵢ Sᵢᵐ / (f_ref · T))^{1/m}
 */
export function damageEquivalentLoad(y: ArrayLike<number>, duration: number, m = 4, refFreq = 1): number {
  if (duration <= 0) return 0;
  let s = 0;
  for (const c of rainflow(y)) s += c.count * Math.pow(c.range, m);
  return Math.pow(s / (refFreq * duration), 1 / m);
}
