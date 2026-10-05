#!/usr/bin/env node
/**
 * Every commute on a map, found by the game's own router.
 *
 *   node scripts/routes.mjs graph.json > routes.json     (from frontend/)
 *
 * `graph.json` is what `MapVersionGraphView` serves for one version — the
 * graph the round screen routes on. The answer is every home to every
 * workplace and back, car, public transport, bike and walk, each leg in the
 * shape `POST .../move/` takes, or `{ "error": … }` where the router finds no
 * way. Car and public transport ask for what the round screen offers first.
 *
 * There is no second router in Python on purpose: one router, so two cannot
 * disagree about which way a class goes. This script runs the TypeScript one
 * under Node through Vite's own module loader, so it is the code the browser
 * runs, `@/` imports and all. `manage.py calibrate_map` calls it; nothing else
 * has to.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const source = process.argv[2];
if (!source) {
  console.error("usage: node scripts/routes.mjs graph.json > routes.json");
  process.exit(2);
}
const graph = JSON.parse(readFileSync(source, "utf-8"));

// No config file: the app's plugins (router codegen, Tailwind, React) have
// nothing to do with routing, and the code generator writes into src/.
const vite = await createServer({
  configFile: false,
  root: frontend,
  logLevel: "silent",
  appType: "custom",
  server: { middlewareMode: true, hmr: false, watch: null },
  optimizeDeps: { noDiscovery: true, include: [] },
  resolve: { alias: { "@": path.join(frontend, "src") } },
});

try {
  const { routeCommutes } = await vite.ssrLoadModule("/src/lib/map/trip-search.ts");
  const { DEFAULT_CAR_OPTIMIZATION, DEFAULT_PT_OPTIMIZATION } = await vite.ssrLoadModule(
    "/src/lib/game/round-draft.ts",
  );
  const choice = {
    carOptimization: DEFAULT_CAR_OPTIMIZATION,
    ptOptimization: DEFAULT_PT_OPTIMIZATION,
  };

  // The routers narrate every search on the console, which is the browser's
  // devtools in the game and would be this script's output here.
  const log = console.log;
  console.log = () => {};
  console.warn = () => {};
  const commutes = await routeCommutes(graph, choice);
  console.log = log;

  process.stdout.write(
    JSON.stringify({
      map_id: graph.map_id,
      version_id: graph.version_id,
      choice,
      commutes,
    }),
  );
} finally {
  await vite.close();
}
