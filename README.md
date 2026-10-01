# CO2MMUTE

Ein Verkehrsspiel für den Unterricht — a classroom traffic game.
Live unter [co2mmute.stsds.tu-berlin.de](https://co2mmute.stsds.tu-berlin.de/).

**[Deutsch](#deutsch) · [English](#english)**

---

## Deutsch

co2mmute ist ein browserbasiertes Mehrspieler-Verkehrsspiel: eine Klasse pendelt gemeinsam über
eine Stadtkarte, wählt pro Runde Verkehrsmittel und Routen, und der Server simuliert, was daraus
wird — CO₂, Kosten, Fahrzeit. Zwischen den Runden stimmt die Klasse über eine Änderung an der Karte
ab, eine Busspur oder eine neue Linie, und fährt die nächste Runde darauf. Grundlage ist der
technische Teil der Masterarbeit von **Sebastian Werblinski** über agentenbasierte Pendlermodelle
an der Freien Universität Berlin (`master_thesis.pdf`); der Code hier ist eine vollständige
Neuentwicklung danach, an der TU Berlin.
Gerechnet wird mit einem Link-Queue-Modell, mesoskopisch, dieselbe Familie wie MATSim.

**Stack:** Django 5.2 + DRF auf Daphne (ASGI), Channels, Celery, Postgres 18, Redis; React 19 +
Vite + TypeScript als SPA. Wie gespielt wird: [`docs/de-ueberblick.md`](docs/de-ueberblick.md).

### Was wo liegt

| Pfad                | Inhalt                                                            |
| ------------------- | ----------------------------------------------------------------- |
| `backend/co2mmute/` | Django-Konfiguration — Settings, URLs, ASGI, Celery                |
| `backend/game/`     | Sitzungen, Spieler, Runden, Spielzüge, Abstimmungen, Websockets    |
| `backend/sim/`      | die Verkehrssimulation als reines Python-Paket, ohne Django        |
| `backend/maps/`     | Kartengraph, Versionierung, REST-API des Karteneditors             |
| `backend/content/`  | kleines CMS für die öffentlichen Seiten                            |
| `backend/template/` | Django-Templates — Landing, Lobby, Beitritt, Rechtstexte, Login    |
| `frontend/`         | die SPA — Spielbildschirm, Hostseiten, Karteneditor                |
| `devops/`           | `dev.sh`, docker-compose, nginx                                    |
| `map_examples/`     | die gespielte Karte als JSON — Berlin Mitte-West, acht Versionen   |
| `docs/`             | Dokumentation                                                      |
| `.github/`          | CI und das Deployment                                              |

Es ist ein Hybrid, kein reines SPA: Landing Page, Beitritt, Rechtstexte, Login und Admin sind
servergerenderte Django-Templates, das Spiel und der Editor sind React.

### Lokal starten

Zwei Wege — `devops/dev.sh` ist der Arbeitsalltag, `docker compose` ist die Anordnung, die auch
deployt wird.

Beide brauchen ein TLS-Zertifikat: die Spieler-Cookies sind `Secure`, über plain http wirft der
Browser sie wortlos weg. Selbstsigniert reicht.

```bash
mkdir -p devops/nginx/certs && openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout devops/nginx/certs/selfsigned.key -out devops/nginx/certs/selfsigned.crt \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

#### Nativ, ohne Docker

Gebraucht: Python 3.13, Node 20+, Redis oder Valkey, und — nur für die Testsuite — Postgres 18.
Homebrew-Befehle; unter Linux dein Paketmanager.

```bash
pyenv virtualenv 3.13.3 commute        # dev.sh sucht $VIRTUAL_ENV, ~/.pyenv/versions/commute, ./.venv
~/.pyenv/versions/commute/bin/pip install -r backend/requirements.txt 'psycopg[binary]'

(cd backend && npm ci)                 # Tailwind für die Django-Templates
(cd frontend && npm ci)

brew services start valkey             # Channel Layer, Cache und Celery-Broker, auf Datenbank 3

brew install postgresql@18 && brew services start postgresql@18   # nur für die Suite
psql postgres -c "CREATE ROLE commute LOGIN CREATEDB PASSWORD 'commute'"
createdb -O commute commute

devops/dev.sh up
```

Danach liegt alles auf **https://localhost:5173** — Vite proxyt jeden Pfad, der Django gehört, so
wie nginx es im Container tut. Die App läuft auf sqlite.

Weitere Befehle: `status`, `logs <dienst> -f`, `restart <dienst>`, `manage <args>`, `reset-db`,
`down`. Celery lädt nicht automatisch neu — nach Änderungen an `game/tasks.py` oder der Simulation
`devops/dev.sh restart worker`.

#### Docker compose

```bash
cp devops/env_template.txt devops/.env
```

Minimum für lokal: `POSTGRES_DB/USER/PASSWORD`, ein `DJANGO_SECRET_KEY` (ohne startet nichts),
`DJANGO_ALLOWED_HOSTS=localhost`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost` und
`DJANGO_BASE_URL=https://localhost`. `DJANGO_BASE_URL` ist die einzige Quelle für die URL im
QR-Code — steht sie falsch, bricht nichts, es zeigen nur alle QR-Codes auf `localhost`.

```bash
docker compose -f devops/docker-compose.yaml up -d --build
```

Alles auf **https://localhost**. Migrationen, Tailwind und `collectstatic` macht der Entrypoint.
Eine Sache, die nicht auf der Hand liegt: **nginx baut die SPA beim Image-Build** — eine
Frontend-Änderung braucht `up -d --build nginx`, keinen Backend-Neustart.

#### Spielbereit machen

Frisch aufgesetzt ist keine Karte da, und hochladen darf nur ein Staff-Account.

```bash
# nativ
DJANGO_SUPERUSER_PASSWORD='e2e-local-only' devops/dev.sh manage createsuperuser \
  --noinput --username e2e --email e2e@example.invalid

# Container
DJANGO_SUPERUSER_PASSWORD='e2e-local-only' docker compose -f devops/docker-compose.yaml \
  exec -T -e DJANGO_SUPERUSER_PASSWORD backend \
  ./manage.py createsuperuser --noinput --username e2e --email e2e@example.invalid
```

Dann die Karte — von Hand unter `/app/maps/upload` mit `map_examples/Berlin_Mitte-West.json`, oder per
Skript, das dasselbe über HTTP tut und wiederholbar ist:

```bash
cd frontend && npm run e2e:seed                                  # gegen :5173
cd frontend && E2E_BASE_URL=https://localhost npm run e2e:seed   # gegen den Container
```

### Tests

```bash
devops/dev.sh test                  # Backend-Suite, gegen Postgres, in der Umgebung der CI
cd frontend && npx vitest run       # Frontend-Unit-Tests
cd frontend && npx tsc -b           # Typen (tests/ und e2e/ haben eigene tsconfigs)
cd frontend && npm run e2e:seed && npm run e2e   # Playwright, WebKit
```

Die Backend-Suite läuft immer gegen Postgres, auch wenn die App auf sqlite läuft: sqlite macht
`select_for_update()` zum No-op und vergibt Primärschlüssel anders, und die Simulation wird über
den Rundenschlüssel geseedet. Gelesen wird die **Anzahl** der Tests, nicht `OK` / `FAILED` — eine
Datei, die beim Import wegbricht, nimmt ihre eigenen Tests aus dem Lauf.

### Deployen

**Ausgeliefert wird durch einen Push, nicht von Hand auf der Box.** In `.github/workflows/` liegen
zwei Workflows:

- `tests` — bei jedem Push und PR: `makemigrations --check` und die Backend-Suite gegen Postgres.
- `go live` — bei jedem Push auf **`prod`**: dieselbe Suite, danach per SSH auf die TU-Box, dort
  `git checkout -B prod origin/prod` und `docker compose -f devops/docker-compose.yaml up -d --build`.

`prod` ist ein **Deploy-Zeiger, kein Entwicklungszweig**. Es wird nie darauf committet und nie
hineingemergt, es wird nur vorgespult:

```bash
git push origin main:prod              # den aktuellen Trunk ausliefern
git push -f origin <älterer-sha>:prod  # zurückrollen
```

Was dafür da sein muss: die Repo-Secrets `KEY`, `USER`, `HOST` und `KNOWN_HOSTS` (SSH-Key,
Benutzer, Hostname und Hostkey der Box), und auf der Box ein Checkout unter `/commute`, der dem
`deploy`-Benutzer gehört. Ein `sudo git` dort hinterlässt root-eigene Dateien und bricht das
nächste Deployment.

Zwei Lücken, die man kennen sollte: **die CI baut die SPA nirgends**, ein Typfehler in `frontend/`
ist also kein roter Check, sondern ein fehlgeschlagenes Deployment; und Playwright läuft nicht auf
dem Runner. Die Box terminiert TLS außerdem mit einem selbstsignierten Zertifikat — ein echtes über
Let's Encrypt wäre technisch möglich, ist aber mit der TU-IT abzustimmen.

### Dokumentation

| Datei                                            | Inhalt                                                         |
| ------------------------------------------------ | -------------------------------------------------------------- |
| [`docs/de-ueberblick.md`](docs/de-ueberblick.md) | Überblick: was das Spiel ist und wie es gespielt wird           |
| [`docs/kalibrierung.md`](docs/kalibrierung.md)   | die Zahlen, gegen die gespielt wird, und wie sie gemessen sind  |
| [`docs/testfaelle.md`](docs/testfaelle.md)       | was das Spiel können muss, Fall für Fall, mit Status            |
| [`docs/technical/`](docs/technical/)             | technische Übersicht — in Arbeit                                |

### Lizenz

MIT, siehe [`LICENSE`](LICENSE). © 2025 Sebastian Werblinski und Lukas von Hirschhausen.

---

## English

co2mmute is a browser-based multiplayer traffic game: a class commutes together across a city map,
picks modes and routes each round, and the server simulates what comes of it — CO₂, cost, travel
time. Between rounds the class votes on a change to the map, a bus lane or a new line, and drives
the next round on it. It builds on the technical part of **Sebastian Werblinski's** master's thesis
on agent-based commuting models at Freie Universität Berlin (`master_thesis.pdf`); the code here is
a complete rewrite after the fact, at TU Berlin. The traffic is computed with a link queue model — mesoscopic, the same
family as MATSim.

**Stack:** Django 5.2 + DRF on Daphne (ASGI), Channels, Celery, Postgres 18, Redis; React 19 + Vite
+ TypeScript for the SPA. How the game is played: [`docs/en-overview.md`](docs/en-overview.md).

### Layout

| Path                | What                                                              |
| ------------------- | ----------------------------------------------------------------- |
| `backend/co2mmute/` | Django config — settings, urls, asgi, celery                       |
| `backend/game/`     | sessions, players, rounds, moves, votes, the websocket layer       |
| `backend/sim/`      | the traffic engine as a plain Python package — no Django           |
| `backend/maps/`     | map graph, versioning, the map editor's REST API                   |
| `backend/content/`  | a small CMS for the public pages                                   |
| `backend/template/` | Django templates — landing, lobby, join, legal, auth               |
| `frontend/`         | the SPA — game screen, host pages, map editor                      |
| `devops/`           | `dev.sh`, docker-compose, nginx                                    |
| `map_examples/`     | the map the group plays — Berlin Mitte-West, eight versions        |
| `docs/`             | documentation                                                      |
| `.github/`          | CI and the deployment                                              |

It is a hybrid, not a pure SPA: the landing page, the join flow, the legal pages, login and admin
are server-rendered Django templates; the game and the editor are React.

### Running it locally

Two ways in — `devops/dev.sh` is the working day, `docker compose` is the arrangement that also
gets deployed.

Both need a TLS certificate: the player cookies are `Secure`, and over plain http the browser
throws them away without a word. Self-signed is fine.

```bash
mkdir -p devops/nginx/certs && openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout devops/nginx/certs/selfsigned.key -out devops/nginx/certs/selfsigned.crt \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

#### Native, no Docker

You need Python 3.13, Node 20+, Redis or Valkey, and — for the test suite only — Postgres 18.
Homebrew commands; on Linux use your package manager.

```bash
pyenv virtualenv 3.13.3 commute        # dev.sh looks at $VIRTUAL_ENV, ~/.pyenv/versions/commute, ./.venv
~/.pyenv/versions/commute/bin/pip install -r backend/requirements.txt 'psycopg[binary]'

(cd backend && npm ci)                 # Tailwind for the Django templates
(cd frontend && npm ci)

brew services start valkey             # channel layer, cache and Celery broker, on database index 3

brew install postgresql@18 && brew services start postgresql@18   # for the suite only
psql postgres -c "CREATE ROLE commute LOGIN CREATEDB PASSWORD 'commute'"
createdb -O commute commute

devops/dev.sh up
```

Everything then lives on **https://localhost:5173** — Vite proxies every path Django owns, the way
nginx does in the container. The app itself runs on sqlite.

Further commands: `status`, `logs <service> -f`, `restart <service>`, `manage <args>`, `reset-db`,
`down`. Celery does not autoreload — run `devops/dev.sh restart worker` after touching
`game/tasks.py` or the simulation.

#### Docker compose

```bash
cp devops/env_template.txt devops/.env
```

The minimum for a local run: `POSTGRES_DB/USER/PASSWORD`, a `DJANGO_SECRET_KEY` (nothing starts
without it), `DJANGO_ALLOWED_HOSTS=localhost`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost` and
`DJANGO_BASE_URL=https://localhost`. `DJANGO_BASE_URL` is the only source for the URL in the QR
code — get it wrong and nothing errors, every QR code just points at `localhost`.

```bash
docker compose -f devops/docker-compose.yaml up -d --build
```

Everything on **https://localhost**. Migrations, Tailwind and `collectstatic` are handled by the
entrypoint. One thing that is not obvious: **nginx builds the SPA at image build time** — a
frontend change needs `up -d --build nginx`, not a backend restart.

#### Making it playable

A fresh instance has no map, and uploading one requires a staff account.

```bash
# native
DJANGO_SUPERUSER_PASSWORD='e2e-local-only' devops/dev.sh manage createsuperuser \
  --noinput --username e2e --email e2e@example.invalid

# container
DJANGO_SUPERUSER_PASSWORD='e2e-local-only' docker compose -f devops/docker-compose.yaml \
  exec -T -e DJANGO_SUPERUSER_PASSWORD backend \
  ./manage.py createsuperuser --noinput --username e2e --email e2e@example.invalid
```

Then the map — by hand at `/app/maps/upload` with `map_examples/Berlin_Mitte-West.json`, or with the
script, which does the same thing over HTTP and is idempotent:

```bash
cd frontend && npm run e2e:seed                                  # against :5173
cd frontend && E2E_BASE_URL=https://localhost npm run e2e:seed   # against the container
```

### Tests

```bash
devops/dev.sh test                  # backend suite, on Postgres, in the environment CI has
cd frontend && npx vitest run       # frontend unit tests
cd frontend && npx tsc -b           # types (tests/ and e2e/ have their own tsconfigs)
cd frontend && npm run e2e:seed && npm run e2e   # Playwright, WebKit
```

The backend suite always runs on Postgres even though the app runs on sqlite: sqlite makes
`select_for_update()` a no-op and hands out primary keys differently, and the simulation is seeded
off the round pk. Read the test **count**, not `OK` / `FAILED` — a file that breaks on import
removes its own tests from the run.

### Deploying

**Shipping happens by pushing, not by hand on the box.** There are two workflows in
`.github/workflows/`:

- `tests` — on every push and PR: `makemigrations --check` and the backend suite against Postgres.
- `go live` — on every push to **`prod`**: the same suite, then SSH to the TU box, where it runs
  `git checkout -B prod origin/prod` and `docker compose -f devops/docker-compose.yaml up -d --build`.

`prod` is a **deploy pointer, not a development branch**. Nothing is ever committed to it or merged
into it; it only fast-forwards:

```bash
git push origin main:prod            # ship the current trunk
git push -f origin <older-sha>:prod  # roll back
```

What has to be in place: the repo secrets `KEY`, `USER`, `HOST` and `KNOWN_HOSTS` (SSH key, user,
hostname and host key of the box), and a checkout at `/commute` on the box owned by the `deploy`
user. A `sudo git` there leaves root-owned files and breaks the next deploy.

Two gaps worth knowing: **CI never builds the SPA**, so a type error in `frontend/` is not a red
check but a failed deploy; and Playwright does not run on the runner. The box also terminates TLS
with a self-signed certificate — a real one via Let's Encrypt is technically possible but needs to
be agreed with TU IT first.

### Documentation

| File                                             | What                                                        |
| ------------------------------------------------ | ----------------------------------------------------------- |
| [`docs/en-overview.md`](docs/en-overview.md)     | overview: what the game is and how it is played              |
| [`docs/kalibrierung.md`](docs/kalibrierung.md)   | the numbers the game is played against, and how they were measured (German) |
| [`docs/testfaelle.md`](docs/testfaelle.md)       | what the game has to do, case by case, with status (German)  |
| [`docs/technical/`](docs/technical/)             | technical overview — in progress                             |

### License

MIT, see [`LICENSE`](LICENSE). © 2025 Sebastian Werblinski and Lukas von Hirschhausen.
