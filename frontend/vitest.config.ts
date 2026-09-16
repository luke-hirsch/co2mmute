import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

// Deliberately separate from vite.config.ts: the TanStack router plugin
// regenerates src/routeTree.gen.ts as a side effect of loading the config, and a
// test run has no business rewriting a source file.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    // Tests mirror src/ in their own tree rather than sitting next to it.
    include: ["tests/**/*.test.ts"],
    // Node, not jsdom. The target is the pure lib/ layer; anything that needs a
    // browser global gets it from vi.stubGlobal in the test that needs it.
    environment: "node",
  },
});
