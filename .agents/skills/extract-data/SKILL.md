---
name: extract-data
description: Export the research data of finished co2mmute games to one zip of CSV files and answer questions from it. Use when someone wants numbers out of played games ("how did the classes commute", "what did the votes choose", "does a bus lane change the CO₂").
---

# extract-data

The games played on an instance, as CSV files you can query. `export_research_data` writes them in
one zip; this skill is how to run it, what is in it, and what you may and may not say from it.

## before you start

- A clone set up natively as in `README.md`, pointed at the instance's database. On a server that
  runs compose, the command runs in the backend container (below); the path you pass is inside the
  container, and you copy the file out.
- Nothing else. The zip opens in Excel, R, pandas and SPSS; for your own queries Python's standard
  library is enough (`zipfile`, `csv`, and `sqlite3` in memory, see "loading").

Locally, `devops/dev.sh manage <command>` runs `manage.py` in `backend/`, so **the path you pass is
absolute**. On a server with compose, the same command is
`docker compose -f devops/docker-compose.yaml exec backend ./manage.py <command>`.

## 1. export

```bash
devops/dev.sh manage export_research_data /abs/path/research.zip
docker compose -f devops/docker-compose.yaml exec backend ./manage.py export_research_data /tmp/research.zip
```

It prints the rows per table. A zip that is already there is replaced; a directory as the path gets
`research-<date>.zip` inside it. The zip holds one `<table>.csv` per table and a `README.txt` with
every column: UTF-8 with a byte-order mark (Excel shows the umlauts; pandas wants
`encoding="utf-8-sig"`), comma-separated, a point for decimals, an empty field is no value. Only games that are **over
and anonymised** leave. A game that ended less than 24 hours ago is still in its grace period (it is
being debriefed) and stays out until the grace ends and the hourly job anonymises it. A running game
is not data yet. `manage.py anonymise_games --all` anonymises every ended game at once, grace period
or not: run it only when the host is done with the debrief (`--dry-run` lists the games it would take).

## 2. what is in it

Players are numbers, nothing else. The zip has no names, no host account, no game name, no
chat, no QR code, no cookie. It is one row per thing:

| table | one row per | holds |
| --- | --- | --- |
| `game` | game | the map (`map_id`, `map_name`), the day it ended (`ended_on`), why (`end_reason`), `max_rounds`, `rounds_played`, `seats`, `gruppen_per_seat`, `people_per_agent`, the budget `co2_kg_per_person` and the `max_co2_kg` the game ends on, `timetable_factor`, `balanced_deal`, `map_updates`, `co2_hidden` (1: that class never saw a CO₂ figure or the budget until the summary, and the budget did not end it) |
| `player` | seat | `id`, its game, `joined_s` (seconds from the game being opened to the seat joining), whether it was `left_early` |
| `round` | round | status, `total_co2_g` and `total_cost_eur` of the players, `network_co2_g` and `network_cost_eur` of the lines nobody rode, `stalemate_count`, the version that won the vote (`winning_version_id`), `tie`, `forced` |
| `ballot_option` | option on a round's ballot | the version and the votes it got |
| `vote` | seat × round | the version it voted for; no version is "leave the map as it is"; `voted_s`, seconds from the round's result being ready |
| `stichwahl_vote` | seat × round | whether it wanted another vote after a tie, and `voted_s` |
| `map_version` | version | its `name`, and what it changes in the words the ballot used (`poll_text`, `revert_poll_text`), `is_base`, the version it was made from |
| `node` | home, workplace or end of a street travelled | the map's name for it and its place (`x`, `y` in map units) |
| `edge` | street or rail travelled | its two nodes, its name, `length_m` |
| `pt_line` | bus or train line ridden | `kind` (bus, or train, which includes the tram), `id`, `name`; `(kind, id)` is the key |
| `gruppe_round` | Gruppe × round | `player_id`, `gruppe` (1, 2, …), `pendlertyp`, `home_node_id`, `destination_node_id`, `mode`, `optimization`, `distance_m`, `trip_min` and `return_min`, `cost_eur` (the real cost), `paid_eur` (what the commuter paid), `co2_g_per_person`, `congestion_delay_min`, `wait_time_min` |
| `route_segment` | street or rail × Gruppe × round × direction | `step` along the route, `mode` (car, bus, train, bike, walk), `edge_id`, `pt_line_id` for bus and train; `direction` is `out` or `home` |
| `replay_round` | round with a recording | the recording's frame: `people_per_dot`, `tick_duration_min`, `end_min`, `home_start_min`, and the people not home (`not_home_unfinished`, `not_home_stranded`) |
| `replay_dot` | dot of the recording | a sampled person or a line vehicle: `pass` (out, home), `player_id` and `gruppe` (empty for a line vehicle), `line`, `mode`, `wants_min` (when they wanted to leave), `ending`, and `legs`, JSON: `[kind, ref, from_min, to_min, from_node]` with kind `e` crossing edge `ref`, `s` waiting at node `ref`, `r` riding the dot `ref`. One dot stands for `people_per_dot` people |

With the study app on (the zip has no `study*` files otherwise), for the studies that have an
exported game:

| table | one row per | holds |
| --- | --- | --- |
| `study` | study | `name` and `description`, the researchers' own words |
| `study_game` | study × game | which exported games belong to which study |
| `study_seat` | participant code × game | the `code` as it is, the game, the seat (`player_id`) that played it |
| `study_note` | note | `about_date`, `created_on`, `text`, `meta` (flat JSON text); never who wrote it |
| `study_note_game` | note × game | the exported games a note is about |

Per-minute street snapshots are not in the zip. If you ever add them: their `speed_kmh` is a
running mean since minute 0, not that minute's speed.

Words:

- **Gruppe**: a game agent — a group of commuters a seat plays, all with one home, one workplace,
  one Pendlertyp. `people_per_agent` people stand behind each. `co2_g_per_person` is one commuter's
  day; the group's is that × `people_per_agent`.
- **Stichwahl**: the second vote after a tie (`StalemateVote` in the code). Two ties leave the map
  as it is.
- **Leitstelle**: the host's machine. A seat can be played there; the file does not tell.
- **alle Pendler**: the sum over every Gruppe, which the budget is measured against.
- **Pendlertyp**: who a Gruppe is played as. Only the standard ones keep their name; one a host
  wrote reads `eigener Typ`.
- **A version is described by what it changes**: its `poll_text` ("Die Karte soll eine Busspur
  bekommen"). Compare versions through that, never through `name` or `id` alone: ids differ between
  maps and instances.
- **`timetable_factor`** is the share of the timetable the class paid (CO₂ and cost) in that game.
  Compare CO₂ between games only with it beside.

## 3. loading and sample queries

The queries are SQL; load the zip into sqlite in memory and ask:

```python
import csv, io, sqlite3, zipfile
db = sqlite3.connect(":memory:")
with zipfile.ZipFile("research.zip") as z:
    for name in z.namelist():
        if not name.endswith(".csv"):
            continue
        rows = list(csv.reader(io.StringIO(z.read(name).decode("utf-8-sig"))))
        table, columns = name[:-4], rows[0]
        db.execute(f"CREATE TABLE {table} ({', '.join(columns)})")
        db.executemany(
            f"INSERT INTO {table} VALUES ({','.join('?' * len(columns))})",
            [[v if v != "" else None for v in row] for row in rows[1:]],
        )
```

Numbers arrive as text (`CAST(x AS REAL)`, or compare after `+ 0`); `NULL` is an empty field.

```sql
-- how many games and seats there are
SELECT COUNT(*) AS games, SUM(seats) AS seats FROM game;

-- mean CO₂ per person and day by mode, with n
SELECT mode, COUNT(*) AS n, ROUND(AVG(co2_g_per_person), 1) AS co2_g
FROM gruppe_round GROUP BY mode;

-- the same by Pendlertyp
SELECT pendlertyp, COUNT(*) AS n, ROUND(AVG(co2_g_per_person), 1) AS co2_g,
       ROUND(AVG(trip_min + return_min), 1) AS day_min
FROM gruppe_round GROUP BY pendlertyp;

-- CO₂ of the players by round number, per budget
SELECT g.co2_kg_per_person AS budget, r.round_number, COUNT(*) AS n,
       ROUND(AVG(r.total_co2_g) / 1000, 1) AS kg
FROM round r JOIN game g ON g.id = r.game_id
GROUP BY budget, r.round_number;

-- what the classes voted for, by what the version changes
SELECT v.poll_text, SUM(b.votes) AS votes, COUNT(*) AS ballots
FROM ballot_option b JOIN map_version v ON v.id = b.version_id
GROUP BY v.poll_text ORDER BY votes DESC;

-- how often a vote went to a Stichwahl, and how those ended
SELECT stalemate_count, COUNT(*) AS rounds,
       SUM(winning_version_id IS NULL) AS left_as_it_was
FROM round WHERE stalemate_count > 0 GROUP BY stalemate_count;

-- which streets the classes used, by mode
SELECT e.name, s.mode, COUNT(*) AS trips
FROM route_segment s JOIN edge e ON e.id = s.edge_id
GROUP BY e.name, s.mode ORDER BY trips DESC LIMIT 10;

-- how long after the result was ready the seats voted, per round (seconds)
SELECT round_id, MIN(voted_s) AS first, MAX(voted_s) AS last, COUNT(*) AS votes
FROM vote GROUP BY round_id;
```

## the rules

- **n beside every number.** A mean of three Gruppen is not a finding. Say how many games, seats
  and Gruppen stand behind it, and what the spread is when it is wide.
- **No claim about one person.** The unit is a Gruppe, a round, a game. Don't write "Spieler 3
  drove every day"; a seat is a handful of Gruppen played by a student. The one exception is a study
  code: `study_seat` lets you follow a code through the games of its study ("the person with this
  code rode the bike in game one, drove in game two"). A code is not a name. Never try to tie one
  to a person, and don't join it with anything outside the file that could.
- **Notes are the group's own words.** Quote a `study_note` as theirs; it is context for a study,
  never a result for one person.
- **No join that re-identifies anyone.** Don't combine `ended_on`, a map, a seat count and a
  Pendlertyp to point at a class. Don't ask anyone which `player_id` was theirs, and don't take the
  file anywhere else than where the work is done.
- **What the new tables allow.** `route_segment` says which streets and lines a class used, not why:
  never write that a Gruppe "avoided" or "preferred" a street, only that it used it. The times
  (`joined_s`, `voted_s`) are how long things took, not when: say "the seats voted within a minute
  of the result", never a time of day, and never point at one seat as slow. A `replay_dot` is a
  sampled person standing for `people_per_dot` people: count dots only with that beside, and don't
  follow one dot as a person.
- **The game is a model, not a city.** The CO₂ and the minutes are the simulation's, on a
  calibrated map; say "in the game", and name the map and the budget.
- **Games differ in their setup.** Compare across `co2_kg_per_person`, `balanced_deal`,
  `co2_hidden`, `timetable_factor` and map only after grouping by them. A hidden game's players chose
  without seeing CO₂, and its rounds run past the budget, so don't pool it with the others.
- A column the file lacks is not to be asked for. Names, the game's name and the chat are not
  exported on purpose; don't go to the database for them.
