import { createFileRoute } from "@tanstack/react-router";

import { StudyPage } from "@/components/studies/study-page";

function StudyRoute() {
  const { studyId } = Route.useParams();
  return <StudyPage studyId={Number(studyId)} />;
}

export const Route = createFileRoute("/studies/$studyId/")({
  component: StudyRoute,
});
