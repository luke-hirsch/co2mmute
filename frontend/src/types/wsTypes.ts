export interface WSPingMessage {
  type: "ping";
}

export interface WSPongMessage {
  type: "pong";
}

export interface WSLobbyRosterMessage {
  type: "lobby.roster";
  game_id: string;
  players: WSPlayer[];
}

export interface WSPlayer {
  playerId: string;
  name: string;
  isMuted: boolean;
  controlledByHost: boolean;
  online: boolean;
  joinedAt: string;
}

export interface WSOptions {
  onOpen?: () => void;
  onClose?: (ev: CloseEvent) => void;
  onError?: (ev: Event) => void;
  onMessage?: (data: any) => void;
}

export type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";

export interface WSClientConfig {
  maxReconnectAttempts?: number;
  initialReconnectDelay?: number; // milliseconds
  maxReconnectDelay?: number; // milliseconds
  heartbeatInterval?: number; // milliseconds
}

// Union types for easier type guarding in handlers
export type WSLobbyMessage = WSPingMessage | WSLobbyRosterMessage;

export interface WSChatMessagePayload {
  ts: number;
  playerName: string;
  message: string;
}

export interface WSChatHistoryMessage {
  type: "chat.history";
  game_id: string;
  messages: WSChatMessagePayload[];
}

export interface WSChatIncomingMessage {
  type: "chat.message";
  game_id: string;
  message: WSChatMessagePayload;
}

export interface WSChatErrorMessage {
  type: "chat.error";
  error: string;
}

export interface WSChatOutgoingMessage {
  type: "chat.message";
  message: string;
}

export type WSChatMessage =
  | WSPingMessage
  | WSChatHistoryMessage
  | WSChatIncomingMessage
  | WSChatErrorMessage;
