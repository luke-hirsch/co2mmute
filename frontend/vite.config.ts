import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";

// Everything the SPA needs from Django in dev. Nginx makes these same-origin in
// the container; without the proxy `npm run dev` has no backend at all.
//
// The target is nginx, not Daphne: compose publishes 80/443 only, and the
// backend's 8000 is reachable inside the container network. Pointing at
// localhost:8000 — as this did until the design-system branch — proxies to a
// closed port, which is why `npm run dev` had never once reached a backend.
// `secure: false` accepts the self-signed local cert.
const BACKEND = "https://localhost";
const proxied = (path: string) => ({
  [path]: { target: BACKEND, changeOrigin: true, secure: false },
});

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
    proxy: {
      ...proxied("/api"),
      ...proxied("/media"),
      ...proxied("/static"),
      // Channels lives behind the same origin in prod, so the SPA opens
      // `wss://<host>/ws/...`. Only `ws: true` makes that reachable in dev.
      "/ws": {
        target: "wss://localhost",
        ws: true,
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
