import { describe, expect, it } from "vitest";

import { ApiError, NetworkError } from "@/lib/api";
import { buildImportForm, readImportRefusal } from "@/lib/map/map-import";

describe("buildImportForm", () => {
  it("names the fields the way MapUploadForm reads them", () => {
    const json = new File(["{}"], "karte.json", { type: "application/json" });

    const form = buildImportForm({
      name: "  Neu  ",
      maxPlayers: "6",
      description: "",
      jsonFile: json,
      imageFile: null,
    });

    expect(form.get("map_name")).toBe("Neu");
    expect(form.get("max_players")).toBe("6");
    expect(form.get("description")).toBe("");
    expect((form.get("json_file") as File).name).toBe("karte.json");
    // An empty file field is a different thing from an absent one to Django:
    // absent is "no image", which is what the host meant.
    expect(form.has("image_file")).toBe(false);
  });
});

describe("readImportRefusal", () => {
  it("keeps field errors per field and the file's errors as a list", () => {
    const refusal = readImportRefusal(
      new ApiError(
        400,
        {
          fields: { map_name: ["Eine Karte mit dem Namen gibt es schon."] },
          graph: [],
        },
        "HTTP 400",
      ),
    );

    expect(refusal.fields).toEqual({
      map_name: ["Eine Karte mit dem Namen gibt es schon."],
    });
    expect(refusal.graph).toEqual([]);
    expect(refusal.other).toBeNull();
  });

  it("lists every graph error, not only the first", () => {
    const refusal = readImportRefusal(
      new ApiError(
        400,
        { fields: {}, graph: ["Kante 0: …", "Kante 3: …"] },
        "HTTP 400",
      ),
    );

    expect(refusal.graph).toEqual(["Kante 0: …", "Kante 3: …"]);
    expect(refusal.other).toBeNull();
  });

  it("puts a refusal that is not a 400 under the form", () => {
    const refusal = readImportRefusal(
      new ApiError(403, { detail: "Keine Berechtigung." }, "HTTP 403"),
    );

    expect(refusal.fields).toEqual({});
    expect(refusal.graph).toEqual([]);
    expect(refusal.other).toBe("Keine Berechtigung.");
  });

  it("has nothing to say about a dropped connection but that it failed", () => {
    const refusal = readImportRefusal(new NetworkError(new Error("offline")));

    expect(refusal.other).toBe("");
  });
});
