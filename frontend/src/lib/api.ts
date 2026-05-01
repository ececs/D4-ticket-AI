/**
 * API client — axios instance configured for the FastAPI backend.
 *
 * Key configuration:
 *  - baseURL: points to the FastAPI backend (configurable via env var)
 *  - withCredentials: true — sends the HttpOnly access_token cookie automatically
 *    with every request. This is how browser sessions work without localStorage.
 *  - Response interceptor: on 401, redirects to login page.
 *
 * Usage:
 *   import api from "@/lib/api";
 *   const { data } = await api.get<TicketListResponse>("/tickets");
 */

import axios from "axios";

const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_URL}/api/v1`,
  withCredentials: true, // Send cookies (access_token) with every request
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor: handle authentication errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      // Redirect to login if the server says we're not authenticated
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
