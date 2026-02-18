import { createFileRoute, Outlet } from "@tanstack/react-router";
import { ProtectedLayout } from "../../components/ProtectedLayout";

function MapDetailLayout() {
  return (
    <ProtectedLayout>
      <Outlet />
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/maps/$mapId")({
  component: MapDetailLayout,
});
