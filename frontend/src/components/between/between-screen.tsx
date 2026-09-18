import { DiscussionScreen } from "@/components/between/discussion-screen";
import { StalemateScreen } from "@/components/between/stalemate-screen";
import { StatsScreen } from "@/components/between/stats-screen";
import { VotingScreen } from "@/components/between/voting-screen";
import { useGame } from "@/components/game/game-context";

/**
 * Between two rounds, for a player.
 *
 * The phase is the router, and the phase is the backend's
 * (`GameRound.between_round_phase`): it arrives in `game.state` on every
 * connect and is moved by the phase events, each of which the reducer already
 * applies. No local step counter, no "which screen am I on" — a screen that
 * cannot disagree with the server about the phase cannot show a vote that has
 * closed.
 *
 * `none` is unreachable here: `currentScreen()` only returns `between-rounds`
 * while the phase is set, and the moment `round.started` clears it the router
 * above swaps in the round. Rendering nothing is the honest answer for the one
 * frame in which that is not yet true.
 */
export function BetweenScreen() {
  const { state } = useGame();

  switch (state.phase) {
    case "stats":
      return <StatsScreen />;
    case "discussion":
      return <DiscussionScreen />;
    case "voting":
      return <VotingScreen />;
    case "stalemate":
      return <StalemateScreen />;
    case "none":
      return null;
  }
}
