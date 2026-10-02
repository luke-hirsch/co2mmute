import { describe, expect, it } from "vitest";

import { invitationText, joinUrl } from "@/lib/game/invitation";

/**
 * What the lobby's share button copies (F3): the way in, in a message somebody
 * pastes into a class chat.
 */

describe("the invitation", () => {
  it("joins where the QR code joins", () => {
    expect(joinUrl("https://co2mmute.example", "A40307")).toBe(
      "https://co2mmute.example/app/join/A40307",
    );
  });

  it("carries the name, the link, the id and the password", () => {
    const text = invitationText({
      gameName: "Dienstag",
      gameId: "A40307",
      url: "https://co2mmute.example/app/join/A40307",
      password: "tram",
    });
    expect(text.split("\n")).toEqual([
      "Mach mit bei co2mmute: „Dienstag“",
      "https://co2mmute.example/app/join/A40307",
      "Spiel-ID: A40307",
      "Passwort: tram",
    ]);
  });

  it("says nothing about a password the game does not have", () => {
    const text = invitationText({
      gameName: "Dienstag",
      gameId: "A40307",
      url: "https://co2mmute.example/app/join/A40307",
      password: null,
    });
    expect(text).not.toContain("Passwort");
  });
});
