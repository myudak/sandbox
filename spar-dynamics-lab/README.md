# SPAR Dynamics Lab

An interactive 3D simulation of a floating offshore wind turbine (the OC3-Hywind
spar with the NREL 5-MW turbine) that has a **rotary tuned mass damper**. Its
goal isn't to show that a damper helps. It asks **when the damper helps and
when it hurts**.

- **Simulate:** a 3D ocean driven by the same wave components as the physics.
  Two platforms run side by side, with and without the TMD, under identical
  waves and wind. The view includes the nacelle cutaway, underwater moorings,
  and a live comparison table and time series.
- **Spectra:** RAOs, response spectra and the environmental input.
- **Optimise:** tunes the damper's frequency and damping under mass, stroke and
  spring-feasibility constraints, and sweeps the mass/benefit/cost trade-off.
- **Robustness:** Hs × Tp heatmaps of % change (blue helps, red hurts) for
  different wind conditions, plus a detuning sweep.
- **Validation:** OC3 natural periods, hydrostatics, time domain vs frequency
  domain, Den Hartog, rainflow.
- **Model:** assumptions, limits, sources and findings.

The equations, assumptions and validation results are in
[`docs/MODEL.md`](docs/MODEL.md).

## Run

```bash
npm install
npm run dev       # http://localhost:5173
npm test          # physics validation tests
npm run build     # type-check + production build to dist/
```

The stack is Vite, React 18, TypeScript, three.js (react-three-fiber/drei),
zustand, uPlot and Comlink. All physics lives in plain TypeScript under
`src/physics` and has no DOM dependencies.

## Layout

```
src/physics/   params, waves, hydro, wind, tmd, model, frequency, timeDomain,
               fatigue, recorder, optimize, robustness, validation (+ __tests__)
src/sim/       engine that runs the paired with/without-TMD simulations
src/scene/     3D scene: ocean shader, turbine + damper, moorings, camera rig
src/dashboard/ panels, charts, heatmap
src/workers/   analysis worker (optimiser, sweeps, validation)
```
