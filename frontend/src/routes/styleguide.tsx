import { useState, type ReactNode } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { InfoIcon, TriangleAlertIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

import { Co2Bar } from "@/components/metro/co2-bar";
import {
  CodeDisplay,
  CodeInput,
  DepartureBoard,
} from "@/components/metro/departure-board";
import { LineLegend, LineSwatch, ModeBadge, ModeLabel } from "@/components/metro/line";
import { modeOrder, modeStyle } from "@/components/metro/mode";
import { PauseBanner } from "@/components/metro/pause-banner";
import { SeatRow } from "@/components/metro/seat-row";
import { Track, TrackStop } from "@/components/metro/track";

import { setColorMode } from "@/lib/color-mode";
import { useResolvedColorMode } from "@/hooks/use-color-mode";
import { de, type TransportMode } from "@/lib/de";
import { kgToGrams } from "@/lib/co2";
import { cn } from "@/lib/utils";

/**
 * Every token, primitive and pattern on one page, at real size.
 *
 * This is the tray the design system is laid out on: fifteen buttons spread
 * across fifteen screens all look fine on their own, and only side by side does
 * the one that drifted become obvious. It is also what gets screenshotted in
 * WebKit — light and dark, phone and desktop — so a token change that moves
 * something unrelated shows up as a pixel diff instead of as a surprise weeks
 * later.
 *
 * Not linked from anywhere and never seen by a player. Its own chrome is
 * therefore hardcoded rather than routed through de.ts — the rule is about
 * player-facing copy, and the components below do follow it.
 *
 * Rules this page is the evidence for: .claude/design/rulebook.md
 */
export const Route = createFileRoute("/styleguide")({
  component: Styleguide,
});

/**
 * Each section rides one of the four lines, cycling through them down the page.
 * Named per section rather than counted during render: a module-level counter
 * would renumber on every re-render, so the colours would change when you hit
 * the theme toggle.
 */
function Section({
  title,
  note,
  line,
  children,
}: {
  title: string;
  note?: string;
  line: TransportMode;
  children: ReactNode;
}) {
  const style = modeStyle[line];
  return (
    <section className="py-12 lg:py-16">
      <div
        className={cn(
          "border-t-[5px] pt-5",
          style.border,
          style.stroke,
        )}
      >
        <h2 className="text-2xl/9 sm:text-3xl/10">{title}</h2>
        {note ? (
          <p className="mt-3 max-w-(--measure-body) text-muted-foreground">
            {note}
          </p>
        ) : null}
      </div>
      <div className="mt-10">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-x-8 gap-y-3 py-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <p className="font-mono text-xs text-muted-foreground">{label}</p>
      <div className="flex flex-wrap items-center gap-4">{children}</div>
    </div>
  );
}

function Swatch({ token, name }: { token: string; name: string }) {
  return (
    <div className="flex w-32 flex-col gap-2">
      <div
        className="h-14 rounded-md border border-border"
        style={{ background: `var(${token})` }}
      />
      <p className="font-mono text-[11px] leading-tight text-muted-foreground">
        {name}
      </p>
    </div>
  );
}

function Styleguide() {
  const mode = useResolvedColorMode();
  const [code, setCode] = useState("");

  return (
    <div className="min-h-dvh px-6 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-end justify-between gap-6 pt-16 pb-4">
          <div>
            <h1 className="text-4xl/[1.05] font-medium sm:text-5xl/[1.02]">
              Styleguide
            </h1>
            <p className="mt-4 max-w-(--measure-lead) text-lg/8 text-muted-foreground">
              Jedes Token, jedes Bauteil, einmal nebeneinander. Was hier nicht
              steht, wird auf keinem Screen erfunden.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={mode === "light" ? "default" : "outline"}
              size="sm"
              onClick={() => setColorMode("light")}
            >
              Hell
            </Button>
            <Button
              variant={mode === "dark" ? "default" : "outline"}
              size="sm"
              onClick={() => setColorMode("dark")}
            >
              Dunkel
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setColorMode("system")}>
              System
            </Button>
          </div>
        </header>

        <Section
          title="Linien"
          line="car"
          note="Zwei Farben tragen alle vier Linien: Primary fürs Auto, Akzent für Bus &amp; Bahn, ein gedämpftes Primary fürs Rad, Tinte für zu Fuß. Zwei Blautöne lassen sich in Strichstärke nicht an der Farbe unterscheiden — deshalb macht das Muster die Arbeit: durchgezogen, gestrichelt, gepunktet."
        >
          <LineLegend className="gap-x-10" />
          <div className="mt-10 flex flex-wrap gap-4">
            {modeOrder.map((m) => (
              <ModeBadge key={m} mode={m} />
            ))}
          </div>
          <div className="mt-8 flex flex-col gap-4">
            {modeOrder.map((m) => (
              <ModeLabel key={m} mode={m} className="text-sm" />
            ))}
          </div>
        </Section>

        <Section
          title="Farben"
          line="public"
          note="Zwei Markenfarben, neutrale Flächen, sonst nichts. Es gibt kein Grün für Erfolg und kein Rot für Gefahr mehr — was Aufmerksamkeit braucht, bekommt den Akzent. Die Werte stehen wortgleich in backend/static/css/custom.css, ein Test vergleicht beide Dateien."
        >
          <Row label="Linien">
            <Swatch token="--color-line-car" name="line-car" />
            <Swatch token="--color-line-pt" name="line-pt" />
            <Swatch token="--color-line-bike" name="line-bike" />
            <Swatch token="--line-walk" name="line-walk" />
          </Row>
          <Separator />
          <Row label="Flächen">
            <Swatch token="--background" name="background" />
            <Swatch token="--card" name="card" />
            <Swatch token="--muted" name="muted" />
            <Swatch token="--accent" name="accent" />
          </Row>
          <Separator />
          <Row label="Schrift und Rand">
            <Swatch token="--foreground" name="foreground" />
            <Swatch token="--muted-foreground" name="muted-foreground" />
            <Swatch token="--border" name="border" />
            <Swatch token="--ring" name="ring" />
          </Row>
          <Separator />
          <Row label="Marke">
            <Swatch token="--primary" name="primary = Auto" />
            <Swatch token="--color-brandaccent" name="accent = Bus & Bahn" />
            <Swatch token="--destructive" name="destructive" />
          </Row>
        </Section>

        <Section
          title="Schrift"
          line="bike"
          note="Systemschrift, kein Webfont — ein fremder Font schickt die IP jedes Besuchers an dessen Server. Höchstens 600er Schnitt; Größe und Abstand trennen die Ebenen, nicht Fettung. Mono nur für IDs, Codes und Zahlen."
        >
          <div className="flex flex-col gap-8">
            <p className="text-4xl/[1.05] sm:text-5xl/[1.02]">
              Eine Stadt. Viele Wege.
            </p>
            <p className="text-2xl/9 sm:text-3xl/10">So läuft eine Runde</p>
            <p className="text-xl/8 font-medium">Vier Wege zum Ziel</p>
            <p className="max-w-(--measure-lead) text-lg/8 text-muted-foreground">
              Lead: höchstens {"46ch"} breit, damit das Auge am Zeilenende
              zurückfindet.
            </p>
            <p className="max-w-(--measure-body) text-base/7">
              Fließtext: höchstens 62 Zeichen breit. Jede Runde wählst du für
              jeden deiner Agenten ein Verkehrsmittel und eine Route. Danach
              rechnet der Server den Verkehr durch und sagt dir, was er gekostet
              hat — an CO₂, an Geld und an Zeit.
            </p>
            <p className="font-mono text-sm text-muted-foreground">
              Mono 4F2A9C · 1 234 kg · Runde 3 von 5
            </p>
          </div>
        </Section>

        <Section
          title="Knöpfe"
          line="walk"
          note="Eine Stufe luftiger als die shadcn-Vorgaben. Höhe 40 px als Normalfall, damit sie auf dem Handy sicher zu treffen sind."
        >
          <Row label="variant">
            <Button>Beitreten</Button>
            <Button variant="secondary">Zurück</Button>
            <Button variant="outline">Abbrechen</Button>
            <Button variant="ghost">Mehr</Button>
            <Button variant="destructive">Spiel beenden</Button>
            <Button variant="link">Datenschutz</Button>
          </Row>
          <Separator />
          <Row label="size">
            <Button size="xs">xs</Button>
            <Button size="sm">sm</Button>
            <Button>default</Button>
            <Button size="lg">lg</Button>
          </Row>
          <Separator />
          <Row label="state">
            <Button disabled>{de.join.submitting}</Button>
            <Button variant="outline" disabled>
              Deaktiviert
            </Button>
          </Row>
        </Section>

        <Section title="Eingaben"
          line="car">
          <div className="flex max-w-sm flex-col gap-3">
            <Label htmlFor="sg-name">{de.join.nameLabel}</Label>
            <Input id="sg-name" placeholder={de.join.namePlaceholder} />
          </div>
          <div className="mt-8 flex max-w-sm flex-col gap-3">
            <Label htmlFor="sg-pw">{de.join.passwordLabel}</Label>
            <Input
              id="sg-pw"
              type="password"
              placeholder={de.join.passwordPlaceholder}
            />
            <p className="text-sm text-muted-foreground">{de.join.passwordHint}</p>
          </div>
          <div className="mt-8 flex max-w-sm flex-col gap-3">
            <Label htmlFor="sg-bad">Mit Fehler</Label>
            <Input id="sg-bad" aria-invalid defaultValue="Ba" />
            <p className="text-sm font-medium">{de.join.nameRequired}</p>
          </div>
        </Section>

        <Section title="Hinweise"
          line="public">
          <div className="flex flex-col gap-5">
            <Alert>
              <InfoIcon />
              <AlertTitle>{de.lobby.waiting}</AlertTitle>
              <AlertDescription>{de.join.seats(3, 6)}</AlertDescription>
            </Alert>
            <Alert variant="destructive">
              <TriangleAlertIcon />
              <AlertTitle>{de.errors.network}</AlertTitle>
              <AlertDescription>{de.actions.retry}</AlertDescription>
            </Alert>
            <PauseBanner />
          </div>
          <Row label="badge">
            <Badge>Neu</Badge>
            <Badge variant="secondary">{de.lobby.host}</Badge>
            <Badge variant="outline">{de.seat.status.waiting}</Badge>
            <Badge variant="destructive">{de.co2.exceeded}</Badge>
          </Row>
          <Row label="skeleton">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-5 w-24" />
            <Skeleton className="size-10 rounded-full" />
          </Row>
        </Section>

        <Section title="Karten und Dialoge"
          line="bike">
          <div className="grid gap-6 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{de.lobby.settings.title}</CardTitle>
                <CardDescription>
                  {de.lobby.roundsCount(5)} · {de.lobby.co2Kg(100)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Co2Bar usedG={kgToGrams(41)} maxG={kgToGrams(100)} />
              </CardContent>
              <CardFooter>
                <Button variant="outline" size="sm">
                  {de.actions.confirm}
                </Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Dialog</CardTitle>
                <CardDescription>
                  Modal mit Titel, Text und zwei Aktionen.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button variant="outline">{de.lobby.leave}</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{de.lobby.leave}</DialogTitle>
                      <DialogDescription>
                        {de.lobby.leaveConfirm}
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline">{de.actions.cancel}</Button>
                      </DialogClose>
                      <Button variant="destructive">{de.actions.confirm}</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardContent>
            </Card>
          </div>
        </Section>

        <Section
          title="Strecke"
          line="walk"
          note="Alles, was eine Reihenfolge hat — Runden, Schritte, Phasen — wird als Linie mit Haltestellen gezeichnet, nicht als Fortschrittsbalken."
        >
          <Track>
            <TrackStop state="done" title={de.round.label(1)}>
              Auto und Rad, 12 kg
            </TrackStop>
            <TrackStop state="done" title={de.round.label(2)}>
              Bus &amp; Bahn, 8 kg
            </TrackStop>
            <TrackStop state="current" title={de.round.of(3, 5)}>
              Läuft gerade
            </TrackStop>
            <TrackStop title={de.round.label(4)} />
            <TrackStop title={de.round.label(5)} />
          </Track>
        </Section>

        <Section
          title="Anzeigetafel"
          line="car"
          note="Codes werden vom Beamer abgelesen: Mono, groß, und in beiden Modi dunkel — eine Tafel ist keine Fläche."
        >
          <div className="grid gap-6 sm:grid-cols-2">
            <DepartureBoard
              label={de.code.boarding}
              footnote={de.code.scanHint}
            >
              <CodeInput value={code} onValueChange={setCode} />
            </DepartureBoard>
            <DepartureBoard
              label={de.code.seatCode}
              footnote={de.code.expiresIn(240)}
            >
              <CodeDisplay code="K7M4QX" />
            </DepartureBoard>
          </div>
        </Section>

        <Section
          title="Plätze"
          line="public"
          note="Eine Zeile der Lobby. „Spielleitung“ ist die eigene Zeile des Hosts, „am Lehrerrechner“ ein Platz, der am Hostgerät mitgespielt wird — das ist nicht dasselbe."
        >
          <ul className="max-w-(--measure-prose) rounded-xl border border-border bg-card px-6">
            <SeatRow name="Mia" status="waiting" online isYou />
            <SeatRow name="Ben" status="making_move" online />
            <SeatRow name="Anna" status="ready" online controlledByHost />
            <SeatRow name="Jonas" status="not_connected" online={false} />
            <SeatRow
              name="Frau Weber"
              status="ready"
              online
              isHost
              action={
                <Button variant="ghost" size="sm">
                  {de.actions.close}
                </Button>
              }
            />
          </ul>
        </Section>

        <Section
          title="CO₂-Budget"
          line="bike"
          note="Zwei Zustände statt drei: läuft, oder will Aufmerksamkeit. Der Balken läuft im Primary und kippt bei 75 % auf den Akzent — die Komplementärfarbe, deshalb liest der Wechsel als Spannung."
        >
          <div className="flex max-w-(--measure-prose) flex-col gap-8">
            <Co2Bar usedG={kgToGrams(18)} maxG={kgToGrams(100)} />
            <Co2Bar usedG={kgToGrams(74)} maxG={kgToGrams(100)} />
            <Co2Bar usedG={kgToGrams(76)} maxG={kgToGrams(100)} />
            <Co2Bar usedG={kgToGrams(112)} maxG={kgToGrams(100)} />
          </div>
        </Section>

        <footer className="flex items-center gap-3 border-t border-border py-12 text-sm text-muted-foreground">
          <LineSwatch mode="walk" />
          Ende der Strecke.
        </footer>
      </div>
    </div>
  );
}
