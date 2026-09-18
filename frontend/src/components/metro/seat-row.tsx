import { de, type SeatStatus } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * One row of the lobby roster, shaped exactly like a `roster.update` player.
 *
 * Two flags that look similar and are not: `isHost` is the host's own row,
 * which never counts as a player; `controlledByHost` is a seat played at the
 * host machine because its student has no device or is out of the room (1.6).
 * A seat can be the second without being the first, and the roster sends both.
 */
export function SeatRow({
  name,
  status,
  online,
  isHost = false,
  controlledByHost = false,
  isYou = false,
  action,
  className,
}: {
  name: string;
  status: SeatStatus;
  online: boolean;
  isHost?: boolean;
  controlledByHost?: boolean;
  isYou?: boolean;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <li
      className={cn(
        // Wrapping matters on a 390px phone: the host's rows carry up to three
        // controls, and they drop under the name rather than squeezing it.
        "flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-border py-4 last:border-b-0",
        className,
      )}
    >
      {/* Presence is filled vs hollow, not green vs grey — the same language the
          round track uses for a stop that has been reached. No colour is spent
          on it, which leaves the accent free to mean "look at this". */}
      <span
        aria-hidden
        className={cn(
          "size-2.5 shrink-0 rounded-full border-2",
          online
            ? "border-foreground bg-foreground"
            : "border-strong bg-transparent dark:border-darkstrong",
        )}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className={cn("truncate", !online && "text-muted-foreground")}>
            {name}
          </span>
          {isYou ? (
            <span className="text-xs text-muted-foreground">({de.lobby.you})</span>
          ) : null}
          {isHost ? (
            <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted-foreground">
              {de.lobby.host}
            </span>
          ) : null}
          {controlledByHost ? (
            // Outlined in ink rather than a line colour: a seat played at the
            // host machine is not a transport mode, and the mode colours mean
            // one thing only.
            <span className="rounded-full border-2 border-foreground px-2 py-0.5 text-xs font-medium">
              {de.seat.atHostMachine}
            </span>
          ) : null}
        </span>
        <span className="text-xs text-muted-foreground">
          {de.seat.status[status]}
        </span>
      </div>

      {action}
    </li>
  );
}
