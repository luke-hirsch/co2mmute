import { useNavigate } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import type { ReactNode } from "react";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredKind?: string | string[];
  fallbackTo?: string;
  loadingComponent?: ReactNode;
}

/**
 * Protects a route based on auth kind
 * @param children - Component to render if authorized
 * @param requiredKind - Single kind or array of kinds allowed to access
 * @param fallbackTo - Route to redirect to if not authorized (default: "/")
 * @param loadingComponent - Component to show while loading auth
 */
export function ProtectedRoute({
  children,
  requiredKind,
  fallbackTo = "/",
  loadingComponent = <div>Loading...</div>,
}: ProtectedRouteProps) {
  const { isLoading, hasKind } = useAuth();
  const navigate = useNavigate();

  if (isLoading) {
    return <>{loadingComponent}</>;
  }

  const isAuthorized = requiredKind ? hasKind(requiredKind) : true;

  if (!isAuthorized) {
    navigate({ to: fallbackTo });
    return null;
  }

  return <>{children}</>;
}
