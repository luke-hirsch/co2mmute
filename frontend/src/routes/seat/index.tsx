import { createFileRoute } from "@tanstack/react-router";

import { SeatCodeForm } from "@/components/seat/seat-code-form";

export const Route = createFileRoute("/seat/")({
  component: SeatCodeForm,
});
