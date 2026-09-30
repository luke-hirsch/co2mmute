/**
 * The host's own account — the three fields they may change themselves.
 *
 * `GET`/`PATCH api/account/` always means the requesting user: there is no pk
 * in the path and none is accepted. Password and account deletion are not here
 * and deliberately so — both are credential flows with a re-authentication
 * step, and they stay on Django's own pages (the host machine stands in a
 * classroom, often projected and often still logged in).
 *
 * `whoami` also answers with a username and cannot be used instead: it is the
 * identity question, cached per game and shared with every screen, and writing
 * an account through it would make one cache entry mean two things.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { navigationKeys } from "@/lib/queries/navigation";

export type HostAccount = {
  first_name: string;
  username: string;
  email: string;
};

export const accountKeys = {
  self: () => ["account"] as const,
};

export function useAccount() {
  return useQuery({
    queryKey: accountKeys.self(),
    queryFn: () => apiFetch<HostAccount>("/api/account/"),
    staleTime: 60_000,
    retry: false,
  });
}

export function useSaveAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: HostAccount) =>
      apiFetch<HostAccount>("/api/account/", {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (saved) => {
      client.setQueryData(accountKeys.self(), saved);
      // The header greets the host by username (from `api/navigation/`), and
      // `whoami` answers with it too. A rename that leaves the old name in the
      // corner of every screen until the next full page load looks like the
      // save did not take.
      client.invalidateQueries({ queryKey: ["identity"] });
      client.invalidateQueries({ queryKey: navigationKeys.all() });
    },
  });
}
