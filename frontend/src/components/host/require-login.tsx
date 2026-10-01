import { useEffect, type ReactNode } from "react";

import { useIdentity } from "@/lib/queries/identity";

/**
 * Keeps the host's own screens behind a login.
 *
 * `/game/create/` on Django is `LoginRequiredMixin`, but the SPA route under
 * `/app/game/create` is reachable by URL, and an anonymous visitor there got
 * the whole form and a map list the server refuses to serve. The credential
 * flows stay on Django, so an anonymous visitor is sent there with `next`
 * pointing back — a full navigation, not a router one.
 *
 * Renders nothing until the answer is in, so the form never flashes.
 */
export function RequireLogin({ children }: { children: ReactNode }) {
  const identity = useIdentity();
  const loggedIn =
    identity.data?.kind === "host" || identity.data?.kind === "user";
  const anonymous = identity.isSuccess && !loggedIn;

  useEffect(() => {
    if (!anonymous) return;
    const next = encodeURIComponent(
      window.location.pathname + window.location.search,
    );
    window.location.replace(`/accounts/login/?next=${next}`);
  }, [anonymous]);

  return loggedIn ? <>{children}</> : null;
}
