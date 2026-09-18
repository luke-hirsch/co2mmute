import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * `/app/` has nothing of its own to show. Someone who lands here either
 * bookmarked the SPA root or scanned a QR code that lost its game id, and the
 * only useful thing to offer them is the id field.
 *
 * Until F1 this jumped out of the SPA to Django's `/join` with a full page
 * load. It stays inside the router now — same screen, no round trip.
 */
export const Route = createFileRoute("/")({
  beforeLoad: () => {
    throw redirect({ to: "/join" });
  },
});
