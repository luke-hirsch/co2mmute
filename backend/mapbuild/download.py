"""Everything a build reads from the internet, fetched once and kept in the cache.

The cache is `mapbuild/cache/` (or `CO2MMUTE_MAP_CACHE`): one directory per area for what is cut to
it, and one each for the sources that cover a country or the globe.

- OpenStreetMap, over Overpass (`OVERPASS_API_URL`, else the public instance; it often answers
  504 for a while — the download waits and tries again), by the area's box. © OpenStreetMap
  contributors, ODbL.
- Nominatim, for a place name.
- Zensus 2022, people per 100 m cell, Germany only. © Statistisches Bundesamt (Destatis), Zensus
  2022.
- GHSL, non-residential building volume per ~100 m cell, worldwide (European Commission, JRC,
  GHS-BUILT-V R2023A, CC BY 4.0).
- DELFI's timetables for Germany as GTFS, from gtfs.de (CC BY 4.0), the next 30 days: local
  transit (`nv`) and regional rail with the S-Bahn (`rv`).
"""

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

UA = {"User-Agent": "co2mmute-map-builder (research game, FU Berlin)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
ZENSUS = "https://www.destatis.de/static/DE/zensus/gitterdaten/Zensus2022_Bevoelkerungszahl.zip"
ZENSUS_CSV = "Zensus2022_Bevoelkerungszahl_100m-Gitter.csv"
GHSL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_V_GLOBE_R2023A/"
    "GHS_BUILT_V_NRES_E2020_GLOBE_R2023A_4326_3ss/V1-0/tiles/"
)
GHSL_TILE = "GHS_BUILT_V_NRES_E2020_GLOBE_R2023A_4326_3ss_V1_0_R{}_C{}"
GTFS = {
    "nv": "https://download.gtfs.de/germany/nv_free/latest.zip",
    "rv": "https://download.gtfs.de/germany/rv_free/latest.zip",
}

# OSM, by the area's box (BB): the street classes, the land the speed rule and the places read,
# and every line of every mode with its stop nodes and its ways
QUERIES = {
    "roads": 'way BB["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link)$"]; out body geom;',
    "local": 'way BB["highway"~"^(tertiary|tertiary_link|unclassified|residential)$"]; out body geom;',
    "residential": '(way BB["landuse"="residential"]; relation BB["landuse"="residential"]["type"="multipolygon"];); out geom;',
    "workland": '(way BB["landuse"~"^(commercial|retail|industrial)$"]; relation BB["landuse"~"^(commercial|retail|industrial)$"]["type"="multipolygon"];); out geom;',
    "water": '(way BB["natural"="water"]; relation BB["natural"="water"]["type"="multipolygon"]; way BB["waterway"="riverbank"]; way BB["waterway"~"^(river|canal)$"];); out geom;',
    "green": '(way BB["leisure"="park"]; relation BB["leisure"="park"]["type"="multipolygon"]; way BB["landuse"~"^(forest|grass)$"]; relation BB["landuse"~"^(forest|grass)$"]["type"="multipolygon"]; way BB["natural"="wood"]; relation BB["natural"="wood"]["type"="multipolygon"];); out geom;',
    "places": 'node BB["place"~"^(city|town|borough|suburb|quarter|neighbourhood|village|hamlet)$"]; out body;',
    "pt_routes": 'relation BB["type"="route"]["route"~"^(bus|trolleybus|tram|subway|light_rail|train)$"]; out body;',
    "pt_nodes": 'relation BB["type"="route"]["route"~"^(bus|trolleybus|tram|subway|light_rail|train)$"]; node(r); out body;',
    "pt_ways": 'relation BB["type"="route"]["route"~"^(bus|trolleybus|tram|subway|light_rail|train)$"]; way(r); out body geom;',
}
TRIES = 4
WAIT_S = 30
SPLIT = (
    3  # a box too big for Overpass is fetched in quarters, down to this many halvings
)


class Missing(Exception):
    """a source has nothing for this area, or could not be reached."""


class TooBig(Missing):
    """Overpass ran out of time or memory on the query (504, a timeout, an error remark)."""


def cache_root(root=None):
    d = Path(
        root or os.environ.get("CO2MMUTE_MAP_CACHE") or Path(__file__).parent / "cache"
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def say(msg):
    print(msg, file=sys.stderr, flush=True)


def _request(url, data=None, timeout=700):
    req = urllib.request.Request(url, data=data, headers=UA)
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise Missing(f"{url}: 404") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        say(f"  {url[:70]} — Versuch {i + 1}: {last}")
        if i + 1 < TRIES:
            time.sleep(WAIT_S)
    too_big = isinstance(last, TimeoutError) or (
        isinstance(last, urllib.error.HTTPError) and last.code == 504
    )
    raise (TooBig if too_big else Missing)(f"nicht erreichbar: {url} ({last})")


def nominatim(name):
    q = urllib.parse.urlencode(
        {"q": name, "format": "jsonv2", "limit": 10, "extratags": 1}
    )
    return json.loads(_request(f"{NOMINATIM}?{q}", timeout=60))


def overpass_url():
    return (
        os.environ.get("OVERPASS_API_URL") or "https://overpass-api.de/api/interpreter"
    )


def overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    out = json.loads(_request(overpass_url(), data=data))
    # a query that runs out of time or memory still answers 200, with what it had and a remark
    if "error" in out.get("remark", "").lower():
        raise TooBig(f"Overpass: {out['remark'][:200]}")
    return out


def _osm(query, bbox, depth=0):
    """the elements of a query in a box; a box Overpass gives up on, in quarters, merged by id."""
    s, w, n, e = bbox
    q = "[out:json][timeout:600];" + query.replace(" BB", f"({s},{w},{n},{e})")
    try:
        return overpass(q)["elements"]
    except TooBig:
        if depth >= SPLIT:
            raise
    say(f"  Overpass gibt auf, in Vierteln: {bbox}")
    ms, mw = (s + n) / 2, (w + e) / 2
    seen, out = set(), []
    for part in ((s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)):
        for x in _osm(query, part, depth + 1):
            if (x["type"], x["id"]) not in seen:
                seen.add((x["type"], x["id"]))
                out.append(x)
    return out


def osm(area, name):
    """the area's OSM data for one query, from the cache or Overpass: [elements]."""
    path = area.cache / f"{name}.json"
    if not path.exists():
        t = time.time()
        say(f"OSM: {name} …")
        els = _osm(QUERIES[name], area.fetch_bbox)
        _write(path, json.dumps({"elements": els}).encode())
        say(f"OSM: {name}, {len(els)} Elemente, {time.time() - t:.0f} s")
    return json.loads(path.read_text())["elements"]


def _write(path, body):
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(path)


def _file(url, path):
    """a big file, streamed to disk once."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    say(f"Download: {url}")
    tmp = path.with_suffix(path.suffix + ".part")
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=700
            ) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(path)
            return path
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise Missing(f"{url}: 404") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        say(f"  Versuch {i + 1}: {last}")
        if i + 1 < TRIES:
            time.sleep(WAIT_S)
    raise Missing(f"nicht erreichbar: {url} ({last})")


def zensus(root=None):
    """the Zensus 2022 grid as a zip (the 100 m cells are `ZENSUS_CSV` in it)."""
    return _file(
        ZENSUS, cache_root(root) / "zensus" / "Zensus2022_Bevoelkerungszahl.zip"
    )


def ghsl(row, col, root=None):
    """one GHSL tile (10° square) as a GeoTIFF; None where the tile has nothing (open sea)."""
    name = GHSL_TILE.format(row, col)
    tif = cache_root(root) / "ghsl" / f"{name}.tif"
    if not tif.exists():
        try:
            z = _file(GHSL + name + ".zip", tif.with_suffix(".zip"))
        except Missing:
            return None
        with zipfile.ZipFile(z) as zf, zf.open(f"{name}.tif") as src, open(
            tif, "wb"
        ) as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
    return tif


def gtfs(feed, root=None):
    return _file(GTFS[feed], cache_root(root) / "gtfs" / f"{feed}.zip")
