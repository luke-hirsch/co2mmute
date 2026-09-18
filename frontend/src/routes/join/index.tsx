import { createFileRoute } from "@tanstack/react-router";

import { GameIdForm } from "@/components/join/game-id-form";

export const Route = createFileRoute("/join/")({
  component: GameIdForm,
});
