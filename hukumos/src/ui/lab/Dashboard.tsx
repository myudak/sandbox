import type { ErrorKind, Verdict } from '../../lab/types';
import { ERROR_KIND, VERDICT, results } from './util';

export function Dashboard({ onPasal }: { onPasal: (id: string) => void }) {
  const ps = results.pasal;
  const sum = (k: keyof (typeof ps)[number]['metrics']) =>
    ps.reduce<[number, number]>((acc, p) => [acc[0] + p.metrics[k][0], acc[1] + p.metrics[k][1]], [0, 0]);
  const pct = ([a, b]: [number, number]) => (b ? Math.round((a / b) * 100) : 0);

  const verdicts = (Object.keys(VERDICT) as Verdict[]).map((v) => [v, ps.filter((p) => p.verdict === v).length] as const);

  const counts = new Map<ErrorKind, number>();
  for (const p of ps)
    for (const s of [...p.samples, ...p.perturbations.map((x) => x.sample)])
      for (const k of new Set(s.errorKinds)) counts.set(k, (counts.get(k) ?? 0) + 1);
  const errors = (Object.keys(ERROR_KIND) as ErrorKind[]).map((k) => [k, counts.get(k) ?? 0] as const).sort((a, b) => b[1] - a[1]);
  const maxErr = Math.max(1, ...errors.map(([, n]) => n));
  const totalSamples = ps.reduce((n, p) => n + p.samples.length + p.perturbations.length, 0);

  const tiles: [string, [number, number], string][] = [
    ['Lolos typecheck', sum('typecheck'), 'sampel'],
    ['Skenario benar', sum('scenarios'), 'pengecekan'],
    ['Uji ubah teks lolos', sum('perturbations'), 'perubahan'],
    ['Terbukti setara baseline', sum('equivalent'), 'sampel'],
  ];

  return (
    <div className="stack">
      <section className="tiles">
        <div className="tile">
          <div className="tile__label">Pasal</div>
          <div className="tile__value">{ps.length}</div>
          <div className="tile__sub">
            {verdicts
              .filter(([, n]) => n)
              .map(([v, n]) => (
                <span key={v} className={`tone--${VERDICT[v].tone}`}>
                  {VERDICT[v].icon} {n} {VERDICT[v].label.toLowerCase()}
                </span>
              ))}
          </div>
        </div>
        {tiles.map(([label, frac, unit]) => (
          <div key={label} className="tile">
            <div className="tile__label">{label}</div>
            <div className="tile__value">{pct(frac)}%</div>
            <div className="tile__sub">
              {frac[0]} dari {frac[1]} {unit}
            </div>
          </div>
        ))}
      </section>

      <section className="card">
        <h3 className="h3">Per pasal</h3>
        <div className="table-wrap">
          <table className="table table--dash">
            <thead>
              <tr>
                <th>Pasal</th>
                <th>Putusan</th>
                <th className="num">Typecheck</th>
                <th className="num">Skenario</th>
                <th className="num">Ubah teks</th>
                <th className="num">Sepakat</th>
                <th className="num">Setara</th>
                <th className="num">Properti</th>
              </tr>
            </thead>
            <tbody>
              {ps.map((p) => (
                <tr key={p.pasal.id} className="clickable" onClick={() => onPasal(p.pasal.id)}>
                  <td>{p.pasal.cite}</td>
                  <td className={`tone--${VERDICT[p.verdict].tone}`}>
                    {VERDICT[p.verdict].icon} {VERDICT[p.verdict].label}
                  </td>
                  {(['typecheck', 'scenarios', 'perturbations', 'agreement', 'equivalent', 'properties'] as const).map((k) => (
                    <td key={k} className={`num ${p.metrics[k][0] === p.metrics[k][1] ? '' : 'warnc'}`}>
                      {p.metrics[k][0]}/{p.metrics[k][1]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h3 className="h3">Jenis kesalahan</h3>
        <p className="muted small">
          Jumlah sampel (dari {totalSamples}, termasuk terjemahan teks yang diubah) dengan tiap jenis kesalahan, dan pengecekan mana yang menangkapnya.
        </p>
        <div className="bars">
          {errors.map(([k, n]) => (
            <div key={k} className="barrow" title={`${ERROR_KIND[k].label}: ${n} sampel`}>
              <div className="barrow__label">
                {ERROR_KIND[k].label}
                <small>ditangkap oleh: {ERROR_KIND[k].caughtBy}</small>
              </div>
              <div className="barrow__track">
                {n > 0 && <div className="barrow__fill" style={{ width: `${(n / maxErr) * 100}%` }} />}
                <span className="barrow__value">{n}</span>
              </div>
            </div>
          ))}
        </div>
        <p className="muted small">
          Yang tidak tampil di sini: terjemahan salah yang lolos semua pengecekan. Ukurannya hanya bisa diketahui dari tinjauan ahli hukum (tab Tinjauan).
        </p>
      </section>
    </div>
  );
}
