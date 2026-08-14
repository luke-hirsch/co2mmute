const resolveApiBaseUrl = () => {
  if (typeof window === "undefined") {
    return "";
  }

  const { protocol, host } = window.location;
  return `${protocol}//${host}`;
};

export const API_BASE_URL = resolveApiBaseUrl();

