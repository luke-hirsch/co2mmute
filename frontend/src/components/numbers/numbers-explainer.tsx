import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { de } from "@/lib/de";
import { usePeoplePerAgent } from "@/components/numbers/use-people-per-agent";

/**
 * What the numbers on screen are made of — the one thing nobody had written
 * down.
 *
 * `8 h 18 min` and `14.541,15 €` are not wrong arithmetic; they are unreadable
 * without the sentence "eine Gruppe steht für hundert Menschen". Same for a
 * round total that is larger than the sum of its own rows, and for a cost column
 * that is not what anybody paid.
 *
 * **It never appears next to the ballot** (Lukas, 2026-09-22). The class needs to
 * know that a line runs empty or not — but putting that beside the vote hands
 * them the argument they should bring up themselves. So it lives in an overlay
 * of its own, opened from the screens that show figures, and reads out in full on
 * the screens where there is nothing to do but wait.
 */
function ExplainerBody({ peoplePerAgent }: { peoplePerAgent: number | null }) {
  const sections = [
    {
      title: de.numbers.scaleTitle,
      body:
        peoplePerAgent === null
          ? de.numbers.scaleBodyPlain
          : de.numbers.scaleBody(peoplePerAgent.toLocaleString("de-DE")),
    },
    { title: de.numbers.timeTitle, body: de.numbers.timeBody },
    { title: de.numbers.paidTitle, body: de.numbers.paidBody },
    { title: de.numbers.networkTitle, body: de.numbers.networkBody },
    { title: de.numbers.jamTitle, body: de.numbers.jamBody },
  ];

  return (
    <dl className="space-y-6">
      {sections.map((section) => (
        <div key={section.title}>
          <dt className="font-medium">{section.title}</dt>
          <dd className="mt-1 max-w-(--measure-body) text-muted-foreground">
            {section.body}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * The overlay, with the link that opens it. Goes wherever figures are on screen.
 *
 * The trigger is a link rather than a button: it is an aside, and a second
 * button beside "Weiter" would compete with the one thing the screen wants
 * pressed.
 */
export function NumbersExplainerDialog() {
  const peoplePerAgent = usePeoplePerAgent();
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground">
        {de.numbers.explain}
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{de.numbers.explainTitle}</DialogTitle>
          <DialogDescription>{de.numbers.explainLead}</DialogDescription>
        </DialogHeader>

        <ExplainerBody peoplePerAgent={peoplePerAgent} />

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {de.numbers.close}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The same text, read out in full, for a screen whose whole content is waiting:
 * the turn is sent, or the class is discussing. There is nothing to press and
 * nothing to hide it behind.
 */
export function NumbersExplainerPanel({ className }: { className?: string }) {
  const peoplePerAgent = usePeoplePerAgent();

  return (
    <section className={className}>
      <h3 className="text-sm text-muted-foreground">{de.numbers.explainTitle}</h3>
      <div className="mt-4">
        <ExplainerBody peoplePerAgent={peoplePerAgent} />
      </div>
    </section>
  );
}
