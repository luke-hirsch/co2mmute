/**
 * The smallest map file worth showing, for the upload screen's format toggle.
 *
 * Data, not copy — which is why it is here and not in `de.ts`: the keys are the
 * importer's field names and stay English, and the German in it is two place
 * names. `maps/tests/test_portability.py` imports a file of this shape, and
 * the Django page carried the same one; it moved across with S19.
 */
export const EXAMPLE_MAP_FILE = {
  scale: 1000,
  map: { name: "Beispiel", x_dim: 10, y_dim: 10, max_player: 6 },
  nodes: [
    {
      id: "A",
      x: 0.0,
      y: 0.0,
      name: "Bahnhof Mitte",
      types: ["intersection", "station"],
    },
    { id: "B", x: 5.0, y: 3.5, name: "Wohnort 1", types: ["home"] },
  ],
  edges: [
    {
      start_node: "A",
      end_node: "B",
      name: "Hauptstraße",
      type: "street",
      speed_limit: 50,
      lanes: 2,
      dedicated_bus_lane: false,
    },
  ],
  bus_lines: [{ name: "M1", edges: [0], interval: 5, capacity: 85 }],
  train_lines: [],
};
