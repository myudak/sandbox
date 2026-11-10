import type { IsoDate } from '../core/calendar';

export function fmtDate(d: IsoDate): string {
  return new Date(`${d}T00:00:00Z`).toLocaleDateString('id-ID', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}
