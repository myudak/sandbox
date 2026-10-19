import { useState } from 'react';
import { useApp } from '../state/store';
import { analysisWorker, proxy } from '../workers/client';
import type { DetuningPoint, RobustMetric, RobustnessMap } from '../physics/robustness';
import type { WindState } from '../physics/wind';
import { Heatmap } from './Heatmap';
import { Chart, COLORS } from './Chart';
import { Progress, Section, Segmented } from './controls';
import { fmt } from './format';

const HS = [1, 2, 3, 4, 6, 8, 10];
const TP = [5, 7, 9, 11, 13, 15, 18, 21, 25, 30];
const DETUNE = [0.8, 0.85, 0.9, 0.95, 1, 1.05, 1.1, 1.15, 1.2];

type WindChoice = 'current' | 'parked' | 'rated' | 'above';
const WINDS: Record<Exclude<WindChoice, 'current'>, WindState> = {
  parked: { speed: 0, turbulence: 'off' },
  rated: { speed: 11.4, turbulence: 'B' },
  above: { speed: 18, turbulence: 'B' },
};

const METRICS: { value: RobustMetric; label: string }[] = [
  { value: 'pitchSigmaDeg', label: 'RMS pitch' },
  { value: 'pitchMaxDeg', label: 'Max pitch' },
  { value: 'towerDel', label: 'Tower DEL' },
];

export function RobustnessPanel() {
  const s = useApp();
  const [windChoice, setWindChoice] = useState<WindChoice>('current');
  const [metric, setMetric] = useState<RobustMetric>('pitchSigmaDeg');
  const [map, setMap] = useState<RobustnessMap | null>(null);
  const [detune, setDetune] = useState<DetuningPoint[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const wind = windChoice === 'current' ? s.wind : WINDS[windChoice];
  const run = async () => {
    setBusy('Sweeping Hs × Tp…');
    setProgress(0);
    setMap(await analysisWorker().robustness(s.tmd, wind, HS, TP, proxy(setProgress)));
    setBusy(null);
  };
  const runDetune = async () => {
    setBusy('Detuning sweep…');
    setProgress(0);
    setDetune(await analysisWorker().detuning(s.tmd, s.sea, s.wind, DETUNE, proxy(setProgress)));
    setBusy(null);
  };

  let summary: { helps: number; hurts: number; best: number; worst: number } | null = null;
  if (map) {
    const all = map.change[metric].flat();
    summary = {
      helps: all.filter((v) => v < -1).length / all.length,
      hurts: all.filter((v) => v > 1).length / all.length,
      best: Math.min(...all),
      worst: Math.max(...all),
    };
  }
  const unit = metric === 'towerDel' ? 'MN·m' : '°';
  const scale = metric === 'towerDel' ? 1e-6 : 1;

  return (
    <>
      <Section title="When does the damper help — and when does it hurt?">
        <p className="muted small">
          Every cell compares the platform with and without the current damper ({fmt(s.tmd.mass / 1000, 0)} t, f {fmt(s.tmd.freqRatio, 2)}, ζ{' '}
          {fmt(s.tmd.dampingRatio, 2)}) in the same JONSWAP sea and wind. Drag is re-linearised in every cell.
        </p>
        <Segmented
          label="Wind condition"
          value={windChoice}
          options={[
            { value: 'current', label: `Current (${fmt(s.wind.speed, 1)} m/s)` },
            { value: 'parked', label: 'Parked' },
            { value: 'rated', label: 'Rated + turb.' },
            { value: 'above', label: '18 m/s + turb.' },
          ]}
          onChange={setWindChoice}
        />
        <Segmented label="Metric" value={metric} options={METRICS} onChange={setMetric} />
        <button className="primary" disabled={!!busy} onClick={run}>
          Run sweep ({HS.length * TP.length} sea states)
        </button>
        {busy && <Progress value={progress} label={busy} />}
      </Section>

      {map && summary && (
        <Section title={`% change in ${METRICS.find((m) => m.value === metric)!.label.toLowerCase()} · wind ${fmt(map.wind.speed, 1)} m/s`}>
          <Heatmap
            rows={map.hs}
            cols={map.tp}
            values={map.change[metric]}
            rowLabel="Hs [m]"
            colLabel="Tp [s]"
            limit={50}
            tooltip={(i, j) =>
              `Hs ${map.hs[i]} m · Tp ${map.tp[j]} s\nWithout: ${fmt(map.base[i][j][metric] * scale, 3)} ${unit}\nWith TMD: ${fmt(
                map.withTmd[i][j][metric] * scale,
                3,
              )} ${unit}\nChange: ${fmt(map.change[metric][i][j], 1)}%\nDamper rotation: ${fmt(map.withTmd[i][j].strokeDeg, 0)}°`
            }
          />
          <p className="small">
            The damper helps in <b>{Math.round(summary.helps * 100)}%</b> of these sea states and hurts in{' '}
            <b>{Math.round(summary.hurts * 100)}%</b> (±1% counted as neutral). Best {fmt(summary.best, 1)}%, worst +{fmt(summary.worst, 1)}%.
          </p>
        </Section>
      )}

      <Section title="Detuning sensitivity">
        <p className="muted small">
          The platform's pitch frequency drifts (ballast changes, marine growth, mooring wear) while the damper keeps its as-built tuning.
          Uses the current sea state and wind.
        </p>
        <button disabled={!!busy} onClick={runDetune}>
          Run detuning sweep
        </button>
        {detune && (
          <Chart
            data={[detune.map((d) => (d.freqFactor - 1) * 100), detune.map((d) => d.changePct)] as never}
            series={[{ label: 'Change in RMS pitch', color: COLORS.withTmd, points: true }]}
            xLabel="Platform pitch-frequency shift [%]"
            yLabel="RMS pitch change [%]"
            height={180}
            fmtX={(v) => v.toFixed(0)}
            fmtY={(v) => v.toFixed(1)}
          />
        )}
      </Section>
    </>
  );
}
