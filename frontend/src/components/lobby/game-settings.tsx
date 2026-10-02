import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";
import { useSetChat } from "@/lib/queries/session";

/**
 * What this game was set up as: agents, rounds and the CO2 budget.
 *
 * Shared by the player's lobby and the host's, because it is the same three
 * numbers and they are read off the same snapshot. The host sees them for the
 * same reason the players do — it is the last chance to notice that the CO₂
 * budget is wrong before a round is played on it.
 *
 * The host's copy has one control in it, the chat (F3): the create form could
 * switch it, the lobby could only say which way it was set.
 */
export function GameSettings({ host = false }: { host?: boolean }) {
  const { state } = useGame();

  return (
    <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
      <Setting
        label={de.lobby.settings.agentsPerPlayer}
        value={state.agentPerPlayer}
      />
      <Setting
        label={de.lobby.settings.maxRounds}
        value={de.lobby.roundsCount(state.maxRounds)}
      />
      <Setting
        label={de.lobby.settings.co2Budget}
        value={de.lobby.co2Kg(state.maxCo2LevelKg)}
      />
      {/*
        Back as of S8. This row was removed in F5 because the chat had died
        with the legacy screen and it went on promising "Chat — an" for a
        feature with no way to reach it. `ChatDock` is that way, so the promise
        is true again — and it has to be kept true: if the chat is ever
        switched off again, this row goes with it.
      */}
      <Setting
        label={de.lobby.settings.chat}
        value={
          host ? (
            <ChatSwitch />
          ) : state.chatEnabled ? (
            de.lobby.settings.chatOn
          ) : (
            de.lobby.settings.chatOff
          )
        }
        mono={false}
      />
    </dl>
  );
}

/**
 * `mono` defaults to true because most of these are numbers, and mono is what
 * the rulebook reserves for ids, codes and numerals. A word like "an" is none
 * of those, so it opts out rather than pretending to be a figure.
 */
function Setting({
  label,
  value,
  mono = true,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="border-t border-border pt-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={mono ? "mt-1 font-mono" : "mt-1"}>{value}</dd>
    </div>
  );
}

/**
 * The chat, on or off, for the host. What it shows is the room's state, which
 * `game.chat` sets for every screen at once; while the PATCH is in flight it
 * shows what was asked for, so the box does not jump back for a moment.
 */
function ChatSwitch() {
  const { state } = useGame();
  const setChat = useSetChat(state.gameId);
  const checked = setChat.isPending
    ? (setChat.variables ?? state.chatEnabled)
    : state.chatEnabled;

  return (
    <div>
      <div className="flex items-center gap-3">
        <input
          id="lobby-chat"
          type="checkbox"
          checked={checked}
          disabled={setChat.isPending}
          onChange={(event) => setChat.mutate(event.target.checked)}
          className="size-4 accent-primary"
        />
        <label htmlFor="lobby-chat">{de.lobby.settings.chatOn}</label>
      </div>
      {setChat.isError ? (
        <p className="mt-2 text-sm text-destructive">{de.host.chatFailed}</p>
      ) : null}
    </div>
  );
}
