import { createFileRoute } from "@tanstack/react-router";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import MapDetail from "@/components/map/MapDetail";

function MapDetailRoute() {
  return (
    <ProtectedRoute staff>
      <MapDetail />
    </ProtectedRoute>
  );
}

export const Route = createFileRoute("/maps/$mapId/")({
  component: MapDetailRoute,
});
