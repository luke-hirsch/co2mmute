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

export interface WSLatencyMetrics {
  current: number; // ms, last ping/pong latency
  min: number; // ms, best latency seen
  max: number; // ms, worst latency seen
  average: number; // ms, rolling average
}

export interface WSConnectionQuality {
  signalStrength: 0 | 1 | 2 | 3 | 4 | 5; // 0 = no signal, 5 = excellent
  latency: WSLatencyMetrics;
  reconnectAttempts: number;
  status: WSStatus;
}

// Union types for easier type guarding in handlers
export type WSLobbyMessage =
  | WSPingMessage
  | WSPongMessage
  | WSLobbyRosterMessage;

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

export interface WSChatSystemMessage {
  type: "chat.system";
  game_id: string;
  message: string;
}

export interface WSChatOutgoingMessage {
  type: "chat.message";
  message: string;
}

export type WSChatMessage =
  | WSPingMessage
  | WSPongMessage
  | WSChatHistoryMessage
  | WSChatIncomingMessage
  | WSChatErrorMessage
  | WSChatSystemMessage;

// Game State WebSocket Messages
export interface WSGameStateUpdate {
  type: "gamestate.update";
  game: WSGameState;
  stats: WSGameStats;
}

export interface WSGameState {
  game_id: string;
  game_name: string;
  is_active: boolean;
  ended_at: string | null;
  max_rounds: number;
  max_co2: number;
  current_round: number;
  round_status: "pending" | "active" | "completed";
  chat_enabled: boolean;
}

export interface WSGameStats {
  totalCo2: number;
  maxCo2: number;
  co2Percentage: number;
  players: WSPlayerStats[];
}

export interface WSPlayerStats {
  playerId: string;
  name: string;
  co2: number;
  moveCount: number;
}

export type WSGameStateMessage =
  | WSPingMessage
  | WSPongMessage
  | WSGameStateUpdate;
