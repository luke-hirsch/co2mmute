import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { CodeInput, DepartureBoard } from "@/components/metro/departure-board";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { useSession } from "@/hooks/useSession";
import { codeMaxLength } from "@/lib/codes";
import { de } from "@/lib/de";

/**
 * `/app/join/` — someone who did not scan a QR code.
 *
 * The code goes in a departure board rather than a form field because that is
 * where it comes from: a projector at the front of a room. The landing page's
 * join box is the same object, and a player who typed one there recognises it
 * here. A game id, a seat code: the length says which, and the next screen
 * finds out.
 *
 * No lookup happens on this screen. It only routes to `/app/join/<CODE>`, which
 * is the same URL every QR scan lands on — so there is exactly one screen that
 * knows what a code can be wrong about, instead of two that have to agree.
 */
export function CodeForm() {
  const navigate = useNavigate();
  // The session, not `useAuth`: no auth provider is mounted above the join
  // box, and a player has no account; whoami says whether the study app is on.
  const studies = useSession().data?.studies === true;
  const label = studies ? de.code.entryStudies : de.code.entry;
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) {
      setError(de.join.codeRequired);
      return;
    }
    void navigate({ to: "/join/$code", params: { code: trimmed } });
  }

  return (
    <Screen narrow>
      <ScreenHeading title={de.join.idTitle} lead={de.join.idSubtitle} />

      <form onSubmit={submit} noValidate>
        <DepartureBoard label={label} footnote={de.code.scanHint}>
          <CodeInput
            value={code}
            onValueChange={(value) => {
              setCode(value);
              if (error) setError(null);
            }}
            autoFocus
            aria-label={label}
            maxLength={codeMaxLength(studies)}
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
    </Screen>
  );
}
