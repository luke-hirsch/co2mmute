import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/layout/field";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { apiErrorMessage, ApiError } from "@/lib/api";
import {
  DEFAULT_AGENT_PER_PLAYER,
  DEFAULT_MAX_PLAYERS,
  DEFAULT_MAX_ROUNDS,
  co2BudgetKg,
  peoplePerAgent,
} from "@/lib/calibration";
import { de } from "@/lib/de";
import { useCreateGame } from "@/lib/queries/session";
import { useGameMaps, type GameMapRow } from "@/lib/queries/maps";

/**
 * Spiel anlegen. S13, and the reason the screen moved off Django at all.
 *
 * `people_per_agent` divides the map's commuter population between the
 * Gruppen, so it changes whenever the seats, the Gruppen per seat or the
 * map change; `max_CO2_level` is the map's per-round budget times the rounds.
 * A server-rendered form derives both once per GET, which meant a host who
 * changed the Platzzahl had to pull both numbers across by hand
 * (`docs/testfaelle.md` H-13). Here they follow.
 *
 * **Each of the two is one piece of state, not two.** What the field shows is
 * `override ?? derived` — an override is set the moment the host types in the
 * field and cleared by "Vorschlag übernehmen". Nothing writes the derived value
 * *into* the form state, so there is no effect to fight, no moment where the
 * two disagree, and no way for a re-render to undo a host's own number. That is
 * the same rule the round draft and the lobby roster are built on: one source of
 * truth per field.
 *
 * Validation is the server's. The endpoint's messages are German
 * (`GameSessionSerializer`) and the fields render what comes back, so no rule is
 * worded twice — the alternative is a client copy that drifts, which is exactly
 * what the map-editor strings did.
 */
export function CreateGameScreen() {
  const maps = useGameMaps();
  const create = useCreateGame();

  const [gameName, setGameName] = useState("");
  const [gamePassword, setGamePassword] = useState("");
  const [mapId, setMapId] = useState<number | null>(null);
  const [mapUpdates, setMapUpdates] = useState(true);
  const [maxPlayers, setMaxPlayers] = useState(String(DEFAULT_MAX_PLAYERS));
  const [agentPerPlayer, setAgentPerPlayer] = useState(
    String(DEFAULT_AGENT_PER_PLAYER),
  );
  const [maxRounds, setMaxRounds] = useState(String(DEFAULT_MAX_ROUNDS));
  const [idleEndDays, setIdleEndDays] = useState("30");
  const [chatEnabled, setChatEnabled] = useState(true);
  /**
   * "Weitere Einstellungen" is closed until the host opens it — or until the
   * server refuses a field inside it, which a closed disclosure would hide.
   */
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [co2Override, setCo2Override] = useState<string | null>(null);
  const [peopleOverride, setPeopleOverride] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  const rows = maps.data ?? [];
  /**
   * The first map until the host picks another — the Django select had
   * `empty_label=None` for the same reason: "---------" is what lets somebody
   * create a game with no map without noticing, and a mapless game can never be
   * started. `mapId` stays null only while the list is in flight.
   */
  const selected: GameMapRow | null =
    rows.find((row) => row.id === mapId) ?? rows[0] ?? null;

  const derivedPeople = useMemo(
    () =>
      selected
        ? peoplePerAgent(Number(maxPlayers), Number(agentPerPlayer), selected)
        : null,
    [selected, maxPlayers, agentPerPlayer],
  );
  const derivedCo2 = useMemo(
    () => (selected ? co2BudgetKg(Number(maxRounds), selected) : null),
    [selected, maxRounds],
  );

  const peopleValue = peopleOverride ?? (derivedPeople?.toString() ?? "");
  const co2Value = co2Override ?? (derivedCo2?.toString() ?? "");

  const agentCount =
    Math.max(1, Math.trunc(Number(maxPlayers)) || 0) *
    Math.max(1, Math.trunc(Number(agentPerPlayer)) || 0);

  /**
   * The one message that is not under a field.
   *
   * A 400 names its fields and those render beside them; anything else — a
   * dropped connection, a 403, a refusal with only a `detail` — has nowhere
   * else to go. `de.create.failed` is the last resort rather than the first:
   * the endpoint's own German sentence is better copy than "versuch es
   * nochmal" whenever there is one.
   */
  const fieldNames = Object.keys(errors).filter(
    (name) => name !== "non_field_errors" && name !== "detail",
  );
  const formLevelError =
    errors.non_field_errors?.join(" ") ??
    errors.detail?.join(" ") ??
    (create.isError && fieldNames.length === 0 ? de.create.failed : null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setErrors({});
    try {
      const game = await create.mutateAsync({
        game_name: gameName.trim(),
        game_password: gamePassword.trim(),
        game_map: selected.id,
        map_updates: mapUpdates,
        max_players: Number(maxPlayers),
        agent_per_player: Number(agentPerPlayer),
        max_rounds: Number(maxRounds),
        max_CO2_level: Number(co2Value),
        people_per_agent: Number(peopleValue),
        idle_end_days: Number(idleEndDays),
        chat_enabled: chatEnabled,
      });
      // A full navigation rather than a router one: the response set both
      // signed cookies, and the game screen's very first request has to carry
      // them. `/app/game/<id>/` is inside the SPA either way.
      window.location.assign(`/app/game/${game.game_id}/`);
    } catch (failure) {
      const next = fieldErrors(failure);
      setErrors(next);
      if (ADVANCED_FIELDS.some((name) => next[name])) setAdvancedOpen(true);
    }
  }

  return (
    <Screen>
      <ScreenHeading title={de.create.title} />

      {maps.isError ? (
        <Alert variant="destructive" className="mb-8">
          <AlertDescription>{de.create.mapFailed}</AlertDescription>
        </Alert>
      ) : null}
      {maps.isSuccess && rows.length === 0 ? (
        <Alert className="mb-8">
          <AlertDescription>{de.create.mapNone}</AlertDescription>
        </Alert>
      ) : null}

      {/*
        S21's grouping, which is Lukas's: what the game is, then the numbers
        that decide how many people are on the map, then the two that decide
        when it ends, then what a first game never needs. Every group is the
        same two-column grid and nothing in it is wider than a column or the
        whole of it — text at a third width, between the two, was what made
        the old "Gerechnet" paragraph read as a mistake.

        Each derived number sits in the group of the numbers it is derived
        from, after them, so the host reads cause before effect.
      */}
      <form onSubmit={submit} noValidate className="space-y-12">
        <section className="grid gap-6 sm:grid-cols-2">
          <Field
            id="game_name"
            label={de.create.name}
            errors={errors.game_name}
          >
            <Input
              id="game_name"
              value={gameName}
              onChange={(event) => setGameName(event.target.value)}
              placeholder={de.create.namePlaceholder}
              autoComplete="off"
              maxLength={100}
              autoFocus
              aria-invalid={errors.game_name ? true : undefined}
            />
          </Field>

          <Field
            id="game_password"
            label={de.create.password}
            help={de.create.passwordHelp}
            errors={errors.game_password}
          >
            <Input
              id="game_password"
              value={gamePassword}
              onChange={(event) => setGamePassword(event.target.value)}
              placeholder={de.create.passwordPlaceholder}
              autoComplete="off"
              maxLength={50}
            />
          </Field>

          <Field id="game_map" label={de.create.map} errors={errors.game_map}>
            <select
              id="game_map"
              name="game_map"
              className={selectClass}
              value={selected?.id ?? ""}
              disabled={maps.isPending || rows.length === 0}
              onChange={(event) => setMapId(Number(event.target.value))}
            >
              {maps.isPending ? (
                <option value="">{de.create.mapLoading}</option>
              ) : null}
              {rows.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
            {/*
              Both notes are about the map, so both sit under the select and
              appear the moment a host picks it — the uncalibrated one names
              the two fields further down rather than repeating itself there.
              Ink with an accent rule, not amber text: the accent is a signage
              colour and three lines of it on the page ground are hard to read.
            */}
            {selected && !selected.calibrated ? (
              <p className={mapNoteClass}>
                {de.create.mapUncalibrated}
              </p>
            ) : null}
            {selected && !selected.offers_map_changes ? (
              <p className={mapNoteClass}>
                {de.create.mapNoChanges}
              </p>
            ) : null}
          </Field>

          <CheckField
            id="map_updates"
            label={de.create.mapUpdates}
            help={de.create.mapUpdatesHelp}
            checked={mapUpdates}
            onChange={setMapUpdates}
            errors={errors.map_updates}
          />
        </section>

        <section className="space-y-6">
          <h2 className="text-2xl font-medium">{de.create.groupPeople}</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <Field
              id="max_players"
              label={de.create.maxPlayers}
              help={de.create.maxPlayersHelp}
              errors={errors.max_players}
            >
              <NumberInput
                id="max_players"
                value={maxPlayers}
                onChange={setMaxPlayers}
                invalid={!!errors.max_players}
              />
            </Field>
            <Field
              id="agent_per_player"
              label={de.create.agentPerPlayer}
              help={de.create.agentPerPlayerHelp}
              errors={errors.agent_per_player}
            >
              <NumberInput
                id="agent_per_player"
                value={agentPerPlayer}
                onChange={setAgentPerPlayer}
                invalid={!!errors.agent_per_player}
              />
            </Field>
            <Field
              id="people_per_agent"
              label={de.create.peoplePerAgent}
              help={
                selected
                  ? de.create.peoplePerAgentHelp(
                      selected.district_commuters,
                      agentCount,
                    )
                  : undefined
              }
              errors={errors.people_per_agent}
            >
              <NumberInput
                id="people_per_agent"
                value={peopleValue}
                onChange={setPeopleOverride}
                invalid={!!errors.people_per_agent}
              />
              <Suggestion
                overridden={peopleOverride !== null}
                onReset={() => setPeopleOverride(null)}
              />
            </Field>
          </div>
        </section>

        <section className="space-y-6">
          <h2 className="text-2xl font-medium">{de.create.groupEnd}</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <Field
              id="max_rounds"
              label={de.create.maxRounds}
              help={de.create.maxRoundsHelp}
              errors={errors.max_rounds}
            >
              <NumberInput
                id="max_rounds"
                value={maxRounds}
                onChange={setMaxRounds}
                invalid={!!errors.max_rounds}
              />
            </Field>
            <Field
              id="max_CO2_level"
              label={de.create.co2Budget}
              help={
                selected
                  ? de.create.co2BudgetHelp(
                      selected.co2_budget_kg_per_round,
                      Math.max(1, Math.trunc(Number(maxRounds)) || 0),
                    )
                  : undefined
              }
              errors={errors.max_CO2_level}
            >
              <NumberInput
                id="max_CO2_level"
                value={co2Value}
                onChange={setCo2Override}
                invalid={!!errors.max_CO2_level}
              />
              <Suggestion
                overridden={co2Override !== null}
                onReset={() => setCo2Override(null)}
              />
            </Field>
          </div>
        </section>

        {/*
          A native disclosure: keyboard and screen reader behaviour for free,
          and the fields inside are still in the form when it is closed, so
          what the host never opened is sent at its default.
        */}
        <details
          open={advancedOpen}
          onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
          className="group"
        >
          <summary className="inline-flex cursor-pointer list-none items-center gap-2 rounded-md [&::-webkit-details-marker]:hidden">
            <h2 className="text-2xl font-medium">{de.create.advanced}</h2>
            <ChevronDown
              aria-hidden="true"
              className="size-6 text-muted-foreground transition-transform group-open:rotate-180"
            />
          </summary>
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <Field
              id="idle_end_days"
              label={de.create.idleEndDays}
              help={de.create.idleEndDaysHelp}
              errors={errors.idle_end_days}
            >
              <NumberInput
                id="idle_end_days"
                value={idleEndDays}
                onChange={setIdleEndDays}
                invalid={!!errors.idle_end_days}
              />
            </Field>
            <CheckField
              id="chat_enabled"
              label={de.create.chat}
              help={de.create.chatHelp}
              checked={chatEnabled}
              onChange={setChatEnabled}
              errors={errors.chat_enabled}
            />
          </div>
        </details>

        {formLevelError ? (
          <Alert variant="destructive">
            <AlertDescription>{formLevelError}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex items-center gap-4">
          <Button
            type="submit"
            size="lg"
            disabled={create.isPending || !selected}
          >
            {create.isPending ? de.create.submitting : de.create.submit}
          </Button>
        </div>
      </form>
    </Screen>
  );
}

const mapNoteClass = "border-l-2 border-brandaccent pl-3 text-sm";

/** The fields inside "Weitere Einstellungen", which opens when one is refused. */
const ADVANCED_FIELDS = ["idle_end_days", "chat_enabled"] as const;

/**
 * The map select. A native `<select>`, not the radix one that is also in the
 * bundle: on a phone this opens the platform picker, which is the control a
 * class of students already knows — and WebKit is the engine that matters here.
 */
const selectClass =
  "h-10 w-full min-w-0 rounded-md border border-input bg-transparent px-3 py-1 " +
  "text-base shadow-xs outline-none transition-[color,box-shadow] md:text-sm " +
  "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 " +
  "disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30";

/**
 * `inputMode="numeric"` rather than `type="number"`: the numeric keypad without
 * the spinner, whose scroll-to-change behaviour is a way to alter a CO₂ budget
 * by accident. The value stays a string so the field can be empty while it is
 * being retyped; the endpoint gets a number.
 */
function NumberInput({
  id,
  value,
  onChange,
  invalid,
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  invalid?: boolean;
}) {
  return (
    <Input
      id={id}
      name={id}
      value={value}
      inputMode="numeric"
      autoComplete="off"
      className="font-mono"
      aria-invalid={invalid ? true : undefined}
      aria-describedby={invalid ? `${id}-error` : `${id}-help`}
      onChange={(event) => onChange(event.target.value.replace(/[^\d]/g, ""))}
    />
  );
}

/**
 * A switch, shaped like every other field: its name as the label on top, then
 * a control as tall as an input, then the help. So it lines up with the field
 * beside it in the grid rather than floating as a sentence of its own width —
 * which the old "Kartenänderungen zulassen" did, at a measure that was neither
 * a column nor the grid.
 *
 * Both labels point at the box, so a tap on the word beside it toggles it.
 */
function CheckField({
  id,
  label,
  help,
  checked,
  onChange,
  errors,
}: {
  id: string;
  label: string;
  help: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  errors?: string[];
}) {
  return (
    <Field id={id} label={label} help={help} errors={errors}>
      <div className="flex h-10 items-center gap-3">
        <input
          id={id}
          name={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          aria-describedby={errors?.length ? `${id}-error` : `${id}-help`}
          className="size-4 accent-primary"
        />
        <label htmlFor={id} className="text-sm">
          {de.create.allow}
        </label>
      </div>
    </Field>
  );
}

/** Says a derived number has been taken over, and offers it back. */
function Suggestion({
  overridden,
  onReset,
}: {
  overridden: boolean;
  onReset: () => void;
}) {
  if (!overridden) return null;
  return (
    <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      {de.create.overridden}
      <button
        type="button"
        onClick={onReset}
        className="underline underline-offset-4 hover:text-foreground"
      >
        {de.create.reset}
      </button>
    </p>
  );
}

/**
 * DRF's 400 body is `{field: [message, ...]}`, and anything else is not a field
 * error — a 403 carries `{"detail": ...}`, a network failure carries nothing.
 * Both end up under the form rather than beside a field.
 */
function fieldErrors(failure: unknown): Record<string, string[]> {
  if (!(failure instanceof ApiError)) return {};
  const body = failure.body;
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    const message = apiErrorMessage(body);
    return message ? { non_field_errors: [message] } : {};
  }
  const out: Record<string, string[]> = {};
  for (const [field, value] of Object.entries(body)) {
    out[field] = Array.isArray(value) ? value.map(String) : [String(value)];
  }
  return out;
}
