import { createFileRoute } from "@tanstack/react-router";

import { ProtectedLayout } from "@/components/ProtectedLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { StudyIndex } from "@/components/studies/study-index";

function StudyIndexRoute() {
  return (
    <ProtectedLayout>
      <ProtectedRoute staff>
        <StudyIndex />
      </ProtectedRoute>
    </ProtectedLayout>
  );
}

export const Route = createFileRoute("/studies/")({
  component: StudyIndexRoute,
});
