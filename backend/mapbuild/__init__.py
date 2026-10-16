"""The map builder: an area's OpenStreetMap data → a game map file.

Plain Python, standard library only, no Django — like `sim/`. `manage.py build_map` is the door:
it names the area, downloads what the area needs on first use (`download.py`, cached under
`mapbuild/cache/` or `CO2MMUTE_MAP_CACHE`), runs `build.build` and writes the file. The file then
goes through `manage.py check_map`, `manage.py calibrate_map --out` and the import.

The stages, in the order they run:

1. `area`      a place name → its administrative boundary, or a box
2. `roads`     OSM's ways of the street classes, clipped; speed and lanes from the tags
3. `streets`   twin carriageways folded into one street, junctions merged, dead ends cut
4. `people`    homes from the Zensus grid, workplaces from GHSL, equal people / jobs each
5. `connect`   each place pins its own node; a place still far off gets a street one class down
6. `mapfile`   the graph as a game map file
7. `lines` → `timetable` → `rail`, `buses` → `transit`: the lines that cover the places, their
   stops and edges, their intervals, on the map; `footpaths` then lays a path to the stop for a place
   the kept streets walk far from one and the side streets don't
8. `backdrop`  the map's own background, an SVG drawn from the land, water, local streets and rails
   the build holds, in the plane of the nodes

Every stage prints what it did into the build report; what a rule could not fix is a line there,
never a question.
"""
