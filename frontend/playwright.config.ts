import { defineConfig, devices } from "@playwright/test";

/**
 * E2E against the real stack, in WebKit.
 *
 * **It needs a complete origin, not a bare SPA.** This is a hybrid: the landing
 * page, the lobby, the join flow, the legal pages and the admin are all
 * server-rendered Django, and a session cookie set by one has to reach the
 * other. Two arrangements provide that, and either works here:
 *
 *     devops/dev.sh up                     the native stack, on :5173 (default)
 *     E2E_BASE_URL=https://localhost ...   the container, behind nginx
 *
 * The native one is the default because it is the fast loop — nginx rebuilds
 * the whole Vite bundle on every `up --build`, so a frontend change costs a
 * compose rebuild before a spec can see it. Run the container one before
 * anything that has to hold in the production arrangement.
 *
 * Both are https with a self-signed certificate, hence `ignoreHTTPSErrors`:
 * player cookies are `Secure`, and a browser on plain http drops them without a
 * word, so the join succeeds and every call after it is a 403.
 *
 * Seed either one first — `npm run e2e:seed` (it talks HTTP and honours
 * `E2E_BASE_URL` too).
 *
 * WebKit only. Safari and every iOS browser are the engines that matter here,
 * and they are the ones with the bug the SPA already works around (a fetch sent
 * in the same task as a new WebSocket never settles).
 */

const BASE_URL = process.env.E2E_BASE_URL ?? "https://localhost:5173";

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
  // One retry in CI, none here. A run there builds a fresh stack and cannot be
  // looked at afterwards, and one flake is known (round 2 opening without
  // "„…“ ist angenommen", a socket reconnecting across `vote.result`) — a spec
  // that only passes on its second try is still reported as flaky, so a retry
  // does not hide it. Locally a failure should stay a failure.
  retries: process.env.CI ? 1 : 0,

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
