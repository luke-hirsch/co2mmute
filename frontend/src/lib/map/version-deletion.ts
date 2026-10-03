import { de } from "@/lib/de";
import type { VersionDeletion } from "@/types/mapTypes";

/**
 * The deletion dialog's text, out of the component so it can be tested (F14).
 *
 * The server answers in numbers and names (`GET …/versions/<id>/deletion/`);
 * this turns them into the lines the dialog shows. A kind of row nothing of
 * goes is left out rather than written as "0 Knoten".
 */

/** `»A«`, `»A« und »B«`, `»A«, »B« und »C«` — names the way the ballot quotes them. */
export function quotedList(names: string[]): string {
  const quoted = names.map((name) => `»${name}«`);
  if (quoted.length <= 1) return quoted.join("");
  return `${quoted.slice(0, -1).join(", ")} und ${quoted[quoted.length - 1]}`;
}

/** What only this version holds, one line per kind. Empty if nothing. */
export function goesLines(goes: VersionDeletion["goes"]): string[] {
  const words = de.editor.version.goes;
  const lines: string[] = [];
  if (goes.nodes) lines.push(words.nodes(goes.nodes));
  if (goes.edges) lines.push(words.edges(goes.edges));
  if (goes.streets) lines.push(words.streets(goes.streets));
  if (goes.rails) lines.push(words.rails(goes.rails));
  if (goes.bus_lines.length)
    lines.push(words.busLines(goes.bus_lines.length, quotedList(goes.bus_lines)));
  if (goes.train_lines.length)
    lines.push(
      words.trainLines(goes.train_lines.length, quotedList(goes.train_lines)),
    );
  if (goes.line_links) lines.push(words.lineLinks(goes.line_links));
  return lines;
}

/** The sentences under the list: the ballot pairs that go, the versions that keep the change. */
export function afterLines(deletion: VersionDeletion): string[] {
  const lines: string[] = [];
  if (deletion.ballot.length)
    lines.push(de.editor.version.deleteBallot(quotedList(deletion.ballot)));
  if (deletion.keeps.length)
    lines.push(de.editor.version.deleteKeeps(quotedList(deletion.keeps)));
  return lines;
}
