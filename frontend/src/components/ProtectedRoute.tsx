import { useEffect, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";

import Loading from "./Loading";
import { useAuth } from "../context/AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredKind?: string | string[];
  fallbackTo?: string;
  loadingComponent?: ReactNode;
  staff?: boolean;
}

/**
 * Keeps a screen behind whatever it is behind.
 *
 * ### The staff gate did not gate anything
 *
 * It read:
 *
 * ```
 * if (staff !== undefined && isStaff !== staff)
 *   if (!isAuthorized) { navigate(...); return null; }
 * ```
 *
 * — two `if`s where one `||` was meant. With `staff` and no `requiredKind`,
 * which is how both callers use it, `isAuthorized` is unconditionally `true`, so
 * the inner branch could never run and **no visitor was ever turned away**. The
 * map detail page and the editor were open to any logged-in account. Nothing
 * leaked: `IsStaffOrReadOnly` refuses every write, so a non-staff user got a
 * read-only editor whose every button failed. But it was a guard that had never
 * once fired, which is the same class of thing as `Player.is_muted` having no
 * reader — see S9.
 *
 * ### The redirect moved into an effect
 *
 * Navigating during render is a state update during render. It was harmless
 * only because the branch was dead; making the condition true would have made
 * it real. `ProtectedLayout` still does it and is left alone — its condition
 * works, and that file is the layout half of S20's header work.
 */
export function ProtectedRoute({
  children,
  requiredKind,
  staff,
  fallbackTo = "/",
  loadingComponent = <Loading />,
}: ProtectedRouteProps) {
  const { isLoading, isStaff, hasKind } = useAuth();
  const navigate = useNavigate();

  const kindOk = requiredKind ? hasKind(requiredKind) : true;
  const staffOk = staff === undefined || isStaff === staff;
  const allowed = kindOk && staffOk;

  useEffect(() => {
    if (!isLoading && !allowed) {
      navigate({ to: fallbackTo });
    }
  }, [isLoading, allowed, fallbackTo, navigate]);

  if (isLoading) return <>{loadingComponent}</>;
  if (!allowed) return null;

  return <>{children}</>;
}
