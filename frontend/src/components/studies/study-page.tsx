import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmAction } from "@/components/layout/confirm-action";
import { Field } from "@/components/layout/field";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import Loading from "@/components/Loading";
import { StudyCodes } from "@/components/studies/study-codes";
import { StudyGames } from "@/components/studies/study-games";
import { StudyNotes } from "@/components/studies/study-notes";
import { textareaClass } from "@/components/studies/study-index";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import {
  useDeleteStudy,
  useStudy,
  useUpdateStudy,
  type Study,
} from "@/lib/queries/studies";

/** `/app/studies/$studyId` — one study: its details, games, codes and notes. */
export function StudyPage({ studyId }: { studyId: number }) {
  const { data: study, isLoading, isError } = useStudy(studyId);

  if (isLoading) {
    return (
      <Screen>
        <Loading label={de.studies.loading} />
      </Screen>
    );
  }

  if (isError || !study) {
    return (
      <Screen>
        <Alert variant="destructive">
          <AlertDescription>{de.studies.notFound}</AlertDescription>
        </Alert>
        <Button asChild variant="outline" className="mt-6">
          <Link to="/studies">{de.studies.allStudies}</Link>
        </Button>
      </Screen>
    );
  }

  return (
    <Screen>
      <Button asChild variant="link" size="sm" className="-ml-4 mb-4">
        <Link to="/studies">{de.studies.allStudies}</Link>
      </Button>
      <ScreenHeading title={study.name} />

      <div className="space-y-14">
        <Details study={study} />
        <StudyGames studyId={studyId} />
        <StudyCodes studyId={studyId} />
        <StudyNotes studyId={studyId} />
        <Remove study={study} />
      </div>
    </Screen>
  );
}

function Details({ study }: { study: Study }) {
  const t = de.studies.details;
  const update = useUpdateStudy(study.id);
  const [name, setName] = useState(study.name);
  const [description, setDescription] = useState(study.description);

  useEffect(() => {
    setName(study.name);
    setDescription(study.description);
  }, [study.name, study.description]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ name, description });
  };

  return (
    <section>
      <form onSubmit={submit} className="max-w-xl space-y-5">
        <Field id="detail-name" label={de.studies.create.name}>
          <Input
            id="detail-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
            required
          />
        </Field>
        <Field id="detail-description" label={de.studies.create.description}>
          <textarea
            id="detail-description"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className={textareaClass}
          />
        </Field>
        {update.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{t.failed}</AlertDescription>
          </Alert>
        ) : null}
        <div className="flex items-center gap-4">
          <Button type="submit" disabled={update.isPending || !name.trim()}>
            {update.isPending ? t.saving : t.save}
          </Button>
          {update.isSuccess ? (
            <span role="status" className="text-sm text-muted-foreground">
              {t.saved}
            </span>
          ) : null}
        </div>
      </form>
    </section>
  );
}

function Remove({ study }: { study: Study }) {
  const t = de.studies.remove;
  const navigate = useNavigate();
  const remove = useDeleteStudy(study.id);

  return (
    <section className="border-t pt-8">
      {remove.isError ? (
        <Alert variant="destructive" className="mb-4">
          {/* A 409 carries the server's own sentence. */}
          <AlertDescription>
            {remove.error instanceof ApiError && remove.error.status === 409
              ? remove.error.message
              : t.failed}
          </AlertDescription>
        </Alert>
      ) : null}
      <ConfirmAction
        label={t.button}
        title={t.title}
        description={t.body(study.name)}
        confirmLabel={t.confirm}
        size="default"
        variant="outline"
        pending={remove.isPending}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => navigate({ to: "/studies" }),
          })
        }
      />
    </section>
  );
}
