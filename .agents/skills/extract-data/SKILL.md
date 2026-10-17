---
name: extract-data
description: Export the research data of finished co2mmute games to one sqlite file and answer questions from it. Use when someone wants numbers out of played games ("how did the classes commute", "what did the votes choose", "does a bus lane change the CO₂").
---

# extract-data

The games played on an instance, as a file you can query. `export_research_data` writes it; this
skill is how to run it, what is in it, and what you may and may not say from it.

## before you start

- A clone set up natively as in `README.md`, pointed at the instance's database. On a server that
  runs compose, the command runs in the backend container (below); the path you pass is inside the
  container, and you copy the file out.
- Nothing else. The file is read with any sqlite client; Python's `sqlite3` is enough.

Locally, `devops/dev.sh manage <command>` runs `manage.py` in `backend/`, so **the path you pass is
absolute**. On a server with compose, the same command is
`docker compose -f devops/docker-compose.yaml exec backend ./manage.py <command>`.

## 1. export

```bash
devops/dev.sh manage export_research_data /abs/path/research.sqlite
docker compose -f devops/docker-compose.yaml exec backend ./manage.py export_research_data /tmp/research.sqlite
```

It prints the rows per table. A file that is already there is replaced. Only games that are **over
and anonymised** leave. A game that ended less than 24 hours ago is still in its grace period (it is
being debriefed) and stays out until the grace ends and the hourly job anonymises it. A running game
is not data yet. `manage.py anonymise_games --all` anonymises every ended game at once, grace period
or not: run it only when the host is done with the debrief.

## 2. what is in it

Players are numbers, nothing else. The file has no names, no host account, no game name, no
chat, no QR code, no cookie. It is one row per thing:

| table | one row per | holds |
| --- | --- | --- |
| `game` | game | the map (`map_id`, `map_name`), the day it ended (`ended_on`), why (`end_reason`), `max_rounds`, `rounds_played`, `seats`, `gruppen_per_seat`, `people_per_agent`, the budget `co2_kg_per_person` and the `max_co2_kg` the game ends on, `timetable_factor`, `balanced_deal`, `map_updates`, `co2_hidden` (1: that class never saw a CO₂ figure or the budget until the summary, and the budget did not end it) |
| `player` | seat | `id`, its game, whether it was `left_early` |
| `round` | round | status, `total_co2_g` and `total_cost_eur` of the players, `network_co2_g` and `network_cost_eur` of the lines nobody rode, `stalemate_count`, the version that won the vote (`winning_version_id`), `tie`, `forced` |
| `ballot_option` | option on a round's ballot | the version and the votes it got |
| `vote` | seat × round | the version it voted for; no version is "leave the map as it is" |
| `stichwahl_vote` | seat × round | whether it wanted another vote after a tie |
| `map_version` | version | its `name`, and what it changes in the words the ballot used (`poll_text`, `revert_poll_text`), `is_base`, the version it was made from |
| `node` | home or workplace used | the map's name for it and its place |
| `gruppe_round` | Gruppe × round | `player_id`, `gruppe` (1, 2, …), `pendlertyp`, `home_node_id`, `destination_node_id`, `mode`, `optimization`, `distance_m`, `trip_min` and `return_min`, `cost_eur` (the real cost), `paid_eur` (what the commuter paid), `co2_g_per_person`, `congestion_delay_min`, `wait_time_min` |

Per-minute street snapshots are not in the file. If you ever add them: their `speed_kmh` is a
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

## 3. sample queries

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
```

## the rules

- **n beside every number.** A mean of three Gruppen is not a finding. Say how many games, seats
  and Gruppen stand behind it, and what the spread is when it is wide.
- **No claim about one person.** The unit is a Gruppe, a round, a game. Don't write "Spieler 3
  drove every day"; a seat is a handful of Gruppen played by a student.
- **No join that re-identifies anyone.** Don't combine `ended_on`, a map, a seat count and a
  Pendlertyp to point at a class. Don't ask anyone which `player_id` was theirs, and don't take the
  file anywhere else than where the work is done.
- **The game is a model, not a city.** The CO₂ and the minutes are the simulation's, on a
  calibrated map; say "in the game", and name the map and the budget.
- **Games differ in their setup.** Compare across `co2_kg_per_person`, `balanced_deal`,
  `co2_hidden`, `timetable_factor` and map only after grouping by them. A hidden game's players chose
  without seeing CO₂, and its rounds run past the budget, so don't pool it with the others.
- A column the file lacks is not to be asked for. Names, the game's name and the chat are not
  exported on purpose; don't go to the database for them.
