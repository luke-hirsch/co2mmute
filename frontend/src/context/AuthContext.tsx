//libs
import {
  createContext,
  useContext,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";

//types
import type { Auth } from "../types/types";
import { useSession } from "../utils/useSession";

interface AuthContextType {
  auth: Auth | undefined;
  isLoading: boolean;
  isError: boolean;
  isAuthenticated: boolean;
  isHost: boolean;
  isPlayer: boolean;
  isUser: boolean;
  isStaff: boolean;
  hasKind: (kind: string | string[]) => boolean;
  refetch: () => void;
}

export const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);

interface AuthProviderProps {
  children: ReactNode;
  gameId?: string;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({
  children,
  gameId,
}) => {
  const { data: auth, isLoading, isError, refetch } = useSession(gameId);

  const isAuthenticated = useMemo(() => auth?.authenticated ?? false, [auth]);

  const isHost = useMemo(() => auth?.kind === "host", [auth]);

  const isPlayer = useMemo(() => auth?.kind === "player", [auth]);

  const isUser = useMemo(() => auth?.kind === "user", [auth]);

  const isStaff = useMemo(() => (auth?.isStaff ? true : false), [auth]);

  const hasKind = useCallback(
    (kind: string | string[]) => {
      if (!auth) return false;
      const kinds = Array.isArray(kind) ? kind : [kind];
      return kinds.includes(auth.kind);
    },
    [auth]
  );

  const value: AuthContextType = useMemo(
    () => ({
      auth,
      isLoading,
      isError,
      isAuthenticated,
      isHost,
      isPlayer,
      isUser,
      isStaff,
      hasKind,
      refetch: () => refetch(),
    }),
    [
      auth,
      isLoading,
      isError,
      isAuthenticated,
      isHost,
      isPlayer,
      isUser,
      isStaff,
      hasKind,
      refetch,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
