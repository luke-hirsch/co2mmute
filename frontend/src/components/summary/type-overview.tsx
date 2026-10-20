import { de } from "@/lib/de";
import { modeTally, type TypeLine } from "@/lib/game/groups";

/**
 * "Wie die Pendlertypen gefahren sind": one line per type, folded by default so
 * the summary does not grow. Opened, it says what all the Gruppen of a type did
 * over the game — the question "did the type matter" in one glance.
 *
 * The text and its modes are in the page while it is folded. No seat is named
 * and no CO₂ figure shown: the budget of a game that hid it is the summary's
 * own to reveal, and this is about what a type did.
 */
export function TypeOverview({ lines }: { lines: readonly TypeLine[] }) {
  if (lines.length === 0) return null;
  return (
    <details className="group">
      <summary className="cursor-pointer text-2xl font-semibold">
        {de.summary.typesTitle}
      </summary>
      <p className="mt-4 max-w-(--measure-body) text-muted-foreground">
        {de.summary.typesLead}
      </p>
      <ul className="mt-4 divide-y divide-border border-y border-border">
        {lines.map((line) => (
          <li
            key={line.name}
            className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-3"
          >
            <span>
              <span className="font-medium">{line.name}</span>
              <span className="text-muted-foreground">
                {" · "}
                {de.summary.typeGroups(line.groups)}
              </span>
            </span>
            <span className="font-mono text-sm text-muted-foreground">
              {line.rounds === 0
                ? de.summary.groupNone
                : modeTally(line.modes)
                    .map(({ mode, count }) =>
                      de.summary.groupModeCount(count, de.modes[mode]),
                    )
                    .join(", ")}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
