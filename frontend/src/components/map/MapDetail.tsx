import { useParams, Link, useNavigate } from "@tanstack/react-router";
import { useGameMap, useMapGraph } from "../../hooks/mapHooks";
import { API_BASE_URL } from "../../config";
import { apiFetch } from "../../utils/api";
import MapViewer from "./MapViewer";
import Loading from "../Loading";

const MapDetail = () => {
  const { mapId } = useParams({ from: "/maps/$mapId" });
  const navigate = useNavigate();
  const {
    data: gameMap,
    isLoading: mapLoading,
    error: mapError,
  } = useGameMap(mapId);
  const {
    data: mapGraph,
    isLoading: graphLoading,
    error: graphError,
  } = useMapGraph(mapId);

  const isLoading = mapLoading || graphLoading;
  const error = mapError || graphError;
  const errorMessage = error
    ? typeof error === "string"
      ? error
      : (error as any).message || "Failed to load map"
    : null;

  return (
    <div className="min-h-screen bg-linear-to-b from-body to-surface dark:from-darkbody dark:to-darksurface">
      {isLoading ? (
        <Loading />
      ) : gameMap && mapGraph ? (
        <>
          <div className="max-w-[1600px] mx-auto px-4 pt-4 flex items-center gap-4">
            <Link
              to="/maps"
              className="text-sm text-muted dark:text-darkmutedtext hover:text-main dark:hover:text-darktext"
            >
              &larr; All maps
            </Link>
            <Link
              to="/maps/$mapId/editor"
              params={{ mapId }}
              className="inline-block px-4 py-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Edit Map
            </Link>
            <button
              onClick={async () => {
                try {
                  const data = await apiFetch(
                    `${API_BASE_URL}/api/maps/${mapId}/export/`
                  );
                  const blob = new Blob([JSON.stringify(data, null, 2)], {
                    type: "application/json",
                  });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${gameMap.name.replace(/\s+/g, "_")}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch (e) {
                  console.error("Export failed:", e);
                }
              }}
              className="inline-block px-4 py-2 text-sm bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
            >
              Export JSON
            </button>
            <button
              onClick={async () => {
                if (!confirm(`Delete map "${gameMap.name}"? This cannot be undone.`)) return;
                try {
                  await apiFetch(`${API_BASE_URL}/api/maps/${mapId}/`, { method: "DELETE" });
                  navigate({ to: "/maps" });
                } catch (e) {
                  console.error("Delete failed:", e);
                }
              }}
              className="inline-block px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              Delete Map
            </button>
          </div>
          <MapViewer
            gameMap={gameMap}
            mapGraph={mapGraph}
            isLoading={false}
            error={null}
          />
        </>
      ) : errorMessage ? (
        <MapViewer
          gameMap={gameMap!}
          mapGraph={null}
          isLoading={false}
          error={errorMessage}
        />
      ) : (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-lg text-red-600 dark:text-red-400">
            Map not found
          </div>
        </div>
      )}
    </div>
  );
};

export default MapDetail;
