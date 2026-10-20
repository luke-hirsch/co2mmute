"""A report on the state of an instance's maps, and the write-back of a new measurement.

    python3 checkup.py report [<dir>]
    python3 checkup.py write <map> <calibrated.json>

`report` exports every map into <dir> (default: ./checkup-<date>), runs `check_map` on each
export and prints one block per map: whether the check is clean, when the count was measured,
when the graph last changed, whether the measurement is out of date, the count, the share of
the timetable and whether the table is there. It changes nothing on the instance.

`write` takes the file `calibrate_map --out` wrote and puts the count, the share, the table and
the time the measurement started on the map's row, and refuses a file of another map. The time
is the run's start on purpose: an edit made while the run was going then still counts as made
after it.

The instance and a staff account come from CO2MMUTE_URL (default http://127.0.0.1:8000, Django
itself), CO2MMUTE_USER and CO2MMUTE_PASSWORD. `check_map` runs through CO2MMUTE_MANAGE
(default `devops/dev.sh manage`, the command that runs `manage.py` in a checkout).
Standard library only.
"""

import http.cookiejar
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("CO2MMUTE_URL", "http://127.0.0.1:8000").rstrip("/")
MANAGE = os.environ.get("CO2MMUTE_MANAGE", "devops/dev.sh manage")


class Api:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self._login()

    def _csrf(self):
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        return ""

    def _login(self):
        user = os.environ.get("CO2MMUTE_USER")
        password = os.environ.get("CO2MMUTE_PASSWORD")
        if not user or not password:
            sys.exit("CO2MMUTE_USER und CO2MMUTE_PASSWORD fehlen.")
        self.opener.open(BASE + "/accounts/login/")
        body = urllib.parse.urlencode(
            {
                "username": user,
                "password": password,
                "csrfmiddlewaretoken": self._csrf(),
            }
        ).encode()
        request = urllib.request.Request(
            BASE + "/accounts/login/",
            data=body,
            headers={"Referer": BASE + "/accounts/login/"},
        )
        self.opener.open(request)
        if not any(cookie.name == "sessionid" for cookie in self.jar):
            sys.exit("Anmeldung abgelehnt: Name, Passwort oder CO2MMUTE_URL prüfen.")

    def call(self, method, path, payload=None, raw=False):
        data = None
        headers = {
            "X-CSRFToken": self._csrf(),
            "Referer": BASE + "/",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            BASE + path, data=data, headers=headers, method=method
        )
        try:
            with self.opener.open(request) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            sys.exit(f"{method} {path}: {error.code} {error.read().decode()[:500]}")
        if raw:
            return body
        return json.loads(body) if body else None


def rows(answer):
    return answer["results"] if isinstance(answer, dict) else answer


def day(moment):
    return moment[:10] if moment else "nie"


def run_check_map(path):
    """(clean, the lines `check_map` printed)"""
    done = subprocess.run(
        shlex.split(MANAGE) + ["check_map", path], capture_output=True, text=True
    )
    lines = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    return done.returncode == 0 and any("in Ordnung" in l for l in lines), lines


def state(row):
    if not row["calibrated_at"]:
        return "nie gemessen"
    if row["edited_since_calibration"]:
        return (
            f"veraltet: bearbeitet am {day(row['graph_edited_at'])}, "
            f"gemessen am {day(row['calibrated_at'])}"
        )
    return f"aktuell, gemessen am {day(row['calibrated_at'])}"


def cmd_report(api, out_dir=None):
    out_dir = os.path.abspath(out_dir or f"checkup-{time.strftime('%Y-%m-%d')}")
    os.makedirs(out_dir, exist_ok=True)
    for row in rows(api.call("GET", "/api/maps/")):
        slug = re.sub(r"[^A-Za-z0-9]+", "-", row["name"]).strip("-")
        path = os.path.join(out_dir, f"{row['id']}-{slug}.json")
        with open(path, "wb") as fh:
            fh.write(api.call("GET", f"/api/maps/{row['id']}/export/", raw=True))
        with open(path, encoding="utf-8") as fh:
            graph = json.load(fh)
        clean, lines = run_check_map(path)
        print(f"{row['id']}  {row['name']}")
        print(f"    check_map:   {'in Ordnung' if clean else 'nicht in Ordnung'}")
        if not clean:
            for line in lines[:6]:
                print(f"                 {line.strip()}")
        print(f"    Messung:     {state(row)}")
        print(
            f"    Zahlen:      {row['district_commuters']} Pendler, Anteil am Fahrplan "
            f"{row.get('timetable_factor')}, Tabelle "
            f"{'da' if row['co2_table'] else 'fehlt'}"
        )
        print(
            f"    Größe:       {len(graph.get('nodes', []))} Knoten, "
            f"{len(graph.get('edges', []))} Kanten (Messdauer: Minuten bis Stunden)"
        )
        print(f"    Export:      {path}")


def cmd_write(api, map_id, path):
    with open(path, encoding="utf-8") as fh:
        meta = json.load(fh).get("map", {})
    row = api.call("GET", f"/api/maps/{map_id}/")
    if meta.get("name") != row["name"]:
        sys.exit(
            f"Die Datei ist die Karte „{meta.get('name')}“, Karte {map_id} heißt "
            f"„{row['name']}“. Nichts geschrieben."
        )
    if not meta.get("calibrated_at") or not meta.get("co2_table"):
        sys.exit("In der Datei fehlt calibrated_at oder die Tabelle: kein `--out` der Messung.")
    payload = {
        "district_commuters": meta["district_commuters"],
        "co2_table": meta["co2_table"],
        "calibrated_at": meta["calibrated_at"],
    }
    if meta.get("timetable_factor") is not None:
        payload["timetable_factor"] = meta["timetable_factor"]
    after = api.call("PATCH", f"/api/maps/{map_id}/", payload)
    print(
        f"{row['name']}: {row['district_commuters']} → {after['district_commuters']} Pendler, "
        f"Anteil {row.get('timetable_factor')} → {after.get('timetable_factor')}, "
        f"gemessen am {day(after['calibrated_at'])}; {state(after)}."
    )


COMMANDS = {"report": cmd_report, "write": cmd_write}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[argv[1]](Api(), *argv[2:])


if __name__ == "__main__":
    main(sys.argv)
