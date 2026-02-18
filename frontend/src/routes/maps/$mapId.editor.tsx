import { createFileRoute } from "@tanstack/react-router";
import { ProtectedRoute } from "../../components/ProtectedRoute";
import MapEditor from "../../components/map/editor/MapEditor";

function MapEditorWrapper() {
  return (
    <ProtectedRoute staff={true}>
      <MapEditor />
    </ProtectedRoute>
  );
}

export const Route = createFileRoute("/maps/$mapId/editor")({
  component: MapEditorWrapper,
});
