import type { AuthKind, MessageType } from "./types";

export interface Auth {
  kind: AuthKind;
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
}

export interface Message {
  show: boolean;
  msg: string;
  type: MessageType;
  onClose?: () => void;
}

export interface ChatMessage {
  id: string;
  authorId: string;
  content: string;
  timestamp: number;
}

export interface Player {
  id: string;
  name: string;
  playerId: string;
  user?: number;
  game: string;
  joinedAt: string;
  isMuted: boolean;
}

export interface WSOptions {
  onOpen?: () => void;
  onClose?: (ev: CloseEvent) => void;
  onError?: (ev: Event) => void;
  onMessage?: (data: any) => void;
}
