export type AuthKind = "host" | "user" | "player" | "anonymous";

export type MessageType = "info" | "success" | "error" | "warning";

export interface AgentAssignment {
  id: number;
  destination_node: number;
}

export interface PlayerAgentAssignments {
  home_node: number;
  agents: AgentAssignment[];
}

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
