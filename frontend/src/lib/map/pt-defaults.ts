/**
 * What a public transport vehicle holds when nobody says otherwise.
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
} as const;

/** Seats a new line of this mode starts with. */
export const defaultPtCapacity = (mode: "bus" | "train"): number =>
  DEFAULT_PT_CAPACITY[mode];
