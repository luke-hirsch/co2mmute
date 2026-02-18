import { createFileRoute } from "@tanstack/react-router";
import MapDetailRoute from "../../components/map/MapDetailRoute";

function MapDetailWrapper() {
  return <MapDetailRoute />;
}

export const Route = createFileRoute("/maps/$mapId/")({
  component: MapDetailWrapper,
});
