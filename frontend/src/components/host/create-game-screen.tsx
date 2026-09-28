import { useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
 * Fahrgäste, so it changes whenever the seats, the Fahrgäste per seat or the
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
      });
      // A full navigation rather than a router one: the response set both
      // signed cookies, and the game screen's very first request has to carry
      // them. `/app/game/<id>/` is inside the SPA either way.
      window.location.assign(`/app/game/${game.game_id}/`);
    } catch (failure) {
      setErrors(fieldErrors(failure));
    }
  }

  return (
    <Screen>
      <ScreenHeading title={de.create.title} lead={de.create.lead} />

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

      <form onSubmit={submit} noValidate className="space-y-12">
        {/*
          The same two-column rhythm as the sections below, so a text input is
          about as wide as a line of text rather than as wide as the page. The
          checkbox spans both because its help text is a sentence.
        */}
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
            {selected && !selected.offers_map_changes ? (
              <p className="mt-2 max-w-(--measure-body) text-sm text-brandaccent">
                {de.create.mapNoChanges}
              </p>
            ) : null}
          </Field>

          <label className="flex max-w-(--measure-body) items-start gap-3 sm:col-span-2">
            <input
              type="checkbox"
              name="map_updates"
              checked={mapUpdates}
              onChange={(event) => setMapUpdates(event.target.checked)}
              className="mt-1 size-4 accent-primary"
            />
            <span>
              <span className="text-sm font-medium">{de.create.mapUpdates}</span>
              <span className="mt-1 block text-sm text-muted-foreground">
                {de.create.mapUpdatesHelp}
              </span>
            </span>
          </label>
        </section>

        <section className="space-y-6">
          <h2 className="text-2xl font-medium">{de.create.classSize}</h2>
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
          </div>
        </section>

        <section className="space-y-6">
          <h2 className="text-2xl font-medium">{de.create.game}</h2>
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
          </div>
        </section>

        <section className="space-y-6">
          <div>
            <h2 className="text-2xl font-medium">{de.create.derived}</h2>
            <p className="mt-2 max-w-(--measure-body) text-muted-foreground">
              {de.create.derivedLead}
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2">
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

function Field({
  id,
  label,
  help,
  errors,
  children,
}: {
  id: string;
  label: string;
  help?: string;
  errors?: string[];
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {help ? (
        <p
          id={`${id}-help`}
          className="max-w-(--measure-body) text-sm text-muted-foreground"
        >
          {help}
        </p>
      ) : null}
      {errors?.length ? (
        // `role="alert"` so a screen reader hears the refusal when it appears,
        // and `id` so the input can point at it — both of which also make it
        // something a test can find without pinning the sentence.
        <ul id={`${id}-error`} role="alert" className="space-y-1">
          {errors.map((message) => (
            <li key={message} className="text-sm text-destructive">
              {message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

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
