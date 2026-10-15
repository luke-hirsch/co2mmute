import { de } from "@/lib/de";
import { modeTally } from "@/lib/game/groups";
import type { SummaryGroup } from "@/lib/queries/summary";

/**
 * "Meine Gruppen": each Gruppe of this seat over the whole game, with the
 * Pendlertyp it was dealt.
 *
 * The question the debrief asks is whether a Gruppe played its type, so each
 * one gets the figures a type is judged by, and the reader does the judging:
 * the Sparfuchs by what it paid, the Sportskanone by its modes, "Bloß kein
 * Stress" by its changes, "Öko aus Überzeugung" by its CO₂, "Auf den letzten
 * Drücker" by its time. Distance is there because a cheap Gruppe with the
 * longest way to work still pays the most. Nothing is ranked or marked: like
 * the three lists, who did well is for the class to say.
 *
 * One day there and back for one commuter, the mean over the rounds — the
 * same frame as "pro Person", so the figures read against the lists.
 */
export function GroupList({ groups }: { groups: readonly SummaryGroup[] }) {
  return (
    <div className="mt-8">
      <p className="max-w-(--measure-body) text-muted-foreground">
        {de.summary.groupsLead}
      </p>

      <ul className="mt-6 border-t border-border">
        {groups.map((group) => (
          <li key={group.agent_id} className="border-b border-border py-6">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="text-lg font-medium">
                {de.round.agent(group.agent_id)}
                {group.destination ? (
                  <span className="font-normal text-muted-foreground">
                    {" "}
                    {group.home ?? de.round.home} → {group.destination}
                  </span>
                ) : null}
              </h3>
              <p className="font-mono text-sm tabular-nums text-muted-foreground">
                {de.summary.groupRounds(group.rounds)}
              </p>
            </div>

            {group.persona ? (
              <p className="mt-2 max-w-(--measure-body) border-l-[3px] border-brandaccent pl-3">
                <span className="font-medium">{group.persona.name}</span>
                {group.persona.description ? (
                  <span className="text-muted-foreground">
                    {" "}
                    – {group.persona.description}
                  </span>
                ) : null}
              </p>
            ) : (
              <p className="mt-2 text-muted-foreground">
                {de.summary.groupNoPersona}
              </p>
            )}

            {group.rounds === 0 ? (
              <p className="mt-4 text-sm text-muted-foreground">
                {de.summary.groupNone}
              </p>
            ) : (
              <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
                <Figure label={de.summary.modes} wide>
                  {modeTally(group.modes)
                    .map(({ mode, count }) =>
                      de.summary.groupModeCount(count, de.modes[mode]),
                    )
                    .join(", ")}
                </Figure>
                <Figure label={de.summary.groupTime}>
                  {de.round.duration(group.time_min)}
                </Figure>
                <Figure label={de.summary.groupDistance}>
                  {`${de.summary.decimal(group.distance_km)} km`}
                </Figure>
                <Figure label={de.summary.groupSpeed}>
                  {`${de.summary.decimal(group.speed_kmh)} km/h`}
                </Figure>
                <Figure label={de.summary.groupPaid}>
                  {de.between.eur(group.paid_eur)}
                </Figure>
                <Figure label={de.summary.groupCo2}>
                  {de.between.grams(group.co2_g)}
                </Figure>
                <Figure label={de.summary.groupChanges}>
                  {de.summary.decimal(group.changes)}
                </Figure>
              </dl>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Figure({
  label,
  wide = false,
  children,
}: {
  label: string;
  /** The mode tally is words, not a number: it gets the row to itself. */
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={wide ? "col-span-2 sm:col-span-4" : undefined}>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={wide ? "mt-0.5" : "mt-0.5 font-mono tabular-nums"}>
        {children}
      </dd>
    </div>
  );
}
