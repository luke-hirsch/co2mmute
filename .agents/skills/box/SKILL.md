---
name: box
description: The runbook for the VM co2mmute runs on — deploying, rolling back, reading what the box is doing, the certificate, the mail, the disk. Use when someone asks to deploy or roll back, when the site is down or slow, when a certificate or the mail sender is in question, or when the box needs looking at. Read-only: it says what to type and reads what the box says; everything that changes the box is the human's.
---

# box

The box is one VM that runs the whole stack from `devops/docker-compose.yaml`. This skill is a
runbook, not a record: **what the box does today, read it from the box**, never from this file or any
note. Every fact below that only the box knows comes with the command that finds it.

**Read-only.** Look, and say what to type. Never change the box yourself: no `git` on it, no
`docker compose up/down/restart`, no edit of `devops/.env`, no certificate command. Those are the
human's, run by them; you give the line and say why.

## who is who

- A **sudo user** (a person's own login) reaches the box over `ssh`. The deploy runs as a user
  called **`deploy`**, who owns `/commute`, the checkout the stack is built from.
- Work in `/commute` as `deploy`: `sudo -iu deploy`. **Never `sudo git`**: it leaves root-owned
  files in the checkout and the next deploy fails.
- Docker needs `sudo docker …` for the sudo user (or runs as `deploy`).
- The host, the user and the host key of the box are the repository's secrets for the deploy
  (`KEY`, `USER`, `HOST`, `KNOWN_HOSTS`, GitHub settings). Ask the human for the address; do not
  look for it in the repo.

## deploying

`prod` is a pointer, never a branch to work on. A push to it is the deploy
(`.github/workflows/workflow-prod.yml`, "go live"): the three jobs of `test.yml` again (backend suite,
frontend, e2e on the compose stack), and only if all are green an `ssh` into the box that runs
`git checkout -B prod origin/prod`, `docker compose -f devops/docker-compose.yaml up -d --build`, and
prunes images. Live about ten to thirteen minutes after the push.

```bash
git fetch origin
git log --oneline origin/prod..origin/main   # what a push would ship; empty = nothing to deploy
git push origin main:prod                     # the human pushes
gh run list --workflow "go live" --limit 3    # watch it; gh run watch <id> follows one
gh run view <id> --log-failed                 # a red run: what failed
```

A red run **does not deploy**: the box keeps what it had. A red e2e on CI that is green locally is
read from the run's artifact (`gh run download <id>`, the trace), not rerun blindly.

After a green run, check the site, not the run: open the landing page and `/app/`, and read what is
live from the box (below) — `origin/prod` says what was pushed, the box says what it runs.

**Rolling back** is the same push with an older commit:

```bash
git push -f origin <older-sha>:prod
```

It runs the whole pipeline again, so it takes the same ten minutes. Migrations are not rolled back:
a rollback over a migration that was applied needs the human's decision before the push.

## reading the box

All of it read-only, in `/commute` (`sudo -iu deploy`) or with `sudo docker`:

```bash
git -C /commute log --oneline -3                                 # the commit it was built from
git -C /commute status --short                                   # anything not from a deploy (should be empty)
docker compose -f devops/docker-compose.yaml ps                  # six services: postgres, redis, backend, celery-worker, celery-beat, nginx
docker compose -f devops/docker-compose.yaml logs --since 30m backend     # also nginx, celery-worker, celery-beat
docker compose -f devops/docker-compose.yaml logs --since 30m nginx | tail
df -h /                                                          # the disk
docker system df                                                 # what images, cache and volumes take
free -h; uptime                                                  # memory and load
```

Reading the output:

- All six `Up`, `postgres` and `redis` `healthy`. A service restarting in a loop: read its logs.
- The backend's entrypoint migrates and collects static files at start, so a deploy that fails
  to come up usually says why in `logs backend`.
- A running round is the worker's. If rounds do not finish, read `celery-worker`; the simulation
  never runs in a web request.
- Player names never reach a log (a test holds that). If one shows in a log, that is a finding.

The jobs that run on their own are `celery-beat`'s (`CELERY_BEAT_SCHEDULE` in
`backend/co2mmute/settings.py`): finished games are anonymised hourly, idle games end at 02:30,
expired sessions go at 03:00. If player names stay readable in a game that has been over for longer
than a day, read `celery-beat`'s log first.

## the disk

Builds fill it: every deploy leaves images and build cache, and the deploy prunes images and
keeps 2 GB of build cache. When `df -h /` says it is filling, `docker system df` says who takes it.
Pruning is the human's; the line to give them:

```bash
sudo docker image prune -f
sudo docker builder prune -f --keep-storage 2GB
```

**Not** `docker volume prune` and not `docker compose down -v`: `postgres-data` is the database.

## no backups, by design

The database is disposable: games are not kept past their debrief, and the one thing that took hours
to make, the maps, lives as files (`map_examples/` in the repo, and the JSON export of every map from
the map page or `GET api/maps/<pk>/export/`). Before anything that could touch the database or a map
nobody has exported, say so and let the human export first. There is nothing to restore from.

## the certificate

`devops/nginx/nginx.conf` answers Let's Encrypt's challenge on port 80 from `./nginx/acme` and serves
the pair `./nginx/certs/selfsigned.crt` / `.key` (the names are old; what sits there may be a real
certificate). Which one is there, and how it renews, only the box knows. Look it up:

```bash
openssl x509 -in /commute/devops/nginx/certs/selfsigned.crt -noout -issuer -subject -dates
sudo ls -la /etc/letsencrypt/live/ /etc/letsencrypt/renewal-hooks/deploy/ 2>/dev/null
sudo certbot certificates 2>/dev/null
systemctl list-timers 2>/dev/null | grep -i certbot; sudo crontab -l 2>/dev/null | grep -i certbot
```

- The **issuer** says self-signed or Let's Encrypt; **notAfter** says when it runs out. Under
  three weeks left with a Let's Encrypt issuer means a renewal failed: say so, with the dates.
- The **renewal hook** (a script under certbot's `renewal-hooks`, or the `deploy-hook` named in the
  certificate's file under `/etc/letsencrypt/renewal/`) is what copies the renewed pair into
  `devops/nginx/certs/`. Read its path and its content from the box; do not assume either. A copied
  pair is only served after nginx re-reads it: whether the hook reloads nginx is in the hook.
- `DJANGO_HSTS_SECONDS` in `devops/.env` makes browsers refuse plain http for that long. It stays 0
  until a real certificate works; a short value first, a long one once a renewal has been seen to
  work. A wrong certificate under a long HSTS locks every browser out for that long.

## the mail

Mail is sent for one thing: "Passwort vergessen?". It is configured in `devops/.env`
(`DJANGO_EMAIL_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_SSL`/`_TLS`, `_FROM`;
`devops/env_template.txt` explains each). With `DJANGO_EMAIL_HOST` empty no mail is sent and the page
still answers the same, so "no reset mail arrives" starts with whether the host is set at all.

Read what the box uses, without printing the password:

```bash
sudo grep -E '^DJANGO_EMAIL_(HOST|PORT|USER|SSL|TLS|FROM)=' /commute/devops/.env
docker compose -f devops/docker-compose.yaml logs --since 24h backend | grep -i -E 'mail|smtp'
```

**Open, for the human, not a step:** the sender today is one person's address. The group needs
a sender of its own (an address and an SMTP account that belong to the group, not to whoever built
the site) before that person's account goes away, and that decision is theirs. Until it is made, say
so whenever mail comes up.

## what to say

German, with du, to the human who asked; the verdict first ("Die Box läuft, der Stand ist `abc1234`,
das Zertifikat gilt bis …"), then what you read, then, if anything is wrong, the line they should type
and why. Never paste a secret you read (`devops/.env` holds the database password and the secret
key; grep the names you need, never `cat` it).

## don't

- Don't change anything on the box, and don't ask a peer or a tool to. Give the human the line.
- Don't trust `origin/prod`, a note or this file for what is live: read the box.
- Don't put a host, an address, a username or a host key into a file in the repo.
- Don't `sudo git` in `/commute`, and don't commit to or merge into `prod`.
