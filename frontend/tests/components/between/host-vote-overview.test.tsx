import { describe, expect, it } from "vitest";

import { HostBetweenScreen } from "@/components/host/host-between-screen";
import { de } from "@/lib/de";

import { renderInGame } from "../in-game";

const options = [
  { id: 11, name: "Busspuren", poll_text: "Busspuren auf der Hauptstraße", is_rollback: false },
  { id: 12, name: "Umgehung", poll_text: "Eine Umgehung bauen", is_rollback: false },
];

describe("the host's vote overview", () => {
  it("offers every option's change on the map, like the ballot does", () => {
    const html = renderInGame(<HostBetweenScreen />, {
      phase: "voting",
      voteOptions: options,
      votes: { cast: 1, needed: 4 },
    });

    expect(html.split(de.vote.showChange).length - 1).toBe(options.length);
    for (const option of options) expect(html).toContain(option.name);
  });

  it("keeps the live tally beside the options", () => {
    const html = renderInGame(<HostBetweenScreen />, {
      phase: "voting",
      voteOptions: options,
      votes: { cast: 3, needed: 4 },
    });

    expect(html).toContain(de.vote.progress(3, 4));
  });
});
