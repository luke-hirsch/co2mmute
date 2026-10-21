# Copy

German only. One dictionary: `frontend/src/lib/de.ts`. No i18n library — the game is played in one
language and a library would only be indirection.

**Nothing hardcoded in JSX.** If a component renders a word a player reads, it comes from `de.ts`.
Parameterised copy is a function in the dictionary, never string concatenation at the call site.
`tests/design/german.test.ts` reads every `.tsx` for English.

The one exception is `/app/styleguide`, which no player ever sees; its own chrome is hardcoded. The
components it *renders* still follow the rule, which is the point.

## du, never Sie

Everywhere, legal pages included. `tests/lib/de.test.ts` fails on `Sie`/`Ihre`/`Ihren`/`Ihrem`/
`Ihnen` anywhere in the dictionary, so this is a check, not a habit.

## Records that mirror the backend

Where the backend can send a fixed set of values, the dictionary types it as a `Record` so a new
backend value **breaks the build** instead of rendering nothing:

| dictionary | mirrors | values |
| --- | --- | --- |
| `de.join.blocked` | `_joinable()` in `game/views_join.py` | `started` `ended` `full` |
| `de.modes` | `AgentRoute.transport_mode` | `car` `public` `bike` `walk` |
| `de.seat.status` | the status constants in `game/roster.py` | `ready` `making_move` `waiting` `not_connected` |

`tests/lib/de.test.ts` also asserts each set matches exactly, so a backend change that adds a value
is caught even if TypeScript is satisfied.

## Words that are easy to get wrong

- **Gruppe** — a game agent: commuters a seat plays, with one home and one workplace. In code and in
  the API it stays `agent`.
- **alle Pendler** — the sum over all Gruppen.
- **Spielleitung** — the host. Not "Host", not "Lehrer" (a student may be running it). The host's own
  row in the roster always reads „Spielleitung“.
- **Leitstelle** — the host machine. **an der Leitstelle** is a seat played there
  (`controlled_by_host`), which is *not* the host's own row; never show the two as the same thing.
- **Platz / Platz-Code** — a seat, and the seven-character code that moves it to another device. Not
  "Ticket", not "Session".
- **Spiel-ID** — the six characters the host shows for a game.
- **Code** — what a player types to join. The join box names no kind of code („Code eingeben und
  mitspielen“, „Dein Code“): a player does not know what they scanned, a game id, a seat code or a
  participant code.
- **wählt noch / abgeschickt** — a player still choosing vs. one who has submitted. The roster
  distinguishes these and so must the screen; „bereit“ means neither (no round is open).
- **Runde** — never "Level".
- **No school words** — „Klasse“, „Lehrer“, „Schule“ — in the interface. The tests allowlist the
  few places a host names their own game.

## Tone

Short sentences. Say what happened and what to do. No exclamation marks, no cheerleading, no emoji
in copy.

Error text names the thing that failed and the next action: „Das Passwort stimmt nicht.“, not
„Fehler bei der Authentifizierung.“

A label names what the person holds, never the system's kinds or where it came from: „Dein Code“,
not „Teilnahmecode“ or „Platz-Code aus dem QR“.

## Never in copy, logs or error reports

Player names. They are the only identifying thing collected, the players are minors, and they are
anonymised once a game is over. A name must not reach a log line, a toast that gets captured, or a
Django message. See `AGENTS.md`, "players are minors".
