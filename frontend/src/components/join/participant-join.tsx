import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { JoinForm } from "@/components/join/join-form";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";
import type { ParticipantLook } from "@/lib/queries/join";

/**
 * A participant code opened: the card's study and the games of it that wait in
 * their lobby. One waiting → straight to the name; several → pick one first;
 * none → what to do about it. The screen never says whose card it is: the site
 * does not know.
 */
export function ParticipantJoin({
  code,
  look,
}: {
  code: string;
  look: ParticipantLook;
}) {
  const navigate = useNavigate();
  const [picked, setPicked] = useState<string | null>(null);

  const chosen =
    look.games.length === 1
      ? look.games[0]
      : look.games.find((game) => game.game_id === picked);

  if (chosen) {
    return <JoinForm session={chosen} participantCode={code} />;
  }

  if (look.games.length === 0) {
    return (
      <Screen narrow>
        <ScreenHeading title={de.join.cardTitle} />
        <Alert variant="destructive">
          <AlertDescription>
            {look.reason === "played" ? de.join.cardPlayed : de.join.cardNoneWaiting}
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

  return (
    <Screen narrow>
      <ScreenHeading title={de.join.cardWhich} lead={de.join.cardWhichLead} />
      <ul className="space-y-3">
        {look.games.map((game) => (
          <li key={game.game_id}>
            <Button
              variant="outline"
              className="h-auto w-full justify-between py-3 text-left"
              onClick={() => setPicked(game.game_id)}
            >
              <span>{game.game_name}</span>
              <span className="text-sm text-muted-foreground">
                {de.join.seats(game.player_count, game.max_players)}
              </span>
            </Button>
          </li>
        ))}
      </ul>
    </Screen>
  );
}
