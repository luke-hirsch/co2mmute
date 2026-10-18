import { describe, expect, it } from "vitest";

import { createSearch } from "@/lib/create-search";

describe("createSearch", () => {
  it("keeps a study's pk", () => {
    expect(createSearch({ study: 7 })).toEqual({ study: 7 });
    expect(createSearch({ study: "12" })).toEqual({ study: 12 });
  });

  it("drops anything that is not a pk", () => {
    expect(createSearch({})).toEqual({});
    for (const study of ["", "abc", 0, -3, 1.5, null]) {
      expect(createSearch({ study })).toEqual({});
    }
  });
});
