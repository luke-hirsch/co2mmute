import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/layout/field";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import Loading from "@/components/Loading";
import { de } from "@/lib/de";
import { useCreateStudy, useStudies, type Study } from "@/lib/queries/studies";

/** `/app/studies` — the studies there are, and a form for a new one. */
export function StudyIndex() {
  const { data: studies, isLoading, isError } = useStudies();

  return (
    <Screen>
      <ScreenHeading title={de.studies.title} lead={de.studies.lead} />

      <NewStudy />

      {isLoading ? <Loading label={de.studies.loading} /> : null}

      {isError ? (
        <Alert variant="destructive">
          <AlertDescription>{de.studies.failed}</AlertDescription>
        </Alert>
      ) : null}

      {studies && studies.length === 0 ? (
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.studies.empty}
        </p>
      ) : null}

      {studies && studies.length > 0 ? (
        <ul className="divide-y divide-border border-y">
          {studies.map((study) => (
            <StudyRow key={study.id} study={study} />
          ))}
        </ul>
      ) : null}
    </Screen>
  );
}

function StudyRow({ study }: { study: Study }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4 py-5">
      <div className="min-w-0">
        <h2 className="text-lg">
          <Link
            to="/studies/$studyId"
            params={{ studyId: String(study.id) }}
            className="underline-offset-4 hover:underline"
          >
            {study.name}
          </Link>
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {de.studies.counts(study.games, study.codes, study.notes)}
        </p>
      </div>
      <Button asChild variant="outline" size="sm">
        <Link to="/studies/$studyId" params={{ studyId: String(study.id) }}>
          {de.studies.open}
        </Link>
      </Button>
    </li>
  );
}

function NewStudy() {
  const t = de.studies.create;
  const navigate = useNavigate();
  const create = useCreateStudy();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  if (!open) {
    return (
      <div className="mb-10">
        <Button onClick={() => setOpen(true)}>{de.studies.newStudy}</Button>
      </div>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { name, description },
      {
        onSuccess: (study) =>
          navigate({
            to: "/studies/$studyId",
            params: { studyId: String(study.id) },
          }),
      },
    );
  };

  return (
    <form onSubmit={submit} className="mb-10 max-w-xl space-y-5 border-y py-6">
      <h2 className="text-xl font-medium">{t.title}</h2>
      <Field id="study-name" label={t.name}>
        <Input
          id="study-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={t.namePlaceholder}
          maxLength={100}
          required
        />
      </Field>
      <Field id="study-description" label={t.description} help={t.descriptionHelp}>
        <textarea
          id="study-description"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className={textareaClass}
        />
      </Field>
      {create.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{t.failed}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex gap-3">
        <Button type="submit" disabled={create.isPending || !name.trim()}>
          {create.isPending ? t.submitting : t.submit}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          {de.actions.cancel}
        </Button>
      </div>
    </form>
  );
}

export const textareaClass =
  "w-full min-w-0 rounded-md border border-input bg-transparent px-3.5 py-2 " +
  "text-base shadow-xs outline-none transition-[color,box-shadow] md:text-sm " +
  "placeholder:text-muted-foreground focus-visible:border-ring " +
  "focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30";
