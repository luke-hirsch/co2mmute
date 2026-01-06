import { createFileRoute } from "@tanstack/react-router";
import MapListRoute from "../../components/map/MapListRoute";

export const Route = createFileRoute("/maps/")({
  component: MapListRoute,
});
