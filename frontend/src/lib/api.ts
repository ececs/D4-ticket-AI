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
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
    if (match) {
      config.headers.Authorization = `Bearer ${decodeURIComponent(match[1])}`;
    }
  }
  return config;
});

// Response interceptor: redirect to login on 401.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
