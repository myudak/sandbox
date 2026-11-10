import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import { addDays, addWorkingDays, isWorkingDay, workingDaysBetween } from './calendar';

describe('calendar', () => {
  it('skips weekends', () => {
    // 2026-11-13 is a Friday.
    expect(addWorkingDays('2026-11-13', 1)).toBe('2026-11-16');
    expect(addWorkingDays('2026-11-13', 10)).toBe('2026-11-27');
    expect(isWorkingDay('2026-11-14')).toBe(false);
  });

  it('skips holidays it is given', () => {
    const cal = { holidays: new Set(['2026-11-16']) };
    expect(addWorkingDays('2026-11-13', 1, cal)).toBe('2026-11-17');
  });

  it('rejects malformed dates', () => {
    expect(() => addDays('2026-02-30', 1)).toThrow();
  });

  it('addWorkingDays and workingDaysBetween are inverse', () => {
    const date = fc.integer({ min: 0, max: 3650 }).map((n) => addDays('2024-01-01', n));
    fc.assert(
      fc.property(date, fc.integer({ min: 0, max: 200 }), (d, n) => {
        const end = addWorkingDays(d, n);
        expect(workingDaysBetween(d, end)).toBe(n);
        if (n > 0) expect(isWorkingDay(end)).toBe(true);
      }),
    );
  });
});
