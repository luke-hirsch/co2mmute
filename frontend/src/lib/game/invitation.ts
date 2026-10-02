import { de } from "@/lib/de";

/**
 * The invitation the lobby's share button copies (F3), for a class that is not
 * in front of the projector: a link straight to the join screen, the id for
 * whoever types it on the landing page instead, and the password when the game
 * has one — the three things the projector shows.
 *
 * The link is built from the page's own origin, not served: it is what
 * `GameSession.join_url` says on a box whose `DJANGO_BASE_URL` is right, and on
 * one where it is not, it is still the address the host is looking at.
 */
export function joinUrl(origin: string, gameId: string): string {
  return `${origin}/app/join/${gameId}`;
}

export function invitationText({
  gameName,
  gameId,
  url,
  password,
}: {
  gameName: string;
  gameId: string;
  url: string;
  password: string | null | undefined;
}): string {
  const lines = [
    de.host.invitation.intro(gameName),
    url,
    de.host.invitation.gameId(gameId),
  ];
  if (password) lines.push(de.host.invitation.password(password));
  return lines.join("\n");
}
