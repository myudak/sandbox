import * as Comlink from 'comlink';
import { OC3_HYWIND } from '../physics/params';
import { Constraints, Objective, optimizeTuning, paretoFront } from '../physics/optimize';
import { detuningCurve, robustnessMap } from '../physics/robustness';
import { runValidation } from '../physics/validation';
import type { TmdDesign } from '../physics/tmd';
import type { SeaState } from '../physics/waves';
import type { WindState } from '../physics/wind';

type Progress = (p: number) => void;

const api = {
  optimize(sea: SeaState, wind: WindState, objective: Objective, constraints: Constraints, geometry: TmdDesign, onProgress: Progress) {
    return optimizeTuning({ params: OC3_HYWIND, sea, wind, objective, constraints }, geometry, onProgress);
  },
  pareto(
    sea: SeaState,
    wind: WindState,
    objective: Objective,
    constraints: Constraints,
    geometry: TmdDesign,
    massRatios: number[],
    onProgress: Progress,
  ) {
    return paretoFront({ params: OC3_HYWIND, sea, wind, objective, constraints }, geometry, massRatios, onProgress);
  },
  robustness(tmd: TmdDesign, wind: WindState, hs: number[], tp: number[], onProgress: Progress) {
    return robustnessMap(OC3_HYWIND, tmd, wind, hs, tp, 3.3, onProgress);
  },
  detuning(tmd: TmdDesign, sea: SeaState, wind: WindState, factors: number[], onProgress: Progress) {
    return detuningCurve(OC3_HYWIND, tmd, sea, wind, factors, onProgress);
  },
  validate(onProgress: Progress) {
    return runValidation(onProgress);
  },
};

export type AnalysisApi = typeof api;

Comlink.expose(api);
