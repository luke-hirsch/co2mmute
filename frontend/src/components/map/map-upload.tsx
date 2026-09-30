import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/layout/field";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { de } from "@/lib/de";
import { EXAMPLE_MAP_FILE } from "@/lib/map/file-format";
import {
  buildImportForm,
  readImportRefusal,
  type ImportRefusal,
} from "@/lib/map/map-import";
import { useImportMap } from "@/lib/queries/maps";

const t = de.map.upload;

const NO_REFUSAL: ImportRefusal = { fields: {}, graph: [], other: null };

/**
 * `/app/maps/upload` — a new map, empty or from a file. S19.
 *
 * The last staff tool that was still a Django page, beside an editor that has
 * been in the SPA since F7. Two things changed on the way across and nothing
 * else did:
 *
 * - **the file format is behind a toggle.** The page used to open on two
 *   screens of reference, so the four fields were below the fold on every visit
 *   — and the reader who needs the format is the one writing a file by hand,
 *   which is rare. The usual file comes out of "Karte sichern (JSON)".
 * - **a refused file lists everything wrong with it** rather than a Django
 *   message banner. A hand-edited file is fixed in one pass or in twenty
 *   uploads.
 *
 * The rules are the server's (`MapUploadForm`, then `maps/importer.py`), and
 * so is the German: nothing here words a refusal of its own, the same stance
 * the create form takes.
 */
export function MapUploadScreen() {
  const navigate = useNavigate();
  const importMap = useImportMap();

  const [name, setName] = useState("");
  const [maxPlayers, setMaxPlayers] = useState("4");
  const [description, setDescription] = useState("");
  const [jsonFile, setJsonFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [showFormat, setShowFormat] = useState(false);
  const [refusal, setRefusal] = useState<ImportRefusal>(NO_REFUSAL);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setRefusal(NO_REFUSAL);
    try {
      const created = await importMap.mutateAsync(
        buildImportForm({ name, maxPlayers, description, jsonFile, imageFile }),
      );
      navigate({ to: "/maps/$mapId", params: { mapId: String(created.id) } });
    } catch (failure) {
      setRefusal(readImportRefusal(failure));
    }
  }

  const { fields } = refusal;

  return (
    <Screen>
      <Button asChild variant="link" size="sm" className="-ml-4 mb-4">
        <Link to="/maps">{t.back}</Link>
      </Button>
      <ScreenHeading title={t.title} lead={t.lead} />

      <section className="mb-12">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={showFormat}
          aria-controls="file-format"
          onClick={() => setShowFormat((open) => !open)}
        >
          {showFormat ? t.hideFormat : t.showFormat}
        </Button>
        {showFormat ? <FileFormat /> : null}
      </section>

      <form onSubmit={submit} noValidate className="space-y-8">
        <div className="grid gap-6 sm:grid-cols-2">
          <Field id="map_name" label={t.name} errors={fields.map_name}>
            <Input
              id="map_name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t.namePlaceholder}
              autoComplete="off"
              maxLength={100}
              autoFocus
              aria-invalid={fields.map_name ? true : undefined}
            />
          </Field>

          <Field
            id="max_players"
            label={t.maxPlayers}
            help={t.maxPlayersHelp}
            errors={fields.max_players}
          >
            <Input
              id="max_players"
              value={maxPlayers}
              inputMode="numeric"
              autoComplete="off"
              className="font-mono"
              onChange={(event) =>
                setMaxPlayers(event.target.value.replace(/[^\d]/g, ""))
              }
              aria-invalid={fields.max_players ? true : undefined}
            />
          </Field>

          <div className="sm:col-span-2">
            <Field
              id="description"
              label={t.description}
              errors={fields.description}
            >
              <textarea
                id="description"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={t.descriptionPlaceholder}
                className={textareaClass}
              />
            </Field>
          </div>

          <Field
            id="json_file"
            label={t.jsonFile}
            help={t.jsonFileHelp}
            errors={fields.json_file}
          >
            <FilePicker
              id="json_file"
              accept=".json,application/json"
              file={jsonFile}
              onChange={setJsonFile}
              invalid={!!fields.json_file}
            />
          </Field>

          <Field
            id="image_file"
            label={t.imageFile}
            help={t.imageFileHelp}
            errors={fields.image_file}
          >
            <FilePicker
              id="image_file"
              accept="image/*"
              file={imageFile}
              onChange={setImageFile}
              invalid={!!fields.image_file}
            />
          </Field>
        </div>

        {refusal.graph.length > 0 ? (
          <Alert variant="destructive">
            <AlertDescription>
              <p>{t.graphErrors}</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 font-mono text-xs">
                {refusal.graph.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}

        {refusal.other !== null ? (
          <Alert variant="destructive">
            <AlertDescription>{refusal.other || t.failed}</AlertDescription>
          </Alert>
        ) : null}

        <Button type="submit" disabled={importMap.isPending}>
          {importMap.isPending ? t.submitting : t.submit}
        </Button>
      </form>
    </Screen>
  );
}

/** The reference, carried across from the Django page and brought up to date. */
function FileFormat() {
  const f = t.format;
  return (
    <div id="file-format" className="mt-6 space-y-8 border-y py-8">
      <div className="max-w-(--measure-body) space-y-3 text-sm text-muted-foreground">
        <p>{f.intro}</p>
        <p>{f.exportHint}</p>
      </div>

      <dl className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
        {f.sections.map((section) => (
          <div key={section.title}>
            <dt className="mb-3 text-sm font-medium">{section.title}</dt>
            <dd>
              <ul className="space-y-2 text-sm">
                {section.fields.map(([key, meaning]) => (
                  <li key={key}>
                    <code className="font-mono text-xs">{key}</code>
                    <span className="text-muted-foreground"> — {meaning}</span>
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        ))}
      </dl>

      <div>
        <p className="mb-3 text-sm font-medium">{f.example}</p>
        {/* Scrolls inside itself: a JSON line does not wrap, and a 390px page
            must never scroll sideways. */}
        <pre className="max-h-96 overflow-auto rounded-md border bg-muted p-4 font-mono text-xs">
          <code>{JSON.stringify(EXAMPLE_MAP_FILE, null, 2)}</code>
        </pre>
      </div>
    </div>
  );
}

const textareaClass =
  "w-full min-w-0 rounded-md border border-input bg-transparent px-3.5 py-2 " +
  "text-base shadow-xs outline-none transition-[color,box-shadow] md:text-sm " +
  "placeholder:text-muted-foreground focus-visible:border-ring " +
  "focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30";

/**
 * A file field that speaks German whatever the browser does.
 *
 * The native control writes its own "Choose File" / "no file selected" in the
 * browser's language, which on an English-set Mac or in WebKit's test profile
 * is English on a German page — and nothing in `de.ts` can reach it. So the
 * input is visually hidden but stays the real, labelled, focusable control
 * (Playwright's `setInputFiles` and a screen reader both find it by its
 * label), and the button and the file name beside it are ours.
 */
function FilePicker({
  id,
  accept,
  file,
  onChange,
  invalid,
}: {
  id: string;
  accept: string;
  file: File | null;
  onChange: (file: File | null) => void;
  invalid?: boolean;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <input
        id={id}
        type="file"
        accept={accept}
        className="peer sr-only"
        aria-invalid={invalid ? true : undefined}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <label
        htmlFor={id}
        aria-hidden="true"
        className="inline-flex h-9 shrink-0 cursor-pointer items-center rounded-md border border-input px-3 text-sm font-medium hover:bg-muted peer-focus-visible:ring-[3px] peer-focus-visible:ring-ring/50"
      >
        {t.pickFile}
      </label>
      <span className="min-w-0 truncate text-sm text-muted-foreground">
        {file ? file.name : t.noFile}
      </span>
    </div>
  );
}
