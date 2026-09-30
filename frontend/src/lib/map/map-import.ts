/**
 * The two pure halves of the map upload screen (S19): the form it posts, and
 * the refusal it reads back.
 *
 * `POST api/maps/import/` runs Django's `MapUploadForm` and then the importer,
 * so there are two kinds of "no": the form's, per field (a taken name, a file
 * that is not JSON), and the file's, as a list (a line pointing at an edge the
 * file does not have). Both arrive in German and are shown as they come —
 * validation is the server's, and a client copy of the rules is how the
 * editor's strings drifted.
 */

import { ApiError, apiErrorMessage } from "@/lib/api";

export type ImportValues = {
  name: string;
  maxPlayers: string;
  description: string;
  jsonFile: File | null;
  imageFile: File | null;
};

/** The field names are `MapUploadForm`'s; they are the endpoint's contract. */
export function buildImportForm(values: ImportValues): FormData {
  const form = new FormData();
  form.set("map_name", values.name.trim());
  form.set("max_players", values.maxPlayers);
  form.set("description", values.description.trim());
  if (values.jsonFile) form.set("json_file", values.jsonFile);
  if (values.imageFile) form.set("image_file", values.imageFile);
  return form;
}

export type ImportRefusal = {
  /** Per form field, keyed by `MapUploadForm`'s field names. */
  fields: Record<string, string[]>;
  /** Everything wrong inside a file that parsed, all at once. */
  graph: string[];
  /**
   * Anything else: a 403, a dropped connection. `""` means "it failed and
   * there is nothing more to say", which the screen turns into its own line;
   * `null` means the refusal is fully described by the two above.
   */
  other: string | null;
};

export function readImportRefusal(failure: unknown): ImportRefusal {
  if (failure instanceof ApiError && failure.status === 400) {
    const body = (failure.body ?? {}) as {
      fields?: Record<string, unknown>;
      graph?: unknown;
    };
    const fields: Record<string, string[]> = {};
    for (const [name, value] of Object.entries(body.fields ?? {})) {
      fields[name] = Array.isArray(value) ? value.map(String) : [String(value)];
    }
    const graph = Array.isArray(body.graph) ? body.graph.map(String) : [];
    return { fields, graph, other: null };
  }
  if (failure instanceof ApiError) {
    return { fields: {}, graph: [], other: apiErrorMessage(failure.body) ?? "" };
  }
  return { fields: {}, graph: [], other: "" };
}
