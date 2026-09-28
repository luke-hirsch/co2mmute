import { createFileRoute } from "@tanstack/react-router";

import { HostHomeScreen } from "@/components/host/host-home-screen";

/**
 * `/app/host` — the host's own page. S13.
 *
 * `/accounts/profile/` redirects here, which matters more than it looks:
 * Django's `LOGIN_REDIRECT_URL` defaults to that path, so this is where a host
 * lands straight after signing in.
 */
export const Route = createFileRoute("/host")({
  component: HostHomeScreen,
});
