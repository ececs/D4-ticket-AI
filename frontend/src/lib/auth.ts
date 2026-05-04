/**
 * Auth utilities for client-side token management.
 */

/**
 * Extracts the access token from cookies.
 * Works only in client-side code (browser).
 */
export function getAuthToken(): string | null {
  if (typeof document === "undefined") return null;
  
  const tokenMatch = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
  if (!tokenMatch) return null;
  
  try {
    return decodeURIComponent(tokenMatch[1]);
  } catch (err) {
    console.error("Failed to decode auth token", err);
    return null;
  }
}
