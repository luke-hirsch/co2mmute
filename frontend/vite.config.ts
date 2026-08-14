import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";

// Everything the SPA needs from Django in dev. Nginx makes these same-origin in
// the container; without the proxy `npm run dev` has no backend at all.
const BACKEND = "http://localhost:8000";
const proxied = (path: string) => ({
  [path]: { target: BACKEND, changeOrigin: true },
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
      "/ws": { target: "ws://localhost:8000", ws: true, changeOrigin: true },
    },
  },
});
