import { Button } from "@/components/ui/button";
import { Screen } from "@/components/layout/screen";
import { de } from "@/lib/de";

/**
 * The covered step between two seats (H-04).
 *
 * The host machine is usually on a projector, so handing it to the next student
 * cannot go straight from one turn to the next: the room would see the previous
 * player's routes, and the next player would see them before choosing. This
 * screen stands in between and shows one name and one button.
 *
 * It renders *instead of* the turn, not over it — nothing of the seat behind it
 * is mounted, so there is nothing to flash, no z-index to get wrong and no
 * scroll position to leak.
 */
export function Curtain({
  name,
  onReady,
  onCancel,
}: {
  name: string;
  onReady: () => void;
  onCancel: () => void;
}) {
  return (
    <Screen narrow>
      <div className="flex min-h-[50vh] flex-col justify-center">
        <p className="font-mono text-xs tracking-[0.2em] text-muted-foreground uppercase">
          {de.code.boarding}
        </p>
        <h1 className="mt-4 text-4xl font-medium hyphens-auto sm:text-5xl">
          {de.host.curtainTitle(name)}
        </h1>
        <p className="mt-6 max-w-(--measure-body) text-muted-foreground">
          {de.host.curtainBody}
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Button size="lg" onClick={onReady}>
            {de.host.curtainGo}
          </Button>
          <Button variant="ghost" onClick={onCancel}>
            {de.actions.back}
          </Button>
        </div>
      </div>
    </Screen>
  );
}
