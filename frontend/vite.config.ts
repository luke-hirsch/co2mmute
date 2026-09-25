import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";

// Everything the SPA needs from Django in dev. Nginx makes these same-origin in
// the container; without the proxy `npm run dev` has no backend at all.
//
// Two backends are possible and the default is the container one:
//
//   https://localhost          nginx, the production-shaped arrangement. Compose
//                              publishes 80/443 only, and the backend's 8000 is
//                              reachable inside the container network — pointing
//                              at localhost:8000 (as this did until the
//                              design-system branch) proxies to a closed port,
//                              which is why `npm run dev` had never once reached
//                              a backend.
//   http://127.0.0.1:8000      a natively-run Django. `devops/dev.sh` sets
//                              BACKEND_ORIGIN to this.
//
// `secure: false` accepts the self-signed local cert in the first case and is
// harmless in the second.
const BACKEND = process.env.BACKEND_ORIGIN ?? "https://localhost";
const SOCKET_BACKEND = BACKEND.replace(/^http/, "ws");
const proxied = (path: string) => ({
  [path]: { target: BACKEND, changeOrigin: true, secure: false },
});

/**
 * The paths Django owns, which nginx serves in the container and on the box.
 *
 * Proxying them makes the dev server a complete origin rather than an SPA with
 * nothing around it: the landing page, the lobby, the join flow, the legal
 * pages and the admin all answer on :5173 beside `/app/`. That matters beyond
 * convenience — it is a hybrid, the funnel is server-rendered, and a session
 * cookie set by `/accounts/login/` has to reach the SPA.
 *
 * `/app/` is deliberately absent: Vite serves that itself, and its own dev
 * assets live under it because of `base`.
 */
const DJANGO_PATHS = [
  "/api",
  "/static",
  "/media",
  "/admin",
  "/accounts",
  "/legal",
  "/content",
  "/game",
  "/join",
  "/map",
];

/**
 * The dev server has to speak TLS, or the player flow cannot work at all.
 *
 * Both player cookies are set with `secure=SESSION_COOKIE_SECURE or
 * request.is_secure()` (`co2mmute/utils.py`), and nginx sends
 * `X-Forwarded-Proto https` on every proxied request — so the cookies always
 * come back marked `Secure`, and a browser on `http://localhost:5173` throws
 * them away without a word. The join then succeeds, and every call after it is
 * a 403: no game cookie. Found while checking F1 in WebKit on 2026-09-18.
 *
 * Reusing nginx's own self-signed cert keeps this to zero extra setup — the
 * same file, the same `CN=localhost`, and the same warning to click through
 * that `https://localhost` already shows. If it is missing, dev falls back to
 * http: the map editor and the styleguide work fine there, only the cookie
 * flows do not, and a hard failure at startup would be the worse trade.
 */
const CERT_DIR = fileURLToPath(new URL("../devops/nginx/certs", import.meta.url));
const certFiles = {
  key: `${CERT_DIR}/selfsigned.key`,
  cert: `${CERT_DIR}/selfsigned.crt`,
};
const https =
  existsSync(certFiles.key) && existsSync(certFiles.cert)
    ? {
        key: readFileSync(certFiles.key),
        cert: readFileSync(certFiles.cert),
      }
    : undefined;

// https://vite.dev/config/
export default defineConfig({
  base: "/app/",
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    https,
    proxy: {
      ...Object.assign({}, ...DJANGO_PATHS.map(proxied)),
      // The landing page, and only it: an exact match, because a plain "/"
      // prefix rule would swallow `/app/` and Vite's own dev assets with it.
      "^/$": { target: BACKEND, changeOrigin: true, secure: false },
      // Channels lives behind the same origin in prod, so the SPA opens
      // `wss://<host>/ws/...`. Only `ws: true` makes that reachable in dev.
      "/ws": {
        target: SOCKET_BACKEND,
        ws: true,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
