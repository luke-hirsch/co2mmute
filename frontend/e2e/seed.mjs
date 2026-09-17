#!/usr/bin/env node
/**
 * Bring a fresh co2mmute instance to the point where a game can be played:
 * a staff account, and one map with home and workplace nodes.
 *
 *   node e2e/seed.mjs
 *
 * Talks HTTP only. There is no seed management command and there does not need
 * to be: `/map/upload/` already imports a whole graph — nodes, node types,
 * edges, bus and train lines — in a single POST, and that is the same path a
 * human uses, so the seed exercises the real importer rather than a second
 * copy of it that could drift.
 *
 * Idempotent: if the map is already there it does nothing and exits 0. Run it
 * as often as you like.
 *
 * The one thing it cannot do over HTTP is create the staff account — signing up
 * gives you a normal user and uploading a map needs `is_staff`. If login fails
 * it prints the one command that fixes it.
 *
 * Env:
 *   E2E_BASE_URL   default https://localhost
 *   E2E_USER       default e2e
 *   E2E_PASSWORD   default e2e-local-only
 *   E2E_MAP        default map_examples/Berlin_Mitte-West.json
 *   E2E_MAP_NAME   default "E2E Berlin"
 *
 * Pass --recreate to delete an existing map of that name first, which is how
 * you reset test data after changing the fixture.
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

// The local stack terminates TLS with a self-signed cert. This script only ever
// talks to a host you named yourself, so accepting it is fine here — it must
// never be lifted into application code.
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

const BASE = (process.env.E2E_BASE_URL ?? "https://localhost").replace(/\/$/, "");
const USER = process.env.E2E_USER ?? "e2e";
const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-local-only";
const MAP_NAME = process.env.E2E_MAP_NAME ?? "E2E Berlin";
const REPO = path.resolve(fileURLToPath(new URL("../..", import.meta.url)));
const MAP_FILE = path.resolve(
  REPO,
  process.env.E2E_MAP ?? "map_examples/Berlin_Mitte-West.json",
);
const RECREATE = process.argv.includes("--recreate");

/**
 * Six homes and six workplaces, so six players each get a home nobody else has.
 * The other examples have one or two of each, and agent assignment then falls
 * back to reusing them — which works, but makes a test that is meant to look
 * like a classroom look like nothing at all.
 */
const WANT_SEATS = 6;

/** Minimal cookie jar — fetch has none, and Django needs sessionid + csrftoken. */
const jar = new Map();

function cookieHeader() {
  return [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
}

function remember(response) {
  // getSetCookie keeps multiple Set-Cookie headers apart; a joined header would
  // be unsplittable because cookie values may contain commas.
  for (const line of response.headers.getSetCookie?.() ?? []) {
    const [pair] = line.split(";");
    const eq = pair.indexOf("=");
    if (eq === -1) continue;
    const name = pair.slice(0, eq).trim();
    const value = pair.slice(eq + 1).trim();
    if (value === '""' || value === "") jar.delete(name);
    else jar.set(name, value);
  }
}

async function request(url, init = {}) {
  const response = await fetch(url, {
    ...init,
    redirect: "manual",
    headers: {
      Cookie: cookieHeader(),
      // Django refuses a CSRF-protected POST over HTTPS without a matching
      // Referer, whatever the token says.
      Referer: BASE + "/",
      ...(init.headers ?? {}),
    },
  });
  remember(response);
  return response;
}

function tokenFrom(html) {
  const match = html.match(/name="csrfmiddlewaretoken"\s+value="([^"]+)"/);
  if (!match) throw new Error("no csrfmiddlewaretoken in the form");
  return match[1];
}

async function login() {
  const page = await request(`${BASE}/accounts/login/`);
  if (!page.ok) throw new Error(`GET /accounts/login/ -> ${page.status}`);
  const token = tokenFrom(await page.text());

  const body = new URLSearchParams({
    username: USER,
    password: PASSWORD,
    csrfmiddlewaretoken: token,
  });
  const response = await request(`${BASE}/accounts/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  // Django answers a good login with a redirect and a bad one with 200 + errors.
  if (response.status !== 302) {
    throw new Error(
      `login as "${USER}" failed (HTTP ${response.status}).\n\n` +
        `  Create the account first:\n\n` +
        `    DJANGO_SUPERUSER_PASSWORD='${PASSWORD}' docker compose -f devops/docker-compose.yaml \\\n` +
        `      exec -T -e DJANGO_SUPERUSER_PASSWORD backend \\\n` +
        `      ./manage.py createsuperuser --noinput --username ${USER} --email ${USER}@example.invalid\n`,
    );
  }
}

async function findMap(name) {
  // GET on the maps API is open, so this works before logging in too.
  const response = await request(`${BASE}/api/maps/`);
  if (!response.ok) throw new Error(`GET /api/maps/ -> ${response.status}`);
  const maps = await response.json();
  const list = Array.isArray(maps) ? maps : (maps.results ?? []);
  return list.find((m) => m.name?.toLowerCase() === name.toLowerCase()) ?? null;
}

async function uploadMap() {
  const page = await request(`${BASE}/map/upload/`);
  if (page.status === 302) {
    throw new Error("/map/upload/ redirected — the account is not staff");
  }
  const token = tokenFrom(await page.text());

  const json = await readFile(MAP_FILE);
  const form = new FormData();
  form.set("csrfmiddlewaretoken", token);
  form.set("map_name", MAP_NAME);
  form.set("description", "Angelegt von e2e/seed.mjs. Loeschbar.");
  form.set("max_players", "6");
  form.set(
    "json_file",
    new Blob([json], { type: "application/json" }),
    path.basename(MAP_FILE),
  );

  const response = await request(`${BASE}/map/upload/`, {
    method: "POST",
    body: form,
  });
  // The view redirects to the new map on success and re-renders with messages
  // on failure, so a 200 here means it refused.
  if (response.status !== 302) {
    const html = await response.text();
    const errors = [...html.matchAll(/•\s*([^<]+)/g)].map((m) => m[1].trim());
    throw new Error(
      `map upload refused (HTTP ${response.status})` +
        (errors.length ? `:\n  ${errors.slice(0, 8).join("\n  ")}` : ""),
    );
  }
}

async function main() {
  console.log(`seeding ${BASE}`);

  const existing = await findMap(MAP_NAME);
  if (existing && !RECREATE) {
    console.log(`  map "${MAP_NAME}" is already there (id ${existing.id}) — nothing to do`);
    return;
  }

  await login();
  console.log(`  logged in as ${USER}`);

  if (existing) {
    const gone = await request(`${BASE}/api/maps/${existing.id}/`, {
      method: "DELETE",
      headers: { "X-CSRFToken": jar.get("csrftoken") ?? "" },
    });
    if (gone.status !== 204 && gone.status !== 200) {
      throw new Error(`could not delete map ${existing.id} (HTTP ${gone.status})`);
    }
    console.log(`  deleted the old "${MAP_NAME}" (id ${existing.id})`);
  }

  await uploadMap();
  const created = await findMap(MAP_NAME);
  if (!created) throw new Error("upload reported success but the map is not listed");

  const graph = await request(`${BASE}/api/maps/${created.id}/graph/baseversion/`);
  const { nodes = [], edges = [], bus_lines = [], train_lines = [] } = await graph.json();
  const homes = nodes.filter((n) => n.node_type?.some?.((t) => t.name === "home"));
  const work = nodes.filter((n) => n.node_type?.some?.((t) => t.name === "workplace"));

  console.log(
    `  imported "${MAP_NAME}" (id ${created.id}): ${nodes.length} nodes, ` +
      `${edges.length} edges, ${bus_lines.length} bus + ${train_lines.length} train lines`,
  );
  console.log(`  ${homes.length} home nodes, ${work.length} workplace nodes`);

  if (homes.length === 0 || work.length === 0) {
    throw new Error(
      "the map has no home or no workplace nodes — players would get no agents",
    );
  }
  if (homes.length < WANT_SEATS) {
    console.warn(
      `  note: only ${homes.length} home nodes, so beyond ${homes.length} players ` +
        `they start sharing one`,
    );
  }
}

main().catch((error) => {
  console.error(`\nseed failed: ${error.message}`);
  process.exit(1);
});
