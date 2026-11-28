declare global {
  interface Window {
    __RUNTIME_CONFIG__?: {
      API_BASE_URL?: string;
    };
  }
}

export function getApiBaseUrl(): string {
  const runtimeUrl = window.__RUNTIME_CONFIG__?.API_BASE_URL?.trim();
  if (runtimeUrl) {
    return runtimeUrl.replace(/\/+$/, "");
  }
  const envUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (envUrl) {
    return envUrl.replace(/\/+$/, "");
  }
  return "/api";
}
