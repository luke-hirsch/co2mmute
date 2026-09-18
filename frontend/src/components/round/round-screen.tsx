import { useMemo, useState } from "react";

import { AgentRow } from "@/components/round/agent-row";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { HandOverPanel } from "@/components/seat/hand-over-panel";
import { RoundHeader } from "@/components/round/round-header";
import { RouteMap } from "@/components/round/route-map";
import { Screen } from "@/components/layout/screen";
import { SubmittedPanel } from "@/components/round/submitted-panel";
import { useGame } from "@/components/game/game-context";
import { useRoundDraft } from "@/hooks/use-round-draft";
import { useSubmitMove } from "@/lib/queries/move";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { de } from "@/lib/de";
import { seatById } from "@/lib/game/game-state";
import type { Node } from "@/types/mapTypes";

/**
 * The turn.
 *
 * Reads the game from the provider in the layout — no socket, no polling, no
 * refetch of its own. What it adds is one seat's draft (`useRoundDraft`) and
 * the one request that ends the turn.
 *
 * **Parameterised by seat.** The player's route passes their own `player_id`
 * from `whoami`; F4's desk passes a host-controlled seat's, and nothing below
 * cares which it got. The backend allows both — `IsPlayerInGame` has had the
 * host branch since 1.6, and it is narrow: only a seat that is actually played
 * at the host machine.
 *
 * `desk` is what tells the two apart on screen. With it the seat belongs to
 * somebody else and the screen says whose and offers the way back; without it
 * the seat is this device's own, and it may be moved to another one.
 *
 * Whether this seat has already submitted is **not** state here: it is
 * `seat.status === "waiting"` from the roster. That is what makes a reload
 * mid-round land on the right screen (R-11), and it is also what takes the desk
 * back to its list the moment a turn is sent.
 *
 * **No chat on this screen yet.** The chat is `ChatSidebar` + `useChatSocket`,
 * both pre-rewrite: it needs the legacy `AuthProvider`, expects to sit in a
 * sized `<aside>`, and paints its status in green and amber, which this palette
 * does not have. Wiring that into the screen F4 and F5 are built on would copy
 * all three forward, so the chat gets its own small chunk instead. Between
 * rounds the legacy screen still has it.
 */
export function RoundScreen({
  seatId,
  desk,
}: {
  seatId: string | null;
  /** Set when the host desk plays this seat: whose it is, and the way back. */
  desk?: { name: string; onLeave: () => void };
}) {
  const { state } = useGame();
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);

  const draft = useRoundDraft({
    gameId: state.gameId,
    seatId,
    roundNumber: state.currentRound,
  });
  const submit = useSubmitMove(state.gameId, seatId);

  const seat = seatById(state, seatId);
  const submitted = seat?.status === "waiting";
  const paused = !!state.pausedAt;

  // Node lookup for the destination names. A Map because a 55-node graph gets
  // scanned once per agent per render otherwise.
  const nodes = useMemo(() => {
    const byId = new Map<number, Node>();
    for (const node of draft.graph?.nodes ?? []) byId.set(node.id, node);
    return byId;
  }, [draft.graph]);

  const selected =
    draft.draft.agents.find((agent) => agent.agentId === selectedAgentId) ??
    draft.draft.agents.find((agent) => agent.status === "ready") ??
    draft.draft.agents[0] ??
    null;

  const handleSubmit = () => {
    if (!draft.payload) return;
    submit.mutate(draft.payload);
  };

  if (draft.isLoading) {
    return (
      <Screen>
        <p className="text-muted-foreground">{de.app.loading}</p>
      </Screen>
    );
  }

  if (!draft.hasAssignment) {
    return (
      <Screen narrow>
        <RoundHeader />
        <Alert>
          <AlertDescription>{de.round.noAssignment}</AlertDescription>
        </Alert>
        {desk ? <SeatBar seatName={desk.name} onLeave={desk.onLeave} /> : null}
      </Screen>
    );
  }

  return (
    <Screen>
      <RoundHeader />

      {desk ? (
        <SeatBar seatName={desk.name} onLeave={desk.onLeave} className="mb-10" />
      ) : seatId ? (
        <div className="mb-10 flex justify-end">
          <HandOverPanel gameId={state.gameId} seatId={seatId} />
        </div>
      ) : null}

      <div className="mb-12">
        <RouteMap
          graph={draft.graph}
          homeNode={draft.draft.homeNode}
          agent={selected}
        />
      </div>

      {submitted ? (
        <SubmittedPanel />
      ) : (
        <>
          <section>
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
              <h2 className="text-2xl font-semibold">{de.round.agents}</h2>
              <p className="font-mono text-sm tabular-nums text-muted-foreground">
                {de.round.chosenOf(draft.progress.done, draft.progress.total)}
              </p>
            </div>

            <ul className="mt-4">
              {draft.draft.agents.map((agent, index) => (
                <AgentRow
                  key={agent.agentId}
                  index={index}
                  agent={agent}
                  nodes={nodes}
                  selected={selected?.agentId === agent.agentId}
                  onSelect={() => setSelectedAgentId(agent.agentId)}
                  onPickMode={(mode) => {
                    setSelectedAgentId(agent.agentId);
                    draft.pickMode(agent.agentId, mode);
                  }}
                  onPickCarOptimization={(optimization) =>
                    draft.pickCarOptimization(agent.agentId, optimization)
                  }
                  onPickPtOptimization={(optimization) =>
                    draft.pickPtOptimization(agent.agentId, optimization)
                  }
                  onClear={() => draft.clearAgent(agent.agentId)}
                  onRetry={() => void draft.retry(agent.agentId)}
                  disabled={paused || submit.isPending}
                />
              ))}
            </ul>
          </section>

          {submit.error ? (
            <Alert variant="destructive" className="mt-8">
              <AlertDescription>{submitFailure(submit.error)}</AlertDescription>
            </Alert>
          ) : null}

          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Button
              size="lg"
              onClick={handleSubmit}
              disabled={!draft.complete || paused || submit.isPending}
            >
              {submit.isPending ? de.round.submitting : de.round.submit}
            </Button>
            {!draft.complete ? (
              <p className="text-sm text-muted-foreground">
                {de.round.submitBlocked}
              </p>
            ) : null}
          </div>
        </>
      )}
    </Screen>
  );
}

/**
 * Whose turn this is, when it is not the reader's own (F4).
 *
 * At the desk the machine is passed around, so the screen has to name the seat
 * it is playing — and always offer the way out, because a student may sit down
 * and then not want to submit yet. Without it the only way back to the list
 * would be finishing somebody else's turn for them.
 */
function SeatBar({
  seatName,
  onLeave,
  className,
}: {
  seatName: string;
  onLeave: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border pb-4",
        className,
      )}
    >
      <p className="font-medium">{de.host.playingSeat(seatName)}</p>
      <Button variant="outline" size="sm" onClick={onLeave}>
        {de.host.back}
      </Button>
    </div>
  );
}

/**
 * Why the move bounced, in words that say what to do next.
 *
 * The statuses carry the meaning (`game/views_rest.py`), which is why
 * `apiFetch` keeps them: 409 `paused` is the bell, and the old screen showed
 * "Netzwerkfehler" for it.
 */
function submitFailure(error: unknown): string {
  if (!(error instanceof ApiError)) return de.round.failedUnknown;
  if (error.status === 409 && error.reason === "paused")
    return de.round.failedPaused;
  if (error.status === 403) return de.round.failedSeat;
  if (error.status === 400 && /active round/i.test(error.message)) {
    return de.round.failedRoundOver;
  }
  // A validation failure names an agent and a node; that is for us, not for a
  // 13-year-old. The generic line plus a retry is the honest answer.
  return de.round.failedUnknown;
}
