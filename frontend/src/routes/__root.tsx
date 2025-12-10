import { Outlet, createRootRoute } from "@tanstack/react-router";
import BaseLayout from "../layouts/baseLayout";

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  return (
    <BaseLayout>
      <Outlet />
    </BaseLayout>
  );
}
