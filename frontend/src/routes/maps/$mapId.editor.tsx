import { createFileRoute } from "@tanstack/react-router";
import { ProtectedLayout } from "../../components/ProtectedLayout";
import { ProtectedRoute } from "../../components/ProtectedRoute";
import MapEditor from "../../components/map/editor/MapEditor";

function MapEditorWrapper() {
  return (
    <ProtectedLayout>
      <ProtectedRoute staff={true}>
        <MapEditor />
      </ProtectedRoute>
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/maps/$mapId/editor")({
  component: MapEditorWrapper,
});
