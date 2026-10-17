import { createFileRoute } from "@tanstack/react-router";

import { StudyCards } from "@/components/studies/study-cards";

function StudyCardsRoute() {
  const { studyId } = Route.useParams();
  return <StudyCards studyId={Number(studyId)} />;
}

export const Route = createFileRoute("/studies/$studyId/karten")({
  component: StudyCardsRoute,
});
