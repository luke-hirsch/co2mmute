import { defineConfig, devices } from "@playwright/test";

/**
 * E2E against the real stack, in WebKit.
 *
 * **It points at nginx, never at `npm run dev`.** Two reasons, both of which
 * make a dev-server run useless rather than merely different:
 *
 * - `CSRF_TRUSTED_ORIGINS` lists 80/443/8080 and not 5173, so every host
 *   mutation answers `403 CSRF Failed: Origin checking failed`. Nothing a host
 *   does can be tested there.
 * - Both player cookies are set `Secure`, and a browser on plain http drops
 *   them silently — the join succeeds and everything after it is a 403.
 *
 * So the stack has to be up before these run:
 *
 *     docker compose -f devops/docker-compose.yaml up -d --build
 *     node e2e/seed.mjs
 *     npm run e2e
 *
 * Nginx rebuilds the SPA on every `up --build`, so a frontend change needs a
 * compose rebuild before a spec sees it. That makes e2e a good deal slower than
 * vitest, which is why this suite stays small: flows that genuinely need a
 * browser — the funnel, the socket, a whole round — and nothing that the pure
 * `lib/` layer can answer.
 *
 * WebKit only. Safari and every iOS browser are the engines that matter here,
 * and they are the ones with the bug the SPA already works around (a fetch sent
 * in the same task as a new WebSocket never settles).
 */

const BASE_URL = process.env.E2E_BASE_URL ?? "https://localhost";

export default defineConfig({
  testDir: "./e2e",
  // The seed scripts live in the same directory and are not tests.
  testMatch: "**/*.spec.ts",

  // A round runs a Celery task and a simulation; the default 30 s is not enough
  // to wait one out on a cold worker.
  timeout: 120_000,
  expect: { timeout: 15_000 },

  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,

  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],

  use: {
    baseURL: BASE_URL,
    // The box terminates TLS with a self-signed certificate, locally and live.
    // This is a browser pointed at a host named right here — it must never be
    // lifted into application code.
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
