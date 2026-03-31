/**
 * Shadow Authentication Manager
 * Handles persistent session UUIDs for recruiter isolation and abuse prevention.
 */

const SESSION_KEY = "nexus_session_id";
const ACCESS_TIER_KEY = "nexus_access_tier";

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";

  let sessionId = localStorage.getItem(SESSION_KEY);
  
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
  }
  
  return sessionId;
}

export function handleAccessParams() {
  if (typeof window === "undefined") return;

  const params = new URLSearchParams(window.location.search);
  const access = params.get("access");
  
  if (access === "recruiter") {
    localStorage.setItem(ACCESS_TIER_KEY, "recruiter");
    // Optional: Clean up URL to look professional
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

export function getAccessTier(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TIER_KEY);
}

export function getAuthHeaders(): Record<string, string> {
  const sessionId = getOrCreateSessionId();
  const headers: Record<string, string> = {
    "X-Nexus-User-Id": sessionId,
  };
  
  const tier = getAccessTier();
  if (tier) {
    headers["X-Nexus-Access-Tier"] = tier;
  }
  
  return headers;
}
