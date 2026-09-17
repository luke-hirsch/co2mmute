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
        "flex items-center gap-4 border-b border-border py-4 last:border-b-0",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "size-2.5 shrink-0 rounded-full",
          online ? "bg-success-500" : "bg-strong dark:bg-darkstrong",
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
            <span className="rounded-full border-2 border-mode-car px-2 py-0.5 text-xs font-medium">
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
