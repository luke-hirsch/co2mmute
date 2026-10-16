/**
 * The replay clock as a time of day.
 *
 * Departures are drawn from a two-hour window around the game's departure hour,
 * so a pass starts an hour before it: the morning at `morning_departure_hour − 1`
 * (8:00 at the default 9), the way home from `evening_departure_hour − 1`
 * (16:00 at 17). The recording's own axis is minutes from zero, with the way home
 * from `homeStartMin`.
 */

export type ClockHours = {
  morningHour: number;
  eveningHour: number;
  /** `Replay.home_start_min`, null for a round with no way home. */
  homeStartMin: number | null;
};

export function replayClockOfDay(minute: number, hours: ClockHours): string {
  const { morningHour, eveningHour, homeStartMin } = hours;
  const home = homeStartMin !== null && minute >= homeStartMin;
  const start = (home ? eveningHour : morningHour) - 1;
  const since = home ? minute - (homeStartMin as number) : minute;
  const total = Math.floor(start * 60 + since);
  const h = Math.floor(total / 60) % 24;
  const m = total % 60;
  return `${h}:${String(m).padStart(2, "0")} Uhr`;
}
