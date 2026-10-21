import { de } from "@/lib/de";
import {
  usePersonasInPlay,
  type PersonaInPlay,
} from "@/lib/queries/personas";

/**
 * "In diesem Spiel": each Pendlertyp once, with how many Gruppen hold it.
 *
 * For the lobby and the Leitstelle, where the room can say what it is made of.
 * Counts only and no link to a seat: who plays which type stays with the seat,
 * and the type's own sentence stays on the round screen.
 */
export function PersonaStripList({ rows }: { rows: readonly PersonaInPlay[] }) {
  if (rows.length === 0) return null;
  return (
    <section aria-labelledby="persona-strip" className="mb-12">
      <h2 id="persona-strip" className="mb-3 text-2xl font-semibold">
        {de.host.personasInPlay.title}
      </h2>
      <ul className="max-w-(--measure-body) divide-y divide-border border-y border-border">
        {rows.map((row) => (
          <li
            key={row.id}
            className="flex items-baseline justify-between gap-6 py-2"
          >
            <span>{row.name}</span>
            <span className="font-mono text-sm text-muted-foreground">
              {de.host.personasInPlay.groups(row.groups)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The strip for a running room: it follows the roster by the seat count. */
export function PersonaStrip({
  gameId,
  seatCount,
}: {
  gameId: string;
  seatCount: number;
}) {
  const { data } = usePersonasInPlay(gameId, seatCount);
  return <PersonaStripList rows={data ?? []} />;
}
