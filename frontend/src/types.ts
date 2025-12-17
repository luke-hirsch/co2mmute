export type Auth = {
  kind: "user" | "player" | "anonymous";
  authenticated: boolean;
  id?: number;
  isStaff?: boolean;
  isActive?: boolean;
  username?: string;
  email?: string;
  firstName?: string;
  lastName?: string;
  detail?: string;
  gameId?: string;
  player?: {
    playerId: string;
    name: string;
  };
};

export type Message = {
  show: boolean;
  msg: string;
  type: "info" | "success" | "error" | "warning";
  onClose?: () => void;
};

export type ChatMessage = {
  id: string;
  authorId: string;
  content: string;
  timestamp: number;
};

export type Player = {
  id: string;
  name: string;
  playerId: string;
  user?: number;
  game: string;
  joinedAt: string;
  isMuted: boolean;
};

export type WSOptions = {
  onOpen?: () => void;
  onClose?: (ev: CloseEvent) => void;
  onError?: (ev: Event) => void;
  onMessage?: (data: any) => void;
};
