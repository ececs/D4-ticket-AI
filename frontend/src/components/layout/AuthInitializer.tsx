/**
 * AuthInitializer — invisible client component that hydrates the auth store.
 *
 * Calls GET /auth/me on mount and stores the result in Zustand so any client
 * component can access the current user without making additional API calls.
 *
 * Mounted once at the layout level — runs exactly once per page load.
 */

"use client";

import { useEffect } from "react";
import useAuthStore from "@/stores/authStore";

export function AuthInitializer() {
  const fetchUser = useAuthStore((s) => s.fetchUser);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return null;
}
