const fallbackBaseUrl = "/api";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? fallbackBaseUrl;

export const COLOR_MODE_STORAGE_KEY = "colorMode";
