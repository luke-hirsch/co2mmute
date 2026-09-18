#!/usr/bin/env node
/**
 * Give the seeded map something to vote on.
 *
 *   node e2e/seed-versions.mjs
 *
 * `seed.mjs` imports a map with exactly one version, which is enough to play a
 * round and not enough to see a single between-round screen: `vote_options()`
 * offers the versions `compatible_versions` reaches from the active one, so with
 * one version the phase goes stats → next round and the vote, the tie and the
 * map change are all unreachable (Z-04 … Z-11).
 *
 * So this adds two atomic versions off the base — a dedicated bus lane on one
 * street, a 30 km/h limit on another — and then asks the backend to generate the
 * combinations, which is also what wires `compatible_versions` up
 * (`GenerateCombinationsView`). Base then reaches both atomics, which is exactly
 * a two-option ballot, and two options are what a tie needs.
 *
 * Idempotent: it does nothing if the map already has more than its base version.
 *
 * Env: as seed.mjs (E2E_BASE_URL, E2E_USER, E2E_PASSWORD, E2E_MAP_NAME).
 */

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

const BASE = (process.env.E2E_BASE_URL ?? "https://localhost").replace(/\/$/, "");
const USER = process.env.E2E_USER ?? "e2e";
const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-local-only";
const MAP_NAME = process.env.E2E_MAP_NAME ?? "E2E Berlin";

const jar = new Map();

function cookieHeader() {
  return [...jar].map(([k, v]) => `${k}=${v}`).join("; ");
}

function remember(response) {
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
      Referer: BASE + "/",
      ...(init.headers ?? {}),
    },
  });
  remember(response);
  return response;
}

async function postJson(url, body) {
  const response = await request(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": jar.get("csrftoken") ?? "",
    },
    body: JSON.stringify(body),
  });
  if (response.status >= 400) {
    throw new Error(`POST ${url} -> ${response.status}: ${await response.text()}`);
  }
  return response.status === 204 ? null : response.json();
}

async function login() {
  const page = await request(`${BASE}/accounts/login/`);
  const html = await page.text();
  const token = html.match(/name="csrfmiddlewaretoken"\s+value="([^"]+)"/)?.[1];
  if (!token) throw new Error("no csrfmiddlewaretoken in the login form");

  const response = await request(`${BASE}/accounts/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      username: USER,
      password: PASSWORD,
      csrfmiddlewaretoken: token,
    }),
  });
  if (response.status !== 302) {
    throw new Error(`login as "${USER}" failed (HTTP ${response.status})`);
  }
}

/** The diff endpoint answers with the new version; be forgiving about shape. */
function versionId(created) {
  const id = created?.id ?? created?.version?.id ?? created?.version_id;
  if (!id) throw new Error(`no version id in ${JSON.stringify(created)}`);
  return id;
}

async function main() {
  const maps = await (await request(`${BASE}/api/maps/`)).json();
  const list = Array.isArray(maps) ? maps : (maps.results ?? []);
  const map = list.find((m) => m.name?.toLowerCase() === MAP_NAME.toLowerCase());
  if (!map) throw new Error(`no map called "${MAP_NAME}" — run seed.mjs first`);

  const versions = await (
    await request(`${BASE}/api/maps/${map.id}/versions/`)
  ).json();
  if (versions.length > 1) {
    console.log(
      `  "${MAP_NAME}" already has ${versions.length} versions — nothing to do`,
    );
    return;
  }

  const base = versions.find((v) => v.base_version) ?? versions[0];
  if (!base) throw new Error("the map has no version at all");

  await login();
  console.log(`  logged in as ${USER}`);

  // Two street edges to change, picked off the base graph. Any two will do —
  // what matters for the vote is that the versions differ, not what they say.
  const graph = await (
    await request(`${BASE}/api/maps/${map.id}/graph/version/${base.id}/`)
  ).json();
  const streets = (graph.edges ?? []).filter((edge) => edge.street_edge);
  if (streets.length < 2) {
    throw new Error(`the map has ${streets.length} street edges, need 2`);
  }

  const busLane = await postJson(
    `${BASE}/api/maps/${map.id}/versions/create-from-diff/`,
    {
      source_version_id: base.id,
      version_name: "Busspur Hauptstraße",
      poll_text: "Auf der Hauptstraße bekommt der Bus eine eigene Spur.",
      revert_poll_text: "Die Busspur auf der Hauptstraße wird wieder aufgehoben.",
      edge_changes: [{ edge_id: streets[0].id, dedicated_bus_lane: true }],
    },
  );
  console.log("  + Busspur Hauptstraße");

  const tempo30 = await postJson(
    `${BASE}/api/maps/${map.id}/versions/create-from-diff/`,
    {
      source_version_id: base.id,
      version_name: "Tempo 30",
      poll_text: "In der Nebenstraße gilt Tempo 30.",
      revert_poll_text: "Tempo 30 in der Nebenstraße wird wieder aufgehoben.",
      edge_changes: [{ edge_id: streets[1].id, speed_limit: 30 }],
    },
  );
  console.log("  + Tempo 30");

  // The two atomic versions, by id. This is also what links them up: the view
  // sets `compatible_versions` for everything it touches, base included, and
  // without that step the versions exist but nothing can be voted on.
  const combos = await postJson(
    `${BASE}/api/maps/${map.id}/versions/generate-combinations/`,
    { version_ids: [versionId(busLane), versionId(tempo30)] },
  );
  console.log(`  generated ${combos?.created ?? 0} combination version(s)`);

  const after = await (
    await request(`${BASE}/api/maps/${map.id}/versions/`)
  ).json();
  console.log(`  "${MAP_NAME}" now has ${after.length} versions`);
  console.log(
    "\n  Create the game with 'Kartenänderungen' on, or the vote never opens.",
  );
}

main().catch((error) => {
  console.error(`\nseeding versions failed: ${error.message}`);
  process.exit(1);
});
