import { createFileRoute } from "@tanstack/react-router";
import RedirectToJoin from "../utils/RedirectToJoin";

export const Route = createFileRoute("/")({
  component: RedirectToJoin,
});
