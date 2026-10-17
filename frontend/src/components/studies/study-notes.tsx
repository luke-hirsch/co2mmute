import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/layout/field";
import { textareaClass } from "@/components/studies/study-index";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import {
  useDeleteNote,
  useSaveNote,
  useStudyNotes,
  type MetaValue,
  type StudyNote,
} from "@/lib/queries/studies";

type Row = { field: string; value: string };

/** A pure number becomes a number in the export; everything else stays text. */
export function metaValue(raw: string): MetaValue {
  const text = raw.trim();
  return /^-?(0|[1-9]\d*)([.,]\d+)?$/.test(text)
    ? Number(text.replace(",", "."))
    : raw;
}

export function rowsToMeta(rows: Row[]): Record<string, MetaValue> {
  const meta: Record<string, MetaValue> = {};
  for (const row of rows) {
    if (row.field.trim()) meta[row.field.trim()] = metaValue(row.value);
  }
  return meta;
}

/** The study's notes: the researchers' own text, with flat fields. */
export function StudyNotes({ studyId }: { studyId: number }) {
  const t = de.studies.notes;
  const { data: notes } = useStudyNotes(studyId);
  // null: closed; 0: a new note; otherwise the id of the note being edited.
  const [editing, setEditing] = useState<number | null>(null);

  return (
    <section aria-labelledby="study-notes">
      <h2 id="study-notes" className="text-2xl font-medium">
        {t.title}
      </h2>
      <p className="mt-2 max-w-(--measure-body) text-muted-foreground">{t.lead}</p>

      {notes && notes.length === 0 && editing === null ? (
        <p className="mt-4 text-muted-foreground">{t.empty}</p>
      ) : null}

      {notes && notes.length > 0 ? (
        <ul className="mt-4 divide-y divide-border border-y">
          {notes.map((note) =>
            editing === note.id ? (
              <li key={note.id} className="py-5">
                <NoteForm
                  studyId={studyId}
                  note={note}
                  onDone={() => setEditing(null)}
                />
              </li>
            ) : (
              <NoteItem
                key={note.id}
                studyId={studyId}
                note={note}
                onEdit={() => setEditing(note.id)}
              />
            ),
          )}
        </ul>
      ) : null}

      {editing === 0 ? (
        <div className="mt-6">
          <NoteForm studyId={studyId} note={null} onDone={() => setEditing(null)} />
        </div>
      ) : (
        <Button className="mt-6" variant="outline" onClick={() => setEditing(0)}>
          {t.add}
        </Button>
      )}
    </section>
  );
}

function NoteItem({
  studyId,
  note,
  onEdit,
}: {
  studyId: number;
  note: StudyNote;
  onEdit: () => void;
}) {
  const t = de.studies.notes;
  const remove = useDeleteNote(studyId);
  const entries = Object.entries(note.meta);

  return (
    <li className="py-5">
      <p className="whitespace-pre-wrap">{note.text}</p>
      {entries.length > 0 ? (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {entries.map(([field, value]) => (
            <div key={field} className="contents">
              <dt className="text-muted-foreground">{field}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="mt-3 text-sm text-muted-foreground">
        {[
          note.about_date,
          note.games.length ? note.games.join(", ") : null,
          t.by(note.author),
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <div className="mt-3 flex gap-2">
        <Button variant="outline" size="xs" onClick={onEdit}>
          {t.edit}
        </Button>
        <Button
          variant="ghost"
          size="xs"
          disabled={remove.isPending}
          onClick={() => remove.mutate(note.id)}
        >
          {t.delete}
        </Button>
      </div>
      {remove.isError ? (
        <Alert variant="destructive" className="mt-3">
          <AlertDescription>{t.deleteFailed}</AlertDescription>
        </Alert>
      ) : null}
    </li>
  );
}

function NoteForm({
  studyId,
  note,
  onDone,
}: {
  studyId: number;
  note: StudyNote | null;
  onDone: () => void;
}) {
  const t = de.studies.notes;
  const save = useSaveNote(studyId);
  const [text, setText] = useState(note?.text ?? "");
  const [date, setDate] = useState(note?.about_date ?? "");
  const [games, setGames] = useState(note?.games.join(", ") ?? "");
  const [rows, setRows] = useState<Row[]>(
    note
      ? Object.entries(note.meta).map(([field, value]) => ({
          field,
          value: String(value),
        }))
      : [],
  );

  const change = (index: number, patch: Partial<Row>) =>
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(
      {
        noteId: note?.id ?? null,
        input: {
          text,
          about_date: date || null,
          games: games
            .split(/[\s,;]+/)
            .map((id) => id.trim().toUpperCase())
            .filter(Boolean),
          meta: rowsToMeta(rows),
        },
      },
      { onSuccess: onDone },
    );
  };

  return (
    <form onSubmit={submit} className="max-w-xl space-y-5">
      <Field id="note-text" label={t.text} help={t.noNames}>
        <textarea
          id="note-text"
          rows={5}
          value={text}
          onChange={(event) => setText(event.target.value)}
          className={textareaClass}
        />
      </Field>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="note-date" label={t.date} help={t.dateHelp}>
          <Input
            id="note-date"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </Field>
        <Field id="note-games" label={t.games} help={t.gamesHelp}>
          <Input
            id="note-games"
            value={games}
            onChange={(event) => setGames(event.target.value)}
            className="font-mono uppercase"
            autoComplete="off"
          />
        </Field>
      </div>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">{t.meta}</legend>
        <p className="text-sm text-muted-foreground">{t.metaHelp}</p>
        {rows.map((row, index) => (
          <div key={index} className="flex items-center gap-2">
            <Input
              aria-label={t.metaField}
              placeholder={t.metaField}
              value={row.field}
              onChange={(event) => change(index, { field: event.target.value })}
            />
            <Input
              aria-label={t.metaValue}
              placeholder={t.metaValue}
              value={row.value}
              onChange={(event) => change(index, { value: event.target.value })}
            />
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
            >
              {t.removeRow}
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="xs"
          onClick={() => setRows((current) => [...current, { field: "", value: "" }])}
        >
          {t.addRow}
        </Button>
      </fieldset>

      {save.isError ? (
        <Alert variant="destructive">
          <AlertDescription>
            {save.error instanceof ApiError && save.error.status === 400
              ? save.error.message
              : t.saveFailed}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex gap-3">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? t.saving : t.save}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t.cancel}
        </Button>
      </div>
    </form>
  );
}
