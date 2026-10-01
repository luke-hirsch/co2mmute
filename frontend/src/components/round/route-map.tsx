import GameMapViewer from "@/components/game/GameMapViewer";
import { de } from "@/lib/de";
import type { SearchTrace } from "@/lib/map/search-trace";
import type { EdgeLoad } from "@/lib/map/traffic";
import type { AgentDraft } from "@/lib/game/round-draft";
import type { ExtendedMapGraph } from "@/types/routeTypes";

/**
 * The map, with one passenger's route drawn on it and last round's traffic
 * under it.
 *
 * A thin wrapper on purpose: the round screen talks to a small surface — graph,
 * selected agent, jam — instead of the renderer's whole prop set, and there is
 * one place to change when the renderer is replaced.
 */
export function RouteMap({
  graph,
  homeNode,
  agent,
  jam,
  search,
  isLoading = false,
  hint = true,
}: {
  graph: ExtendedMapGraph | null;
  homeNode: number | null;
  agent: AgentDraft | null;
  /** Where it stopped last round, drawn as stroke weight. */
  jam?: EdgeLoad[];
  /** What the router looked at for this route; played once, then gone. */
  search?: SearchTrace | null;
  isLoading?: boolean;
  /** Off once the turn is sent — there is nothing left to tap. */
  hint?: boolean;
}) {
  return (
    <section aria-label={de.round.mapTitle}>
      <GameMapViewer
        mapGraph={graph}
        isLoading={isLoading}
        compact
        homeNodeId={homeNode ?? undefined}
        destinationNodeId={agent?.destinationNode}
        routeSegments={agent?.route?.segments}
        jam={jam}
        search={search}
      />
      {hint ? (
        <p className="mt-3 text-sm text-muted-foreground">{de.round.mapHint}</p>
      ) : null}
    </section>
  );
}
