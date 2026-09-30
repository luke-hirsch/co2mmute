import { Link } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import Loading from "@/components/Loading";
import { useAuth } from "@/context/AuthContext";
import { de } from "@/lib/de";
import { useGameMaps } from "@/lib/queries/map-graph";
import type { GameMap } from "@/types/mapTypes";

/**
 * `/app/maps` — the maps there are.
 *
 * ### The three bugs this one screen closes
 *
 * `routes/maps/index.tsx` was a stub that threw `redirect({ to: "/join" })`,
 * under a comment promising "F7 gives the editor a real index". F7 never did,
 * and S10's click-through found the consequences separately without seeing that
 * they were one cause:
 *
 * - "Alle Karten" on the detail page bounced a logged-in host onto a student's
 *   join screen,
 * - `/app/maps` was not a list,
 * - and deleting a map landed you there too.
 *
 * The `Importing a module script failed` in his notes is the same line: the
 * redirect has to fetch the join chunk, and when that fails the router surfaces
 * the loader error rather than the screen.
 *
 * ### It replaces a Django page
 *
 * `/map/list/` has been the staff map list since before the SPA. That template
 * is gone and its URL redirects here, which also retires a page that was still
 * in English — "Maps", "Upload Map", "Manage and view all game maps", "By",
 * "No description" — and that printed a description field `GameMap` does not
 * have.
 *
 * ### What a row says
 *
 * What a host actually decides on. **`offers_map_changes` is the one that
 * matters**: a map whose base version reaches no compatible version removes the
 * discussion, the vote and the map change from the whole game, silently. The
 * create screen says so at the select; this says it a step earlier, where the
 * map is made.
 */
export function MapIndex() {
  const { isStaff } = useAuth();
  const { data: maps, isLoading, isError } = useGameMaps();

  return (
    <Screen>
      <ScreenHeading title={de.map.index.title} lead={de.map.index.lead} />

      {isStaff ? (
        <div className="mb-10">
          {/* Django's, and it stays there until S19 brings the upload across. */}
          <Button asChild>
            <a href="/map/upload/">{de.map.index.upload}</a>
          </Button>
        </div>
      ) : null}

      {isLoading ? <Loading label={de.map.index.loading} /> : null}

      {isError ? (
        <Alert variant="destructive">
          <AlertDescription>{de.map.index.failed}</AlertDescription>
        </Alert>
      ) : null}

      {maps && maps.length === 0 ? (
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.map.index.empty}
        </p>
      ) : null}

      {maps && maps.length > 0 ? (
        <ul className="divide-y divide-border border-y">
          {maps.map((gameMap) => (
            <MapRow key={gameMap.id} gameMap={gameMap} isStaff={isStaff} />
          ))}
        </ul>
      ) : null}
    </Screen>
  );
}

function MapRow({ gameMap, isStaff }: { gameMap: GameMap; isStaff: boolean }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4 py-5">
      <div>
        <h2 className="text-lg">
          <Link
            to="/maps/$mapId"
            params={{ mapId: String(gameMap.id) }}
            className="underline-offset-4 hover:underline"
          >
            {gameMap.name}
          </Link>
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {de.map.index.size(gameMap.x_dim, gameMap.y_dim)}
          {" · "}
          {de.map.index.seats(gameMap.max_player)}
          {" · "}
          {de.map.index.commuters(gameMap.district_commuters)}
        </p>
        <div className="mt-2">
          {/* Outline both ways round: this is a property of the map, not good
              news or bad news, and the palette has no ramp to say which. */}
          <Badge variant="outline">
            {gameMap.offers_map_changes
              ? de.map.index.votable
              : de.map.index.noVote}
          </Badge>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline" size="sm">
          <Link to="/maps/$mapId" params={{ mapId: String(gameMap.id) }}>
            {de.map.index.open}
          </Link>
        </Button>
        {isStaff ? (
          <Button asChild size="sm">
            <Link
              to="/maps/$mapId/editor"
              params={{ mapId: String(gameMap.id) }}
            >
              {de.editor.editMap}
            </Link>
          </Button>
        ) : null}
      </div>
    </li>
  );
}
