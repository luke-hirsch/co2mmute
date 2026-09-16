import type { Config } from "tailwindcss";

/**
 * Legacy theme, kept alive only until the last pre-rewrite component is gone.
 * The shadcn tokens live as CSS variables in src/main.css instead — see the
 * comment there. Delete this file, the `@config` line and the `.dark body` rule
 * together at the end of phase 2.
 *
 * `muted` and `accent` were renamed to `mutedtext` / `brandaccent` because
 * shadcn owns those two names now and a colliding key would silently repaint
 * ~240 call sites.
 */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#e3f2fd",
          100: "#bbdefb",
          200: "#90caf9",
          300: "#64b5f6",
          400: "#42a5f5",
          500: "#1e88e5",
          600: "#1565c0",
          700: "#0d47a1",
          800: "#092f6b",
          900: "#041c3d",
        },
        brandaccent: "#ffb300",
        body: "#f3f4f6",
        surface: "#ffffff",
        elevated: "#f9fafb",
        subtle: "#e5e7eb",
        strong: "#d1d5db",
        main: "#111827",
        mutedtext: "#6b7280",
        soft: "#9ca3af",
        darkbody: "#0b1120",
        darksurface: "#111827",
        darkelevated: "#1f2933",
        darksubtle: "#1f2937",
        darkstrong: "#374151",
        darktext: "#f9fafb",
        darkmutedtext: "#9ca3af",
        darksofttext: "#6b7280",
        success: {
          100: "#d1fae5",
          500: "#10b981",
          700: "#047857",
        },
        warning: {
          100: "#fef3c7",
          500: "#f59e0b",
          700: "#b45309",
        },
        danger: {
          100: "#fee2e2",
          500: "#ef4444",
          700: "#b91c1c",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
