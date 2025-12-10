import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  safelist: [
    { pattern: /^(p|m|mx|my|mt|mr|mb|ml|px|py|pt|pr|pb|pl)-[0-9]+$/ },
    { pattern: /^rounded(-[a-z]+)?$/ },
    { pattern: /^(min|max)-(w|h)-(full|screen|svh)$/ },
    { pattern: /^flex(-col)?$/ },
    { pattern: /^(items|justify)-(center|between|start|end)$/ },
    { pattern: /^overflow(-y)?-(auto|hidden)$/ },
    { pattern: /^text-(left|center|start)$/ },
    { pattern: /^opacity-(0|100)$/ },
    { pattern: /^z-(0|50)$/ },
    { pattern: /^translate-x-(full)$/ },
    { pattern: /^-translate-x-full$/ },
    { pattern: /^w-(full|screen|auto|2\/3)$/ },
    {
      pattern:
        /^(bg|text|border)-(body|surface|elevated|subtle|strong|main|muted|soft|primary-(50|100|200|300|400|500|600|700|800|900)|success-(100|500|700)|warning-(100|500|700)|danger-(100|500|700))$/,
    },
    {
      pattern:
        /^dark:(bg|text|border)-(darkbody|darksurface|darkelevated|darksubtle|darkstrong|darktext|darkmutedtext|primary-600|primary-500|danger-500)$/,
    },
    {
      pattern:
        /^(hover:|dark:hover:)(bg-(elevated|primary-500|primary-600|darkelevated)|text-(primary-600|darktext)|opacity-80)$/,
    },
    {
      pattern:
        /^(focus(-visible)?:(outline(-offset)?(-2)?|ring-0|border-primary-500|outline-primary-600))$/,
    },
    { pattern: /^shadow(-.*)?$/ },
  ],
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
        accent: "#ffb300",
        body: "#f3f4f6",
        surface: "#ffffff",
        elevated: "#f9fafb",
        subtle: "#e5e7eb",
        strong: "#d1d5db",
        main: "#111827",
        muted: "#6b7280",
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
