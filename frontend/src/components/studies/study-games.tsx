import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/layout/field";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import {
  useLinkGame,
  useStudyGames,
  useUnlinkGame,
  type StudyGameRow,
} from "@/lib/queries/studies";

function state(game: StudyGameRow): string {
  if (game.ended_at) return de.studies.games.ended;
  if (game.started_at) return de.studies.games.running;
  return de.studies.games.waiting;
}

/** The study's games: link one that is still in its lobby, or let go of it. */
export function StudyGames({ studyId }: { studyId: number }) {
  const t = de.studies.games;
  const { data: games } = useStudyGames(studyId);
  const link = useLinkGame(studyId);
  const unlink = useUnlinkGame(studyId);
  const [gameId, setGameId] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    link.mutate(gameId.trim(), { onSuccess: () => setGameId("") });
  };

  const message = (error: unknown, fallback: string) =>
    error instanceof ApiError && (error.status === 409 || error.status === 404)
      ? error.status === 404
        ? t.notFound
        : error.message
      : fallback;

  return (
    <section aria-labelledby="study-games">
      <h2 id="study-games" className="text-2xl font-medium">
        {t.title}
      </h2>
      <p className="mt-2 max-w-(--measure-body) text-muted-foreground">{t.lead}</p>

      {games && games.length === 0 ? (
        <p className="mt-4 text-muted-foreground">{t.empty}</p>
      ) : null}

      {games && games.length > 0 ? (
        <ul className="mt-4 divide-y divide-border border-y">
          {games.map((game) => (
            <li
              key={game.game_id}
              className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3"
            >
              <div className="min-w-0">
                <span className="font-mono">{game.game_id}</span>
                {" · "}
                {game.name}
                <p className="text-sm text-muted-foreground">
                  {game.map ?? t.noMap}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="outline">{state(game)}</Badge>
                {!game.started_at ? (
                  <Button
                    variant="outline"
                    size="xs"
                    disabled={unlink.isPending}
                    onClick={() => unlink.mutate(game.game_id)}
                  >
                    {t.unlink}
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {unlink.isError ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{message(unlink.error, t.unlinkFailed)}</AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={submit} className="mt-6 flex max-w-xl flex-wrap items-end gap-3">
        <div className="w-44">
          <Field id="link-game-id" label={t.gameId}>
            <Input
              id="link-game-id"
              value={gameId}
              onChange={(event) => setGameId(event.target.value)}
              placeholder={t.gameIdPlaceholder}
              maxLength={6}
              className="font-mono uppercase"
              autoCapitalize="characters"
              autoComplete="off"
            />
          </Field>
        </div>
        <Button type="submit" disabled={link.isPending || gameId.trim().length === 0}>
          {link.isPending ? t.linking : t.link}
        </Button>
      </form>
      {link.isError ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{message(link.error, t.linkFailed)}</AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
