// NEXT_PUBLIC_* vars are inlined at build time. If missing, detect context at runtime.
// On an HTTPS deployment, falling back to http://localhost:8000 causes Mixed Content errors.
// We guard against this by using the current window origin when baked-in value is missing.
function resolveApiBaseUrl(): string {
  const baked = process.env.NEXT_PUBLIC_API_URL;
  if (baked) return baked;

  // Runtime fallback: use the page's own origin in a browser context (same host, correct protocol)
  if (typeof window !== "undefined" && window.location.protocol === "https:") {
    return window.location.origin;
  }

  return "http://localhost:8000";
}

export const API_BASE_URL = resolveApiBaseUrl();

