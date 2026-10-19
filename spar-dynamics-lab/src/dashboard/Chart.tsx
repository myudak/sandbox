import { useEffect, useRef } from 'react';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

export const COLORS = {
  withTmd: '#3987e5',
  without: '#d95926',
  aux: '#199e70',
  grid: 'rgba(160, 175, 190, 0.12)',
  axis: '#93a1ae',
  helps: '#3987e5',
  hurts: '#e66767',
  neutral: '#383835',
};

export interface SeriesSpec {
  label: string;
  color: string;
  dash?: number[];
  width?: number;
  points?: boolean;
}

interface Props {
  data: uPlot.AlignedData;
  series: SeriesSpec[];
  xLabel: string;
  yLabel: string;
  height?: number;
  xLog?: boolean;
  yLog?: boolean;
  xRange?: [number, number];
  fmtX?: (v: number) => string;
  fmtY?: (v: number) => string;
}

/** Thin uPlot wrapper: one y axis, recessive grid, crosshair + legend values on hover. */
export function Chart({ data, series, xLabel, yLabel, height = 200, xLog, yLog, xRange, fmtX, fmtY }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  const key = series.map((s) => s.label + s.color).join('|') + xLog + yLog + xLabel + yLabel + JSON.stringify(xRange) + series.map((s) => s.points).join();

  useEffect(() => {
    if (!host.current) return;
    const axis = (label: string, fmt?: (v: number) => string): uPlot.Axis => ({
      label,
      stroke: COLORS.axis,
      labelSize: 18,
      size: 46,
      font: '11px Inter, system-ui, sans-serif',
      labelFont: '11px Inter, system-ui, sans-serif',
      grid: { stroke: COLORS.grid, width: 1 },
      ticks: { stroke: COLORS.grid, width: 1 },
      values: fmt ? (_u, vals) => vals.map((v) => (v == null ? '' : fmt(v))) : undefined,
    });
    const opts: uPlot.Options = {
      width: host.current.clientWidth || 400,
      height,
      padding: [8, 8, 0, 0],
      cursor: { points: { size: 8 }, drag: { x: false, y: false } },
      legend: { show: true, live: true },
      scales: {
        x: { time: false, distr: xLog ? 3 : 1, ...(xRange ? { range: xRange } : {}) },
        y: { distr: yLog ? 3 : 1 },
      },
      axes: [axis(xLabel, fmtX), axis(yLabel, fmtY)],
      series: [
        { label: xLabel, value: (_u, v) => (v == null ? '—' : fmtX ? fmtX(v) : v.toPrecision(3)) },
        ...series.map((s) => ({
          label: s.label,
          stroke: s.color,
          width: s.width ?? 2,
          dash: s.dash,
          points: { show: s.points ?? false, size: 8, fill: s.color },
          value: (_u: uPlot, v: number | null) => (v == null ? '—' : fmtY ? fmtY(v) : v.toPrecision(3)),
        })),
      ],
    };
    plot.current = new uPlot(opts, data, host.current);
    const ro = new ResizeObserver(() => {
      if (host.current && plot.current) plot.current.setSize({ width: host.current.clientWidth, height });
    });
    ro.observe(host.current);
    return () => {
      ro.disconnect();
      plot.current?.destroy();
      plot.current = null;
    };
  }, [key, height]);

  useEffect(() => {
    plot.current?.setData(data);
  }, [data]);

  return <div className="chart" ref={host} />;
}
