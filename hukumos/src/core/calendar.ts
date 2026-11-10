/**
 * Working-day ("hari kerja") arithmetic on ISO dates (YYYY-MM-DD), in UTC.
 *
 * Weekends are never working days. Public holidays and cuti bersama change
 * every year by government decree, so they are passed in, not hard-coded.
 */

export type IsoDate = string;

export interface Calendar {
  holidays: ReadonlySet<IsoDate>;
}

export const WEEKENDS_ONLY: Calendar = { holidays: new Set() };

export function parseIso(d: IsoDate): Date {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) throw new Error(`Tanggal tidak valid: ${d}`);
  const date = new Date(`${d}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== d) {
    throw new Error(`Tanggal tidak valid: ${d}`);
  }
  return date;
}

export function toIso(d: Date): IsoDate {
  return d.toISOString().slice(0, 10);
}

export function addDays(d: IsoDate, n: number): IsoDate {
  const date = parseIso(d);
  date.setUTCDate(date.getUTCDate() + n);
  return toIso(date);
}

export function isWorkingDay(d: IsoDate, cal: Calendar = WEEKENDS_ONLY): boolean {
  const dow = parseIso(d).getUTCDay();
  return dow !== 0 && dow !== 6 && !cal.holidays.has(d);
}

/**
 * The n-th working day after `start` (the start day itself is not counted).
 * A deadline of 10 hari kerja from a request received on `start` ends on
 * `addWorkingDays(start, 10)`.
 */
export function addWorkingDays(start: IsoDate, n: number, cal: Calendar = WEEKENDS_ONLY): IsoDate {
  if (!Number.isInteger(n) || n < 0) throw new Error(`Jumlah hari kerja tidak valid: ${n}`);
  let d = start;
  let left = n;
  while (left > 0) {
    d = addDays(d, 1);
    if (isWorkingDay(d, cal)) left--;
  }
  return d;
}

/** Working days in (a, b]. Zero when b <= a. */
export function workingDaysBetween(a: IsoDate, b: IsoDate, cal: Calendar = WEEKENDS_ONLY): number {
  let count = 0;
  let d = a;
  while (d < b) {
    d = addDays(d, 1);
    if (isWorkingDay(d, cal)) count++;
  }
  return count;
}
