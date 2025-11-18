import { queryOptions } from "@tanstack/react-query";
import type { AuthResult } from "./types";
import { API_BASE_URL } from "../config";
export const authQueryOptions = queryOptions<AuthResult>({
  queryKey: ["auth"],
  queryFn: async () => {
    const res = await fetch(`${API_BASE_URL}/api/me`, {
      credentials: "include",
    });

    if (!res.ok) {
      return { user: null };
    }

    const user = await res.json();
    return { user };
  },
});
