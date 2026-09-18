import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { CodeInput, DepartureBoard } from "@/components/metro/departure-board";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";

/**
 * `/app/seat/` — "Sitzung fortsetzen" (J-12).
 *
 * The second way into a game, next to the game id: a student who was already
 * playing and is now at a different device. The code is six characters off a
 * projector or another phone, in an alphabet with no 0/O and no 1/I/L.
 *
 * Like the game-id screen, nothing is checked here — it routes to
 * `/app/seat/<CODE>`, which is also where a scanned QR lands. One screen knows
 * what a code can be wrong about, instead of two that have to agree.
 */
export function SeatCodeForm() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) {
      setError(de.resumeSeat.codeRequired);
      return;
    }
    void navigate({ to: "/seat/$code", params: { code: trimmed } });
  }

  return (
    <Screen narrow>
      <ScreenHeading title={de.resumeSeat.title} lead={de.resumeSeat.lead} />

      <form onSubmit={submit} noValidate>
        <DepartureBoard label={de.code.seatCode} footnote={de.code.scanHint}>
          <CodeInput
            value={code}
            onValueChange={(value) => {
              setCode(value);
              if (error) setError(null);
            }}
            autoFocus
            aria-label={de.code.seatCode}
            aria-invalid={error ? true : undefined}
          />
        </DepartureBoard>

        {error ? (
          <p role="alert" className="mt-3 text-sm text-brandaccent">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="mt-8 w-full sm:w-auto">
          {de.resumeSeat.submit}
        </Button>
      </form>
    </Screen>
  );
}
