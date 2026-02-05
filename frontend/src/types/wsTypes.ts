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

// Player status for game roster
export type PlayerStatus = "ready" | "making_move" | "waiting" | "not_connected";

export interface WSRosterPlayer {
  player_id: string;
  name: string;
  is_host: boolean;
  controlled_by_host: boolean;
  online: boolean;
  status: PlayerStatus;
}

export interface WSRosterUpdateMessage {
  type: "roster.update";
  game_id: string;
  players: WSRosterPlayer[];
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

// Game State WebSocket Messages (from GameConsumer)

// Player stats for a single round
export interface WSPlayerRoundStats {
  player_id: string;
  player_name: string;
  action: "car" | "public" | "bike" | "walk";
  emissions_g: number;
  cost_eur: number;
  time_min: number;
}

// game.started event
export interface WSGameStartedMessage {
  type: "game.started";
  game_id: string;
  data: {
    game_name: string;
    max_rounds: number;
    max_co2_level: number;
    current_round: number;
    started_at: string | null;
  };
}

// game.ended event
export interface WSGameEndedMessage {
  type: "game.ended";
  game_id: string;
  data: {
    reason: "co2_limit" | "max_rounds";
    final_round: number;
    total_emissions_g: number;
    max_co2_level_g: number;
    ended_at: string | null;
  };
}

// round.started event
export interface WSRoundStartedMessage {
  type: "round.started";
  game_id: string;
  data: {
    round_number: number;
    max_rounds: number;
    total_game_emissions_g: number;
    max_co2_level_g: number;
  };
}

// round.completed event
export interface WSRoundCompletedMessage {
  type: "round.completed";
  game_id: string;
  data: {
    round_number: number;
    round_emissions_g: number;
    round_cost_eur: number;
    total_game_emissions_g: number;
    max_co2_level_g: number;
    player_stats: WSPlayerRoundStats[];
  };
}

// game.state event (sent on reconnect to sync client state)
export interface WSGameStateInitMessage {
  type: "game.state";
  game_id: string;
  data: {
    isActive: boolean;
    currentRound: number;
    totalEmissionsG: number;
    maxCo2LevelG: number;
    maxRounds: number;
    startedAt: string | null;
    endedAt: string | null;
  };
}

// Union type for all game state messages
export type WSGameStateMessage =
  | WSPingMessage
  | WSPongMessage
  | WSGameStartedMessage
  | WSGameEndedMessage
  | WSRoundStartedMessage
  | WSRoundCompletedMessage
  | WSRosterUpdateMessage
  | WSGameStateInitMessage;

// Combined game state for UI consumption
export interface WSGameState {
  gameId: string;
  gameName: string;
  isActive: boolean;
  endedAt: string | null;
  endReason: "co2_limit" | "max_rounds" | null;
  maxRounds: number;
  maxCo2LevelG: number;
  currentRound: number;
  totalEmissionsG: number;
  lastRoundStats: WSPlayerRoundStats[] | null;
  roster: WSRosterPlayer[];
}
