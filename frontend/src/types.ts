export type AuthResult = {
  user: null | {
    id: string;
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
