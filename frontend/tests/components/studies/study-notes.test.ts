import { describe, expect, it } from "vitest";

import { metaValue, rowsToMeta } from "@/components/studies/study-notes";

describe("a note's fields", () => {
  it("turns a plain number into a number and keeps the rest text", () => {
    expect(metaValue("24")).toBe(24);
    expect(metaValue("2,5")).toBe(2.5);
    expect(metaValue("-3")).toBe(-3);
    expect(metaValue("9b")).toBe("9b");
    expect(metaValue("007")).toBe("007");
    expect(metaValue("")).toBe("");
  });

  it("drops a row without a field name and trims the name", () => {
    expect(
      rowsToMeta([
        { field: " Ort ", value: "Aula" },
        { field: "", value: "verloren" },
        { field: "Schüler", value: "24" },
      ]),
    ).toEqual({ Ort: "Aula", Schüler: 24 });
  });
});
