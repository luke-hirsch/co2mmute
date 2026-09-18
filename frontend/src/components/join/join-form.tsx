import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { DepartureBoard } from "@/components/metro/departure-board";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { ApiError, NetworkError } from "@/lib/api";
import { de, type JoinBlockedReason } from "@/lib/de";
import { useJoinGame, useSessionLookup } from "@/lib/queries/join";

/**
 * `/app/join/<ID>` — the screen a QR scan lands on.
 *
 * Two calls, in this order:
 *
 *   GET  lookup/<ID>/   does the game exist, is it joinable, is there a password
 *   POST join/<ID>/     name (+ password) in, a player row and both cookies out
 *
 * The lookup is what lets the screen ask for a password only when there is one,
 * and say "voll" before someone types a name for nothing. It is readable
 * without a cookie and deliberately leaks nothing — no host, no player names.
 *
 * ### Why the error handling is this explicit
 *
 * The join answers 404, 403 and 409 with prose that is intentionally similar,
 * so that a wrong password cannot be used to find out whether a game is full or
 * already running. Similar prose for the player is not the same as one error
 * for the screen: a wrong password has to leave the name in place and put the
 * focus back in the password field, while "voll" has to stop the form
 * entirely. That is the whole reason `lib/api.ts` keeps the status code and the
 * parsed body on `ApiError` instead of flattening both into a message, the way
 * the old `utils/api.ts` did.
 */
export function JoinForm({ gameId }: { gameId: string }) {
  const navigate = useNavigate();
  const lookup = useSessionLookup(gameId);
  const join = useJoinGame(gameId);

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [passwordWrong, setPasswordWrong] = useState(false);
  /** Set only by a 409 on submit — the lookup's own answer is derived below. */
  const [refusedOnSubmit, setRefusedOnSubmit] =
    useState<JoinBlockedReason | null>(null);

  // Two ways to learn the game cannot be joined, and neither needs an effect:
  // the lookup says so up front, or the join says so because the game filled up
  // while a name was being typed. The second wins, being newer.
  const blocked: JoinBlockedReason | null =
    refusedOnSubmit ??
    (lookup.data && !lookup.data.joinable ? lookup.data.reason : null);

  if (lookup.isLoading) {
    return (
      <Screen narrow>
        <p className="text-muted-foreground">{de.join.checking}</p>
      </Screen>
    );
  }

  // 404 from the lookup: there is no such game. Anything else that goes wrong
  // here is a connection problem, and saying "there is no such game" to someone
  // whose wifi dropped would send them hunting for a typo that is not there.
  if (lookup.isError) {
    const unknownGame =
      lookup.error instanceof ApiError && lookup.error.status === 404;
    return (
      <Screen narrow>
        <ScreenHeading title={de.join.title} />
        <Alert variant="destructive">
          <AlertDescription>
            {unknownGame
              ? de.join.gameNotFound
              : lookup.error instanceof NetworkError
                ? de.errors.network
                : de.errors.unknown}
          </AlertDescription>
        </Alert>
        <Button
          variant="outline"
          className="mt-8"
          onClick={() => void navigate({ to: "/join" })}
        >
          {de.actions.back}
        </Button>
      </Screen>
    );
  }

  const session = lookup.data;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    setPasswordWrong(false);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError(de.join.nameRequired);
      return;
    }

    try {
      const result = await join.mutateAsync({
        name: trimmedName,
        ...(password ? { password } : {}),
      });
      // Both cookies are set by the response. One route per game since F3 —
      // whether that shows the lobby or a running round is the game's call,
      // not the URL's.
      await navigate({
        to: "/game/$gameId",
        params: { gameId: result.game_id },
      });
    } catch (error) {
      if (error instanceof NetworkError) {
        setFormError(de.errors.network);
        return;
      }
      if (!(error instanceof ApiError)) {
        setFormError(de.errors.unknown);
        return;
      }
      if (error.status === 403) {
        // The password, and only the password: the backend checks it before it
        // looks at the game's state, so a 403 can mean nothing else.
        setPasswordWrong(true);
        return;
      }
      if (error.status === 404) {
        setFormError(de.join.gameNotFound);
        return;
      }
      if (error.status === 409) {
        const reason = error.reason as JoinBlockedReason | null;
        // `blocked` stops the form; an unknown reason must not do that
        // silently, so it falls through to a visible message instead.
        if (reason && reason in de.join.blocked) setRefusedOnSubmit(reason);
        else setFormError(de.errors.unknown);
        return;
      }
      setFormError(error.message || de.errors.unknown);
    }
  }

  if (blocked) {
    return (
      <Screen narrow>
        <ScreenHeading title={session?.game_name || de.join.title} />
        <Alert variant="destructive">
          <AlertDescription>{de.join.blocked[blocked]}</AlertDescription>
        </Alert>
        <Button
          variant="outline"
          className="mt-8"
          onClick={() => void navigate({ to: "/join" })}
        >
          {de.actions.back}
        </Button>
      </Screen>
    );
  }

  return (
    <Screen narrow>
      <ScreenHeading
        title={session?.game_name || de.join.title}
        lead={de.join.subtitle}
      />

      <DepartureBoard
        label={de.code.gameId}
        footnote={
          session
            ? de.join.seats(session.player_count, session.max_players)
            : undefined
        }
        className="mb-10"
      >
        <p className="font-mono text-3xl tracking-[0.3em] text-brandaccent uppercase">
          {gameId}
        </p>
      </DepartureBoard>

      <form onSubmit={submit} noValidate className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="join-name">{de.join.nameLabel}</Label>
          <Input
            id="join-name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (formError) setFormError(null);
            }}
            placeholder={de.join.namePlaceholder}
            autoFocus
            autoComplete="off"
            maxLength={40}
            aria-invalid={formError ? true : undefined}
          />
        </div>

        {session?.requires_password ? (
          <div className="space-y-2">
            <Label htmlFor="join-password">{de.join.passwordLabel}</Label>
            <Input
              id="join-password"
              type="password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (passwordWrong) setPasswordWrong(false);
              }}
              placeholder={de.join.passwordPlaceholder}
              autoComplete="off"
              aria-invalid={passwordWrong ? true : undefined}
            />
            <p className="text-sm text-muted-foreground">
              {passwordWrong ? de.join.passwordWrong : de.join.passwordHint}
            </p>
          </div>
        ) : null}

        {formError ? (
          <Alert variant="destructive">
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        ) : null}

        <Button
          type="submit"
          disabled={join.isPending}
          className="w-full sm:w-auto"
        >
          {join.isPending ? de.join.submitting : de.join.submit}
        </Button>
      </form>
    </Screen>
  );
}
