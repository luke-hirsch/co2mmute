import { useParams } from "@tanstack/react-router";
import { useGameMap, useMapGraph } from "../../hooks/mapHooks";
import MapViewer from "./MapViewer";
import Loading from "../Loading";

const MapDetail = () => {
  const { mapId } = useParams({ from: "/maps/$mapId" });
  const { data: gameMap, isLoading: mapLoading } = useGameMap(mapId);
  const { data: mapGraph, isLoading: graphLoading } = useMapGraph(mapId);

  const isLoading = mapLoading || graphLoading;

  return (
    <div className="min-h-screen bg-linear-to-b from-body to-surface dark:from-darkbody dark:to-darksurface">
      {isLoading ? (
        <Loading />
      ) : gameMap && mapGraph ? (
        <MapViewer gameMap={gameMap} mapGraph={mapGraph} />
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
