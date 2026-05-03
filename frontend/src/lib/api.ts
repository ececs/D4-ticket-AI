/**
 * API client — axios instance configured for the FastAPI backend.
 *
 * Cross-domain auth strategy:
 *  - The JWT is stored as a readable (non-httpOnly) cookie on the Vercel domain.
 *  - The Next.js middleware reads it server-side for route protection.
 *  - The request interceptor below reads it client-side and attaches it as an
 *    Authorization: Bearer header so the Railway backend (different domain) can
 *    authenticate each request. Browsers don't share cookies across domains, so
 *    withCredentials alone is not sufficient here.
 */

import axios from "axios";
import { getAuthToken } from "./auth";

const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_URL}/api/v1`,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: read the JWT from the frontend-domain cookie and attach
// it as Authorization: Bearer on every outbound API request to the backend.
api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    // Direct assignment is safer for cross-version compatibility
    if (config.headers) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor: on 401, redirect to /api/auth/clear which deletes the
// session cookie server-side (JS cannot delete httpOnly cookies) before sending
// the user to /login. This breaks the middleware redirect loop caused by stale
// httpOnly cookies.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      if (!window.location.pathname.startsWith("/api/auth")) {
        window.location.href = "/api/auth/clear";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
