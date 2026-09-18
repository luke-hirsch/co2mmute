import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { CodeInput, DepartureBoard } from "@/components/metro/departure-board";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";

/**
 * `/app/join/` — someone who did not scan the QR code.
 *
 * The id goes in a departure board rather than a form field because that is
 * where it comes from: a projector at the front of a room. The landing page's
 * join box is the same object, and a player who typed one there recognises it
 * here.
 *
 * No lookup happens on this screen. It only routes to `/app/join/<ID>`, which
 * is the same URL a QR scan lands on — so there is exactly one screen that
 * knows what a game id can be wrong about, instead of two that have to agree.
 */
export function GameIdForm() {
  const navigate = useNavigate();
  const [gameId, setGameId] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = gameId.trim().toUpperCase();
    if (!trimmed) {
      setError(de.join.idRequired);
      return;
    }
    void navigate({ to: "/join/$gameId", params: { gameId: trimmed } });
  }

  return (
    <Screen narrow>
      <ScreenHeading title={de.join.idTitle} lead={de.join.idSubtitle} />

      <form onSubmit={submit} noValidate>
        <DepartureBoard label={de.code.gameId} footnote={de.code.scanHint}>
          <CodeInput
            value={gameId}
            onValueChange={(value) => {
              setGameId(value);
              if (error) setError(null);
            }}
            autoFocus
            aria-label={de.join.idLabel}
            aria-invalid={error ? true : undefined}
          />
        </DepartureBoard>

        {error ? (
          <p role="alert" className="mt-3 text-sm text-brandaccent">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="mt-8 w-full sm:w-auto">
          {de.join.idSubmit}
        </Button>
      </form>

      {/* The second way in (1.7, J-12): somebody who was already playing and is
          now at another device. A game id would give them a *new* seat and
          leave their moves behind, so it is deliberately a separate door. */}
      <Button
        variant="link"
        className="mt-10 px-0"
        onClick={() => void navigate({ to: "/seat" })}
      >
        {de.resumeSeat.link}
      </Button>
    </Screen>
  );
}
