import GameMapViewer from "@/components/game/GameMapViewer";
import { de } from "@/lib/de";
import type { AgentDraft } from "@/lib/game/round-draft";
import type { ExtendedMapGraph } from "@/types/routeTypes";

/**
 * The map, with one passenger's route drawn on it.
 *
 * A thin wrapper on purpose. `GameMapViewer` is the cytoscape renderer and it
 * works; porting or redesigning it is not this chunk (Roadmap.md: the editor is
 * F7, and "nur portieren"). This exists so the round screen talks to a small
 * surface — graph plus the selected agent — instead of thirteen optional props,
 * and so there is exactly one place to change when the renderer is replaced.
 */
export function RouteMap({
  graph,
  homeNode,
  agent,
  isLoading = false,
  hint = true,
}: {
  graph: ExtendedMapGraph | null;
  homeNode: number | null;
  agent: AgentDraft | null;
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
        showRouteLegend={false}
      />
      {hint ? (
        <p className="mt-3 text-sm text-muted-foreground">{de.round.mapHint}</p>
      ) : null}
    </section>
  );
}
