export interface Player {
  id: string;
  name: string;
  playerId: string;
  user?: number;
  game: string;
  joinedAt: string;
  isMuted: boolean;
  controlledByHost: boolean;
}
