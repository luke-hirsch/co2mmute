import { Link } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import Loading from "@/components/Loading";
import { de } from "@/lib/de";
import { useStudy, useStudyCards } from "@/lib/queries/studies";

/**
 * `/app/studies/$studyId/karten` — the codes as a sheet of cards to print.
 *
 * The route has no app header (see `app-chrome.ts`), so the sheet is all that
 * prints; the toolbar is `print:hidden`. Paper is white with black ink whatever
 * the colour mode is, and each card has a dashed border to cut along.
 */
export function StudyCards({ studyId }: { studyId: number }) {
  const t = de.studies.cards;
  const { data: study } = useStudy(studyId);
  const { data: cards, isLoading, isError } = useStudyCards(studyId);

  return (
    <main className="min-h-dvh bg-background px-4 py-8 text-foreground sm:px-6 print:bg-white print:p-0 print:text-black">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-3 print:hidden">
          <div>
            <Button asChild variant="link" size="sm" className="-ml-4">
              <Link to="/studies/$studyId" params={{ studyId: String(studyId) }}>
                {t.back}
              </Link>
            </Button>
            <h1 className="text-2xl font-medium">
              {t.title}
              {study ? ` · ${study.name}` : ""}
            </h1>
          </div>
          <Button onClick={() => window.print()} disabled={!cards?.length}>
            {t.print}
          </Button>
        </div>

        {isLoading ? <Loading label={t.loading} /> : null}
        {isError ? (
          <Alert variant="destructive">
            <AlertDescription>{t.failed}</AlertDescription>
          </Alert>
        ) : null}
        {cards && cards.length === 0 ? (
          <p className="text-muted-foreground">{t.empty}</p>
        ) : null}

        {cards && cards.length > 0 ? (
          <ul className="grid grid-cols-1 gap-4 min-[560px]:grid-cols-2 print:grid-cols-2 print:gap-0">
            {cards.map((card) => (
              <li
                key={card.code}
                className="flex break-inside-avoid items-center gap-4 border border-dashed border-foreground/60 p-5 print:border-black"
              >
                <img
                  src={card.qr}
                  alt={t.qrAlt(card.code)}
                  className="size-28 shrink-0 bg-white"
                />
                <div className="min-w-0">
                  <p className="font-mono text-2xl tracking-widest">{card.code}</p>
                  <p className="mt-2 text-sm">{t.instruction}</p>
                  <p className="mt-1 text-xs text-muted-foreground print:text-black">
                    {t.orType}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </main>
  );
}
