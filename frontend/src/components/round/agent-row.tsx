import { Button } from "@/components/ui/button";
import { ModeBadge } from "@/components/metro/line";
import { ModePicker, OptimizationRow } from "@/components/round/mode-picker";
import { RouteSummary } from "@/components/round/route-summary";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import type { AgentDraft } from "@/lib/game/round-draft";
import type { Node } from "@/types/mapTypes";
import type { CarOptimization, PTOptimization, TransportMode } from "@/types/routeTypes";

/**
 * One passenger's leg of the turn: where they are going, how, and what that
 * costs them.
 *
 * A row in a ruled list, not a card — the same idiom as `SeatRow` in the lobby.
 * A wall of cards is what the rulebook names as the default-layout failure, and
 * on a 390px phone three cards are three boxes of wasted edge.
 *
 * Collapsed once a route is found: the picker only stays open while there is a
 * decision to make. With three passengers and four modes, leaving every picker
 * open is a screen nobody can find the submit button on.
 */
export function AgentRow({
  index,
  agent,
  nodes,
  selected,
  onSelect,
  onPickMode,
  onPickCarOptimization,
  onPickPtOptimization,
  onClear,
  onRetry,
  disabled = false,
}: {
  index: number;
  agent: AgentDraft;
  nodes: Map<number, Node>;
  selected: boolean;
  onSelect: () => void;
  onPickMode: (mode: TransportMode) => void;
  onPickCarOptimization: (optimization: CarOptimization) => void;
  onPickPtOptimization: (optimization: PTOptimization) => void;
  onClear: () => void;
  onRetry: () => void;
  disabled?: boolean;
}) {
  const destination = nodes.get(agent.destinationNode)?.name;
  const done = agent.status === "ready" && agent.route;

  return (
    <li
      className={cn(
        "border-b border-border py-6 last:border-b-0",
        selected && "bg-muted/40",
      )}
    >
      <div className="flex items-start gap-4">
        {/* Filled once this passenger has a route — the same "presence is fill,
            not colour" language the roster and the track use. */}
        <span
          aria-hidden
          className={cn(
            "mt-[0.35lh] size-2.5 shrink-0 rounded-full border-2",
            done
              ? "border-foreground bg-foreground"
              : "border-strong bg-transparent dark:border-darkstrong",
          )}
        />

        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={onSelect}
            className="text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <p className="font-medium">{de.round.agent(index + 1)}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {de.round.home} → {destination ?? `#${agent.destinationNode}`}
            </p>
          </button>

          <div className="mt-4">
            {done ? (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <ModeBadge mode={agent.mode!} />
                <RouteSummary route={agent.route!} />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClear}
                  disabled={disabled}
                  className="ml-auto"
                >
                  {de.round.change}
                </Button>
              </div>
            ) : (
              <ModePicker
                value={agent.mode}
                onPick={onPickMode}
                disabled={disabled}
              />
            )}

            {agent.status === "routing" ? (
              <p className="mt-3 text-sm text-muted-foreground">{de.round.routing}</p>
            ) : null}

            {agent.status === "failed" ? (
              // Attention is the accent, and there is no red anywhere in this
              // interface. The line above it says what to do next.
              <div className="mt-3 border-l-[3px] border-brandaccent pl-4">
                <p className="max-w-(--measure-body) text-sm">{de.round.noRoute}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onRetry}
                  disabled={disabled}
                  className="mt-1 -ml-3"
                >
                  {de.round.routeAgain}
                </Button>
              </div>
            ) : null}

            {/* The alternatives, once a mode is picked and the default route is
                already on screen. */}
            {agent.mode === "car" && agent.status !== "routing" ? (
              <OptimizationRow
                options={de.round.carOptimization}
                value={agent.carOptimization}
                onPick={onPickCarOptimization}
                disabled={disabled}
              />
            ) : null}
            {agent.mode === "public" && agent.status !== "routing" ? (
              <OptimizationRow
                options={de.round.ptOptimization}
                value={agent.ptOptimization}
                onPick={onPickPtOptimization}
                disabled={disabled}
              />
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
}
