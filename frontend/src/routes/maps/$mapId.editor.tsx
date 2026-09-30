import { createFileRoute } from "@tanstack/react-router";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import MapEditor from "@/components/map/editor/MapEditor";

function MapEditorRoute() {
  return (
    <ProtectedRoute staff>
      <MapEditor />
    </ProtectedRoute>
  );
}

export const Route = createFileRoute("/maps/$mapId/editor")({
  component: MapEditorRoute,
});
