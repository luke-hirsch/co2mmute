import { createFileRoute } from "@tanstack/react-router";

import { ProtectedLayout } from "@/components/ProtectedLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { MapUploadScreen } from "@/components/map/map-upload";

/**
 * `/app/maps/upload` — a new map, empty or from a file. S19.
 *
 * A static segment beside `maps/$mapId`, so the router prefers it; a map whose
 * pk is "upload" cannot exist. `/map/upload/` on the Django side redirects
 * here, which keeps `base.html`'s menu pointing at one screen.
 */
function MapUploadRoute() {
  return (
    <ProtectedLayout>
      <ProtectedRoute staff>
        <MapUploadScreen />
      </ProtectedRoute>
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/maps/upload")({
  component: MapUploadRoute,
});
