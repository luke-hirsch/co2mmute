"""The whole build: an area → a game map file and its report."""

from . import connect, mapfile, people, roads, streets, timetable, transit

AUTO = object()

# Whose data a map is drawn from, as each licence asks it to be said. The map file carries the
# ones the build used, and the viewers print them small in a corner.
OSM = {
    "text": "© OpenStreetMap contributors",
    "url": "https://www.openstreetmap.org/copyright",
}
ZENSUS = {"text": "© Statistisches Bundesamt (Destatis), Zensus 2022"}
GHSL = {"text": "© European Union, CC BY 4.0 (EC JRC, GHS-BUILT-V R2023A)"}
DELFI = {"text": "© DELFI e.V., CC BY 4.0, via gtfs.de"}


def build(area, name=None, builtup=AUTO, places=None, extract=AUTO):
    """(map file data, report). The report is [(heading, [lines])], the heads-up lines last.

    builtup: the built-up test for unsigned speed limits (`roads.fit_builtup` unless given; None
    takes each class's default). places: the homes and workplaces {"home <name>" | "work <name>":
    (lat, lon)} instead of the rule's. extract: the area's timetable (`timetable.of_area` unless
    given; None is no timetable)."""
    area.use()
    report = []
    credits = [OSM]
    if area.notes:
        report.append(("Gebiet", list(area.notes)))
    say = []
    if builtup is AUTO:
        builtup, margin, ok50, ok100 = roads.fit_builtup(area)
        if builtup is None:
            say.append(
                "keine beschilderten 50er und 100er Straßen: ohne Schild gilt die Vorgabe der Straßenklasse"
            )
        else:
            say.append(
                f"innerorts = bebautes Land im Umkreis von {margin} m ({ok50:.0%} der 50er-Schilder, {ok100:.0%} der 100er stimmen)"
            )
    pos, links, st = streets.folded(area, builtup)
    mesh = connect.mesh_m(pos, links)
    say.append(f"mittlere Straße {mesh:.0f} m")
    report.append(("Straßen", say))
    if places is None:
        places, say = people.places_of(area, mesh, area.inside())
        credits += [ZENSUS, GHSL]
        report.append(("Wohn- und Arbeitsorte", say))
    cpos, clinks, say = connect.connected(area, pos, links, st, places)
    report.append(("Anbindung", say))
    data, say = mapfile.to_map(cpos, clinks, name or area.name, places)
    report.append(("Karte", say))
    if extract is AUTO:
        extract = timetable.of_area(area)
    data, say, heads_up = transit.add(
        area, data, mapfile.street_shapes(cpos, clinks), extract
    )
    if extract is not None:
        credits.append(DELFI)
    data["map"]["credits"] = [dict(c) for c in credits]
    report.append(("Bus und Bahn", say))
    report.append(("Achtung", heads_up))
    return data, report
