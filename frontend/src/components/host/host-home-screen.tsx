import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import { hostGameState } from "@/lib/host-game-state";
import {
  useAccount,
  useSaveAccount,
  type HostAccount,
} from "@/lib/queries/account";
import {
  useDeleteGame,
  useHostGames,
  type HostGameRow,
} from "@/lib/queries/host-games";

/**
 * `/app/host` — the host's own page. S13.
 *
 * It replaces `/accounts/profile/`, a Django template that listed the games and
 * carried a `ProfileForm`. Both followed the create form across because the
 * host's own pages belong together (Lukas, 2026-09-28), and both are things
 * that change while you look at them: a game ends, a name turns out to be taken.
 *
 * Two things stayed on Django and are linked out to, not embedded: changing the
 * password and deleting the account. Both re-authenticate, and the host machine
 * stands in a classroom, often projected and often still logged in — that
 * password prompt is the guard.
 *
 * **The game list is the one screen in the SPA with no socket.** Nothing
 * broadcasts "a game was deleted", so there is no second source of truth to
 * race with, and invalidating after a mutation is the right shape here rather
 * than the anti-pattern it would be on a game screen.
 */
export function HostHomeScreen() {
  const games = useHostGames();
  const account = useAccount();

  return (
    <Screen>
      <ScreenHeading
        title={de.hostHome.greeting(
          account.data?.first_name || account.data?.username || "",
        )}
        lead={de.hostHome.lead}
      />

      <div className="grid gap-12 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start">
        <section>
          <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
            <h2 className="text-2xl font-medium">{de.hostHome.games}</h2>
            <Button asChild>
              <a href="/game/create/">{de.hostHome.newGame}</a>
            </Button>
          </div>

          {games.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{de.hostHome.gamesFailed}</AlertDescription>
            </Alert>
          ) : null}

          {games.isSuccess && games.data.length === 0 ? (
            <p className="max-w-(--measure-body) text-muted-foreground">
              {de.hostHome.noGames}
            </p>
          ) : null}

          <ul className="divide-y divide-border">
            {(games.data ?? []).map((game) => (
              <GameRow key={game.game_id} game={game} />
            ))}
          </ul>
        </section>

        <aside className="space-y-10">
          <AccountPanel />
          <section>
            <h2 className="text-2xl font-medium">{de.hostHome.deleteAccount}</h2>
            <p className="mt-3 max-w-(--measure-body) text-sm text-muted-foreground">
              {de.hostHome.deleteAccountBody}
            </p>
            <Button asChild variant="outline" className="mt-4 w-full">
              <a href="/accounts/profile/delete/">{de.hostHome.deleteAccount}</a>
            </Button>
          </section>
        </aside>
      </div>
    </Screen>
  );
}

function GameRow({ game }: { game: HostGameRow }) {
  const [asking, setAsking] = useState(false);

  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4 py-5">
      <div>
        <h3 className="text-lg">{game.game_name}</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {de.hostHome.gameId}{" "}
          <span className="font-mono tracking-widest uppercase">
            {game.game_id}
          </span>
          {" · "}
          {hostGameState(game)}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {de.hostHome.rounds(game.round_count)}
          {" · "}
          {de.hostHome.players(game.player_count)}
          {" · "}
          {de.hostHome.createdAt(
            new Date(game.created_at).toLocaleDateString("de-DE"),
          )}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="outline" size="sm">
          <a href={`/app/game/${game.game_id}/`}>{de.hostHome.open}</a>
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setAsking(true)}>
          {de.hostHome.delete}
        </Button>
      </div>

      <DeleteDialog game={game} open={asking} onOpenChange={setAsking} />
    </li>
  );
}

/**
 * Asks before deleting, and names what goes with it.
 *
 * "Alle Daten" is not something anybody can weigh, which is why the confirm
 * page it replaces counted the rounds and the seats — a game is CASCADE all the
 * way down, and every round on it is thesis data.
 */
function DeleteDialog({
  game,
  open,
  onOpenChange,
}: {
  game: HostGameRow;
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const remove = useDeleteGame();

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) remove.reset();
  }

  const refusedRunning =
    remove.error instanceof ApiError &&
    remove.error.status === 409 &&
    remove.error.reason === "running";

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{de.hostHome.deleteTitle}</DialogTitle>
          <DialogDescription>
            {de.hostHome.deleteBody(game.game_name)}
          </DialogDescription>
        </DialogHeader>

        <p className="text-sm text-muted-foreground">
          {de.hostHome.deleteTakes(game.round_count, game.player_count)}
        </p>
        <p className="text-sm text-muted-foreground">
          {de.hostHome.deleteWarning}
        </p>

        {remove.isError ? (
          <Alert variant="destructive">
            <AlertDescription>
              {refusedRunning
                ? de.hostHome.deleteRunning
                : de.hostHome.deleteFailed}
            </AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {de.hostHome.deleteCancel}
          </Button>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={async () => {
              try {
                await remove.mutateAsync(game.game_id);
                close(false);
              } catch {
                // The alert above says which refusal it was. The dialog stays
                // open so the host can read it beside the game it is about.
              }
            }}
          >
            {remove.isPending
              ? de.hostHome.deleting
              : de.hostHome.deleteConfirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The three fields a host may change about themselves.
 *
 * Validation is the server's, and two of its rules — is this name taken, is
 * this address taken — are ones the screen could not check anyway. Its messages
 * are German and render under the field they name, so nothing is worded twice.
 *
 * **The form only exists once the account has arrived**, and that is not a
 * loading nicety. The first version rendered the fields immediately and seeded
 * them from an effect when the query resolved — so anything typed in that
 * window was silently overwritten by the fetched value, and pressing Speichern
 * then saved what was already there. A host would have seen "Gespeichert." over
 * a change that never happened. Mounting the form with the data as its initial
 * state removes the effect, the guard flag and the race together.
 */
function AccountPanel() {
  const account = useAccount();

  return (
    <section>
      <h2 className="text-2xl font-medium">{de.hostHome.account}</h2>
      <p className="mt-3 max-w-(--measure-body) text-sm text-muted-foreground">
        {de.hostHome.accountLead}
      </p>

      {account.isError ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{de.hostHome.accountFailed}</AlertDescription>
        </Alert>
      ) : null}

      {account.data ? <AccountForm account={account.data} /> : null}

      <Button asChild variant="outline" className="mt-4 w-full">
        <a href="/accounts/password_change/">{de.hostHome.changePassword}</a>
      </Button>
    </section>
  );
}

function AccountForm({ account }: { account: HostAccount }) {
  const save = useSaveAccount();
  // The account as it was when this form opened. React Query re-delivers the
  // same object on a refocus; nothing here listens, so a half-typed name
  // survives one.
  const [form, setForm] = useState<HostAccount>(account);
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setErrors({});
    try {
      await save.mutateAsync(form);
    } catch (failure) {
      setErrors(fieldErrors(failure));
    }
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 space-y-5">
      <AccountField
        id="first_name"
        label={de.hostHome.firstName}
        help={de.hostHome.firstNameHelp}
        value={form.first_name}
        onChange={(next) => setForm({ ...form, first_name: next })}
        errors={errors.first_name}
      />
      <AccountField
        id="username"
        label={de.hostHome.username}
        value={form.username}
        onChange={(next) => setForm({ ...form, username: next })}
        errors={errors.username}
      />
      <AccountField
        id="email"
        label={de.hostHome.email}
        type="email"
        value={form.email}
        onChange={(next) => setForm({ ...form, email: next })}
        errors={errors.email}
      />

      {save.isSuccess && !save.isPending && Object.keys(errors).length === 0 ? (
        <p className="text-sm text-muted-foreground">{de.hostHome.saved}</p>
      ) : null}
      {errors.non_field_errors || errors.detail ? (
        <Alert variant="destructive">
          <AlertDescription>
            {(errors.non_field_errors ?? errors.detail).join(" ")}
          </AlertDescription>
        </Alert>
      ) : null}

      <Button type="submit" className="w-full" disabled={save.isPending}>
        {save.isPending ? de.hostHome.saving : de.hostHome.save}
      </Button>
    </form>
  );
}

function AccountField({
  id,
  label,
  help,
  type,
  value,
  onChange,
  errors,
}: {
  id: string;
  label: string;
  help?: string;
  type?: string;
  value: string;
  onChange: (next: string) => void;
  errors?: string[];
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        name={id}
        type={type}
        value={value}
        autoComplete="off"
        aria-invalid={errors ? true : undefined}
        aria-describedby={
          errors?.length ? `${id}-error` : help ? `${id}-help` : undefined
        }
        onChange={(event) => onChange(event.target.value)}
      />
      {help ? (
        <p id={`${id}-help`} className="text-sm text-muted-foreground">
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

/** DRF's 400 body is `{field: [message, ...]}`; anything else is form-level. */
function fieldErrors(failure: unknown): Record<string, string[]> {
  if (!(failure instanceof ApiError)) return {};
  const body = failure.body;
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { non_field_errors: [de.hostHome.saveFailed] };
  }
  const out: Record<string, string[]> = {};
  for (const [field, value] of Object.entries(body)) {
    out[field] = Array.isArray(value) ? value.map(String) : [String(value)];
  }
  return out;
}
