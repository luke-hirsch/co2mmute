import { useNavigate } from "@tanstack/react-router";
import { AuthProvider, useAuth } from "../context/AuthContext";
import type { ReactNode } from "react";

interface ProtectedLayoutProps {
  children: ReactNode;
  gameId?: string;
  requiredKind?: string | string[];
  fallbackTo?: string;
  loadingComponent?: ReactNode;
}

/**
 * Combines AuthProvider + route protection in one component
 * Handles both auth context setup and access control
 */
export function ProtectedLayout({
  children,
  gameId,
  requiredKind,
  fallbackTo = "/",
  loadingComponent = <div>Loading...</div>,
}: ProtectedLayoutProps) {
  return (
    <AuthProvider gameId={gameId}>
      <ProtectedRouteGuard
        requiredKind={requiredKind}
        fallbackTo={fallbackTo}
        loadingComponent={loadingComponent}
      >
        {children}
      </ProtectedRouteGuard>
    </AuthProvider>
  );
}

/**
 * Inner component that uses auth context
 * Must be inside AuthProvider
 */
function ProtectedRouteGuard({
  children,
  requiredKind,
  fallbackTo,
  loadingComponent,
}: Omit<ProtectedLayoutProps, "gameId">) {
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
