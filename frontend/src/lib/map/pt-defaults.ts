/**
 * What a public transport vehicle holds, and how fast it runs, when nobody says
 * otherwise.
 *
 * Five places used to answer this and three of them disagreed — and the one a
 * map author actually meets, the editor's new-line panel, did not branch on
 * mode at all. That is how the shipped Berlin map came to carry a 60-seat
 * U-Bahn. The backend's own defaults (`maps/models.py`, the JSON importer and
 * the version-diff endpoint) carry the same two numbers.
 *
 * A 12 m city bus carries 70–100 including standing room; a Großprofil U-Bahn
 * train and a full S-Bahn are both around a thousand. They are game
 * parameters with a real order of magnitude behind them, not sourced figures:
 * since the timetable change nothing in the emissions path reads them, and
 * they decide only who fits on board.
 */
export const DEFAULT_PT_CAPACITY = {
  bus: 85,
  train: 1000,
  // Berlin's 40 m Flexity: 84 seats and 164 standing at 4 people/m²
  // (Bombardier's datasheet) — `TrainLine.DEFAULTS` on the backend.
  tram: 248,
} as const;

/**
 * How fast a new line of each kind runs, the backend's `bus_speed_kmh` default
 * and `TrainLine.DEFAULTS`. A tram gets the bus's 30: the model has no dwell
 * time, so a line's speed leaves its stops out, and BVG's own averages put
 * tram and bus level (17.1 and 17.9 km/h in 2025, stops and traffic counted).
 */
export const DEFAULT_PT_SPEED_KMH = {
  bus: 30,
  train: 40,
  tram: 30,
} as const;

/** What runs a line: a bus, or a train line's kind. */
export type PtVehicle = keyof typeof DEFAULT_PT_CAPACITY;

/** Seats a new line of this kind starts with. */
export const defaultPtCapacity = (vehicle: PtVehicle): number =>
  DEFAULT_PT_CAPACITY[vehicle];

/** The speed a new line of this kind starts with. */
export const defaultPtSpeed = (vehicle: PtVehicle): number =>
  DEFAULT_PT_SPEED_KMH[vehicle];
