import { createFileRoute } from "@tanstack/react-router";
import MapDetailRoute from "../../components/map/MapDetailRoute";

export const Route = createFileRoute("/maps/$mapId")({
  component: MapDetailRoute,
});
