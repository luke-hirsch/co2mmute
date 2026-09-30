import { createFileRoute } from "@tanstack/react-router";

import { ProtectedLayout } from "@/components/ProtectedLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { MapIndex } from "@/components/map/map-index";

/**
 * `/app/maps` — a real list since S18.
 *
 * It used to be `beforeLoad: () => { throw redirect({ to: "/join" }) }`, which
 * is why "alle Karten", `/app/maps` and the landing spot after deleting a map
 * all put a logged-in host on a student's join screen. See `map-index.tsx`.
 */
function MapIndexRoute() {
  return (
    <ProtectedLayout>
      <ProtectedRoute staff>
        <MapIndex />
      </ProtectedRoute>
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/maps/")({
  component: MapIndexRoute,
});
