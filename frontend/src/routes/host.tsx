import { createFileRoute } from "@tanstack/react-router";

import { HostHomeScreen } from "@/components/host/host-home-screen";
import { RequireLogin } from "@/components/host/require-login";

/**
 * `/app/host` — the host's own page. S13.
 *
 * `/accounts/profile/` redirects here, which matters more than it looks:
 * Django's `LOGIN_REDIRECT_URL` defaults to that path, so this is where a host
 * lands straight after signing in.
 */
function HostRoute() {
  return (
    <RequireLogin>
      <HostHomeScreen />
    </RequireLogin>
  );
}

export const Route = createFileRoute("/host")({
  component: HostRoute,
});
