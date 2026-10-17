import { createFileRoute } from "@tanstack/react-router";

import { CodeForm } from "@/components/join/code-form";

export const Route = createFileRoute("/join/")({
  component: CodeForm,
});
