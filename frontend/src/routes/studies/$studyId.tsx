import { createFileRoute, Outlet } from "@tanstack/react-router";

import { ProtectedLayout } from "@/components/ProtectedLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";

function StudyLayout() {
  return (
    <ProtectedLayout>
      <ProtectedRoute staff>
        <Outlet />
      </ProtectedRoute>
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/studies/$studyId")({
  component: StudyLayout,
});
