/**
 * What the header and footer offer — `GET api/navigation/`.
 *
 * The list is built once, in `backend/co2mmute/navigation.py`, and `base.html`
 * renders the same dictionary. The SPA used to carry its own header with its
 * own idea of what belongs in it, and it disagreed with the Django one about
 * almost everything: which items, who sees the map menu, whether there is a way
 * to sign out. So this side renders what it is given and decides nothing —
 * including who counts as staff, which is the server's to say.
 *
 * Signing in and out are Django pages and reload the document, so the answer
 * only goes stale on a rename, which `useSaveAccount` invalidates.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

/** A link, a menu (`children`), or — from the CMS — a label with nowhere to go. */
export type NavItem = {
  id: string;
  label: string;
  href?: string | null;
  children?: NavItem[];
};

export type Navigation = {
  header: NavItem[];
  footer: NavItem[];
  /** The profile, labelled with the username; null for anyone not signed in. */
  account: NavItem | null;
  /** Abmelden or Anmelden. */
  session: NavItem;
};

export const navigationKeys = {
  all: () => ["navigation"] as const,
};

export function useNavigation() {
  return useQuery({
    queryKey: navigationKeys.all(),
    queryFn: () => apiFetch<Navigation>("/api/navigation/"),
    staleTime: 60_000,
    retry: false,
  });
}
