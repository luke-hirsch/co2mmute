import { carShareAt, type Co2Table } from "@/lib/calibration";
import { de } from "@/lib/de";

/** The map notes' look: ink with an accent rule, not amber text. */
const noteClass = "border-l-2 border-brandaccent pl-3 text-sm";

/**
 * What the dial's kg buys on the selected map, one line under the dial.
 *
 * Reads the map's table the way the Python side does (`carShareAt`). Prints
 * nothing on a map that has no table; a budget that cannot be lost or made is
 * said, not refused — the host may still create the game.
 */
export function BudgetNote({
  table,
  kgPerPerson,
}: {
  table: Co2Table | null | undefined;
  kgPerPerson: string;
}) {
  if (!table) return null;
  const share = carShareAt(kgPerPerson, table);

  if (share === null || share >= 1) {
    const lost = share !== null;
    return (
      <div className={`${noteClass} space-y-1`}>
        <p>
          {de.create.co2Unplayable}{" "}
          {lost
            ? de.create.co2NeverLost(kgPerPerson)
            : de.create.co2NeverMade(kgPerPerson)}
        </p>
        <p>{lost ? de.create.co2NeverLostTip : de.create.co2NeverMadeTip}</p>
      </div>
    );
  }
  return (
    <p className={noteClass}>
      {de.create.co2Reaches(kgPerPerson, Math.round(share * 100))}
    </p>
  );
}
