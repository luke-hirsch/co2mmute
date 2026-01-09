import { createFileRoute } from "@tanstack/react-router";
import { ProtectedLayout } from "../../components/ProtectedLayout";
import MapDetailRoute from "../../components/map/MapDetailRoute";

function MapDetailWrapper() {
  return (
    <ProtectedLayout>
      <MapDetailRoute />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/maps/$mapId")({
  component: MapDetailWrapper,
});
