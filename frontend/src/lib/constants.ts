const rawUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// Force absolute URL to prevent relative path 404s on Render
export const API_BASE_URL = rawUrl.startsWith("http")
  ? rawUrl 
  : (rawUrl.includes(".") || rawUrl.includes("localhost")) 
    ? `https://${rawUrl}` 
    : rawUrl;
