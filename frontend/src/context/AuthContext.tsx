//libs

//types

import { createContext } from "react";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return <AuthContext.Provider value={null}>{children}</AuthContext.Provider>;
};

export const AuthContext = createContext<any>(undefined);
