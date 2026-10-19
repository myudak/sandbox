/** Small dense linear algebra for 3×3–8×8 systems. Matrices are row-major number[][]. */

export type Mat = number[][];
export type Vec = number[];

export function zeros(n: number, m = n): Mat {
  return Array.from({ length: n }, () => new Array<number>(m).fill(0));
}

export function clone(a: Mat): Mat {
  return a.map((r) => r.slice());
}

export function add(a: Mat, b: Mat): Mat {
  return a.map((r, i) => r.map((v, j) => v + b[i][j]));
}

export function matVec(a: Mat, x: Vec): Vec {
  return a.map((r) => r.reduce((s, v, j) => s + v * x[j], 0));
}

export function transpose(a: Mat): Mat {
  return a[0].map((_, j) => a.map((r) => r[j]));
}

export function matMul(a: Mat, b: Mat): Mat {
  const n = a.length;
  const m = b[0].length;
  const k = b.length;
  const out = zeros(n, m);
  for (let i = 0; i < n; i++)
    for (let j = 0; j < m; j++) {
      let s = 0;
      for (let l = 0; l < k; l++) s += a[i][l] * b[l][j];
      out[i][j] = s;
    }
  return out;
}

/** Real Gaussian elimination with partial pivoting; returns A⁻¹. */
export function inverse(a: Mat): Mat {
  const n = a.length;
  const m = a.map((r, i) => [...r, ...Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(m[r][c]) > Math.abs(m[p][c])) p = r;
    if (Math.abs(m[p][c]) < 1e-300) throw new Error('Singular matrix');
    [m[c], m[p]] = [m[p], m[c]];
    const piv = m[c][c];
    for (let j = 0; j < 2 * n; j++) m[c][j] /= piv;
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = m[r][c];
      if (f === 0) continue;
      for (let j = 0; j < 2 * n; j++) m[r][j] -= f * m[c][j];
    }
  }
  return m.map((r) => r.slice(n));
}

export function solve(a: Mat, b: Vec): Vec {
  return matVec(inverse(a), b);
}

/**
 * Complex solve (Ar + i·Ai)(xr + i·xi) = br + i·bi via Gaussian elimination
 * with partial pivoting on interleaved storage. Allocation-light for hot loops.
 */
export function complexSolve(ar: Mat, ai: Mat, br: Vec, bi: Vec): { re: Vec; im: Vec } {
  const n = ar.length;
  const Mr = ar.map((r) => r.slice());
  const Mi = ai.map((r) => r.slice());
  const xr = br.slice();
  const xi = bi.slice();
  for (let c = 0; c < n; c++) {
    let p = c;
    let best = Mr[c][c] ** 2 + Mi[c][c] ** 2;
    for (let r = c + 1; r < n; r++) {
      const v = Mr[r][c] ** 2 + Mi[r][c] ** 2;
      if (v > best) {
        best = v;
        p = r;
      }
    }
    if (best < 1e-300) throw new Error('Singular complex matrix');
    if (p !== c) {
      [Mr[c], Mr[p]] = [Mr[p], Mr[c]];
      [Mi[c], Mi[p]] = [Mi[p], Mi[c]];
      [xr[c], xr[p]] = [xr[p], xr[c]];
      [xi[c], xi[p]] = [xi[p], xi[c]];
    }
    const pr = Mr[c][c];
    const pi = Mi[c][c];
    const den = pr * pr + pi * pi;
    for (let r = c + 1; r < n; r++) {
      // f = M[r][c] / M[c][c]
      const fr = (Mr[r][c] * pr + Mi[r][c] * pi) / den;
      const fi = (Mi[r][c] * pr - Mr[r][c] * pi) / den;
      if (fr === 0 && fi === 0) continue;
      for (let j = c; j < n; j++) {
        Mr[r][j] -= fr * Mr[c][j] - fi * Mi[c][j];
        Mi[r][j] -= fr * Mi[c][j] + fi * Mr[c][j];
      }
      const tr = xr[r] - (fr * xr[c] - fi * xi[c]);
      const ti = xi[r] - (fr * xi[c] + fi * xr[c]);
      xr[r] = tr;
      xi[r] = ti;
    }
  }
  for (let r = n - 1; r >= 0; r--) {
    let sr = xr[r];
    let si = xi[r];
    for (let j = r + 1; j < n; j++) {
      sr -= Mr[r][j] * xr[j] - Mi[r][j] * xi[j];
      si -= Mr[r][j] * xi[j] + Mi[r][j] * xr[j];
    }
    const pr = Mr[r][r];
    const pi = Mi[r][r];
    const den = pr * pr + pi * pi;
    xr[r] = (sr * pr + si * pi) / den;
    xi[r] = (si * pr - sr * pi) / den;
  }
  return { re: xr, im: xi };
}

/** Cholesky factor L (lower) with A = L Lᵀ. A must be SPD. */
export function cholesky(a: Mat): Mat {
  const n = a.length;
  const L = zeros(n);
  for (let i = 0; i < n; i++)
    for (let j = 0; j <= i; j++) {
      let s = a[i][j];
      for (let k = 0; k < j; k++) s -= L[i][k] * L[j][k];
      if (i === j) {
        if (s <= 0) throw new Error('Matrix not positive definite');
        L[i][i] = Math.sqrt(s);
      } else L[i][j] = s / L[j][j];
    }
  return L;
}

/** Cyclic Jacobi eigen-decomposition of a symmetric matrix. Columns of `vectors` are eigenvectors. */
export function symmetricEigen(a: Mat): { values: Vec; vectors: Mat } {
  const n = a.length;
  const A = clone(a);
  const V = zeros(n);
  for (let i = 0; i < n; i++) V[i][i] = 1;
  for (let sweep = 0; sweep < 100; sweep++) {
    let off = 0;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) off += A[i][j] ** 2;
    if (off < 1e-22 * (1 + A.reduce((s, r, i) => s + r[i] ** 2, 0))) break;
    for (let p = 0; p < n; p++)
      for (let q = p + 1; q < n; q++) {
        if (Math.abs(A[p][q]) < 1e-300) continue;
        const theta = (A[q][q] - A[p][p]) / (2 * A[p][q]);
        const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = A[k][p];
          const akq = A[k][q];
          A[k][p] = c * akp - s * akq;
          A[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = A[p][k];
          const aqk = A[q][k];
          A[p][k] = c * apk - s * aqk;
          A[q][k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = V[k][p];
          const vkq = V[k][q];
          V[k][p] = c * vkp - s * vkq;
          V[k][q] = s * vkp + c * vkq;
        }
      }
  }
  return { values: A.map((r, i) => r[i]), vectors: V };
}

/**
 * Generalised symmetric eigenproblem K φ = λ M φ (M SPD). Returns eigenvalues
 * ascending with M-orthonormal eigenvectors (columns). K may be indefinite.
 */
export function generalizedEigen(K: Mat, M: Mat): { values: Vec; vectors: Mat } {
  const L = cholesky(M);
  const Li = inverse(L);
  const A = matMul(matMul(Li, K), transpose(Li));
  // symmetrise against round-off
  const n = A.length;
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) A[i][j] = A[j][i] = 0.5 * (A[i][j] + A[j][i]);
  const { values, vectors } = symmetricEigen(A);
  const phi = matMul(transpose(Li), vectors);
  const order = values.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0]);
  return {
    values: order.map(([v]) => v),
    vectors: phi.map((row) => order.map(([, i]) => row[i])),
  };
}
