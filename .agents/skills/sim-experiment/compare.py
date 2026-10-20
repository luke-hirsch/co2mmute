"""Two `calibrate_map` reports side by side: what a change to a number did to a map.

    python3 compare.py <before.txt> <after.txt>

Each file is what `calibrate_map <map> --commuters N` printed, before and after the change, on
the same map file with the same count. Per car share it prints kg per person, euro per person,
the car's trip there and back, the public transport trip and wait, and `nicht da`, as
before -> after, and above them what moved most. A report from before the euro column existed
is read, and its euro stays empty. Standard library only.
"""

import re
import sys

NUMBER = r"[\d.,]+"
ROW = re.compile(
    rf"^\s*(\d+) %\s+({NUMBER}) kg\s+({NUMBER}) kg\s+({NUMBER}) kg\s+({NUMBER}) kg\s+"
    rf"(—|{NUMBER} / {NUMBER} min)\s+(—|{NUMBER} min)\s+(—|{NUMBER} min)"
    rf"(?:\s+({NUMBER}) €)?\s+(\d+)\s*$"
)


def number(text):
    return float(text.replace(".", "").replace(",", "."))


def minutes(text):
    return None if text == "—" else number(text.replace(" min", ""))


def read(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    rows = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        trip = m.group(6)
        there, back = (None, None)
        if trip != "—":
            a, b = trip.replace(" min", "").split(" / ")
            there, back = number(a), number(b)
        rows[int(m.group(1))] = {
            "kg": number(m.group(2)),
            "car_there": there,
            "car_back": back,
            "pt": minutes(m.group(7)),
            "wait": minutes(m.group(8)),
            "eur": number(m.group(9)) if m.group(9) else None,
            "not_home": int(m.group(10)),
        }
    if not rows:
        sys.exit(f"{path}: keine Tabelle von `calibrate_map` gefunden.")
    facts = {}
    m = re.search(r"^Pendler: ([\d.]+)", text, re.M)
    facts["Pendler"] = m.group(1) if m else "?"
    m = re.search(r"^Anteil am Fahrplan: ([\d,]+|nicht messbar)", text, re.M)
    facts["Anteil am Fahrplan"] = m.group(1) if m else "?"
    m = re.search(r"reicht hier, wenn ([\d.,]+) % der Gruppen Auto fahren", text)
    if m:
        facts["Normal reicht bei Auto"] = m.group(1) + " %"
    elif "Nicht spielbar: nicht zu gewinnen" in text:
        facts["Normal reicht bei Auto"] = "nicht zu gewinnen"
    elif "Nicht spielbar: nicht zu verlieren" in text:
        facts["Normal reicht bei Auto"] = "nicht zu verlieren"
    else:
        facts["Normal reicht bei Auto"] = "?"
    return rows, facts


def show(value, digits=2, unit=""):
    if value is None:
        return "—"
    text = f"{value:.{digits}f}".replace(".", ",")
    return text + unit


def pair(before, after, digits=2, unit=""):
    if before is None and after is None:
        return "—"
    return f"{show(before, digits, unit)} → {show(after, digits, unit)}"


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    before, facts_before = read(argv[1])
    after, facts_after = read(argv[2])
    shares = sorted(set(before) & set(after), reverse=True)
    if not shares:
        sys.exit("Keine gemeinsamen Autoanteile in den beiden Berichten.")

    print("Was sich bewegt hat")
    for name in facts_before:
        a, b = facts_before[name], facts_after.get(name, "?")
        print(f"  {name}: {a}" + (f" → {b}" if a != b else " (gleich)"))
    biggest = max(shares, key=lambda s: abs(after[s]["kg"] - before[s]["kg"]))
    delta = after[biggest]["kg"] - before[biggest]["kg"]
    percent = delta / before[biggest]["kg"] * 100 if before[biggest]["kg"] else 0
    print(
        f"  kg pro Person: am meisten bei {biggest} % Auto, "
        f"{show(before[biggest]['kg'])} → {show(after[biggest]['kg'])} "
        f"({'+' if delta >= 0 else ''}{show(percent, 1)} %)"
    )
    home = [s for s in shares if before[s]["not_home"] or after[s]["not_home"]]
    if home:
        print(
            "  NICHT ALLE ANGEKOMMEN bei "
            + ", ".join(f"{s} % Auto" for s in home)
            + ": ein Fehler, kein Ergebnis."
        )
    else:
        print("  Alle angekommen, davor und danach (nicht da 0).")
    print()
    print("Autoanteil | kg pro Person | € pro Person | Auto hin | Auto zurück | Bus & Bahn | Warten | nicht da")
    for s in shares:
        b, a = before[s], after[s]
        print(
            f"{s:>8} % | {pair(b['kg'], a['kg'])} | {pair(b['eur'], a['eur'])} | "
            f"{pair(b['car_there'], a['car_there'], 1, ' min')} | "
            f"{pair(b['car_back'], a['car_back'], 1, ' min')} | "
            f"{pair(b['pt'], a['pt'], 1, ' min')} | "
            f"{pair(b['wait'], a['wait'], 1, ' min')} | "
            f"{b['not_home']} → {a['not_home']}"
        )


if __name__ == "__main__":
    main(sys.argv)
