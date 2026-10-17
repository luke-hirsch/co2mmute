import { useState, type FormEvent } from "react";
import { Link } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/layout/field";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import {
  useDeleteCode,
  useMakeCodes,
  useStudyCodes,
} from "@/lib/queries/studies";

/** Participation codes: optional, made in batches, printed as cards. */
export function StudyCodes({ studyId }: { studyId: number }) {
  const t = de.studies.codes;
  const { data: codes } = useStudyCodes(studyId);
  const make = useMakeCodes(studyId);
  const remove = useDeleteCode(studyId);
  const [count, setCount] = useState("12");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    make.mutate(Number(count));
  };

  return (
    <section aria-labelledby="study-codes">
      <h2 id="study-codes" className="text-2xl font-medium">
        {t.title}
      </h2>
      <p className="mt-2 max-w-(--measure-body) text-muted-foreground">{t.lead}</p>

      <form onSubmit={submit} className="mt-6 flex max-w-xl flex-wrap items-end gap-3">
        <div className="w-32">
          <Field id="code-count" label={t.count} help={t.range}>
            <Input
              id="code-count"
              type="number"
              inputMode="numeric"
              min={1}
              max={500}
              value={count}
              onChange={(event) => setCount(event.target.value)}
            />
          </Field>
        </div>
        <Button type="submit" disabled={make.isPending || !Number(count)}>
          {make.isPending ? t.making : t.make}
        </Button>
      </form>
      {make.isError ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{t.makeFailed}</AlertDescription>
        </Alert>
      ) : null}

      {codes && codes.length === 0 ? (
        <p className="mt-6 text-muted-foreground">{t.empty}</p>
      ) : null}

      {codes && codes.length > 0 ? (
        <div className="mt-6">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">{t.total(codes.length)}</p>
            <Button asChild variant="outline" size="sm">
              <Link to="/studies/$studyId/karten" params={{ studyId: String(studyId) }}>
                {t.cards}
              </Link>
            </Button>
          </div>
          <ul className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
            {codes.map((code) => (
              <li
                key={code.id}
                className="flex items-center justify-between gap-3 border-b py-2"
              >
                <span className="font-mono tracking-wider">{code.code}</span>
                {code.used ? (
                  <Badge variant="outline">{t.used}</Badge>
                ) : (
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(code.id)}
                  >
                    {t.delete}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {remove.isError ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>
            {remove.error instanceof ApiError && remove.error.status === 409
              ? remove.error.message
              : t.deleteFailed}
          </AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
