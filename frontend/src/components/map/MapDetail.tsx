import { useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import MapViewer from "@/components/map/MapViewer";
import Loading from "@/components/Loading";
import { apiFetch } from "@/lib/api";
import { de } from "@/lib/de";
import { useGameMap, useMapGraph } from "@/lib/queries/map-graph";

/**
 * `/app/maps/<id>` — one map, for whoever draws them.
 *
 * S18 made this the page and left `MapViewer` the graph. It used to be the
 * other way round: the viewer rendered the heading, four stat panels, the SVG,
 * the detail panel and the legend, and this file bolted a bar of three coloured
 * buttons — indigo, emerald, red — on top of it. Those three were most of the
 * detail page's off-palette count on their own.
 *
 * The facts are a row of plain labelled values rather than four bordered boxes.
 * A box per number is the card grid the rulebook names as the failure mode, and
 * there is nothing to press on any of them.
 *
 * **Author and description are not shown, because the API does not have them.**
 * `GameMapSerializer` exposes `author` as a primary key, not a name, and
 * `GameMap` has no `description` column at all — so the old "Angelegt von" read
 * `undefined.username` and rendered blank, and the Django list page's
 * description block never printed anything either. Putting a host's username on
 * an endpoint anonymous readers can GET is a data decision, not a colour one;
 * it is written up in the worklog rather than taken here.
 */
const MapDetail = () => {
  const { mapId } = useParams({ from: "/maps/$mapId" });
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: gameMap,
    isLoading: mapLoading,
    error: mapError,
  } = useGameMap(mapId);
  const {
    data: mapGraph,
    isLoading: graphLoading,
    error: graphError,
  } = useMapGraph(mapId, null);

  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);

  const loadError = mapError || graphError;

  const handleExport = async () => {
    if (!gameMap) return;
    setBusy("export");
    setFailure(null);
    try {
      // The whole map since S14 — every version, the ballot between them and
      // both poll texts. It is the only way a map moves between boxes, which is
      // why it sits next to "bearbeiten" rather than behind anything.
      const data = await apiFetch(`/api/maps/${mapId}/export/`);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${gameMap.name.replace(/\s+/g, "_")}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setFailure(de.map.exportFailed);
    } finally {
      setBusy(null);
    }
  };

  /**
   * Asked in a dialog since S19, not `window.confirm`: the browser's own box
   * cannot say what stays, and what stays is the point — the games played on
   * the map keep their results (`game_map` is `SET_NULL`).
   */
  const handleDelete = async () => {
    if (!gameMap) return;
    setAsking(false);
    setBusy("delete");
    setFailure(null);
    try {
      await apiFetch(`/api/maps/${mapId}/`, { method: "DELETE" });
      queryClient.invalidateQueries({ queryKey: ["maps"] });
      navigate({ to: "/maps" });
    } catch {
      setFailure(de.map.deleteFailed);
      setBusy(null);
    }
  };

  if (mapLoading || graphLoading) {
    return (
      <Screen wide>
        <Loading label={de.map.loading} />
      </Screen>
    );
  }

  if (!gameMap) {
    return (
      <Screen>
        <Alert variant="destructive">
          <AlertDescription>
            {loadError ? de.map.loadFailed : de.editor.notFound}
          </AlertDescription>
        </Alert>
        <Button asChild variant="outline" className="mt-6">
          <Link to="/maps">{de.map.allMaps}</Link>
        </Button>
      </Screen>
    );
  }

  return (
    <Screen wide>
      <Button asChild variant="link" size="sm" className="-ml-4 mb-4">
        <Link to="/maps">{de.map.allMaps}</Link>
      </Button>

      <ScreenHeading title={gameMap.name} className="mb-8" />

      <div className="mb-10 flex flex-wrap items-center gap-3">
        <Button asChild>
          <Link to="/maps/$mapId/editor" params={{ mapId }}>
            {de.editor.editMap}
          </Link>
        </Button>
        <Button variant="outline" onClick={handleExport} disabled={busy !== null}>
          {busy === "export" ? de.map.exporting : de.editor.exportMap}
        </Button>
        <Button
          variant="destructive"
          onClick={() => setAsking(true)}
          disabled={busy !== null}
        >
          {busy === "delete" ? de.map.deleting : de.editor.deleteMap}
        </Button>
      </div>

      <Dialog open={asking} onOpenChange={setAsking}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{de.map.deleteTitle}</DialogTitle>
            <DialogDescription>{de.map.deleteBody(gameMap.name)}</DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{de.map.deleteKeeps}</p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAsking(false)}>
              {de.actions.cancel}
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              {de.map.deleteConfirm}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {failure ? (
        <Alert variant="destructive" className="mb-8">
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      ) : null}

      <dl className="mb-10 grid grid-cols-2 gap-x-8 gap-y-6 border-y py-6 sm:grid-cols-3 lg:grid-cols-6">
        <Fact label={de.editor.settings.maxPlayer} value={gameMap.max_player} />
        <Fact
          label={de.map.dimensions}
          value={`${gameMap.x_dim} × ${gameMap.y_dim}`}
        />
        <Fact
          label={de.map.created}
          value={new Date(gameMap.created).toLocaleDateString("de-DE")}
        />
        <Fact label={de.map.nodes} value={mapGraph?.node_count ?? 0} />
        <Fact label={de.map.edges} value={mapGraph?.edge_count ?? 0} />
        <Fact label={de.map.version} value={mapGraph?.version_name ?? "—"} />
      </dl>

      {mapGraph ? (
        <MapViewer gameMap={gameMap} mapGraph={mapGraph} />
      ) : (
        <Alert variant="destructive">
          <AlertDescription>
            {loadError ? de.map.loadFailed : de.map.noGraph}
          </AlertDescription>
        </Alert>
      )}
    </Screen>
  );
};

/**
 * One labelled number. Mono on the value because the rulebook reserves it for
 * ids and numerals, and a row of counts is exactly that.
 */
function Fact({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-mono text-lg">{value}</dd>
    </div>
  );
}

export default MapDetail;
