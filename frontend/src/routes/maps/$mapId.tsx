import { createFileRoute, Outlet } from "@tanstack/react-router";

import { ProtectedLayout } from "@/components/ProtectedLayout";

function MapLayout() {
  return (
    <ProtectedLayout>
      <Outlet />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/maps/$mapId")({
  component: MapLayout,
});
