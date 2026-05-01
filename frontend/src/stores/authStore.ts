/**
 * Authentication state store — Zustand.
 *
 * Zustand is a lightweight state management library. Unlike Redux, it requires
 * no boilerplate (no actions, reducers, or dispatch). The store is a single
 * object with state and actions merged together.
 *
 * This store holds:
 *  - user: the currently authenticated user, or null if not logged in.
 *  - isLoading: true while the /auth/me request is in flight (prevents flash).
 *
 * The store is populated on app startup by calling fetchUser() from the
 * root layout. Subsequent components can read `user` without making API calls.
 */

import { create } from "zustand";
import { User } from "@/types";
import api from "@/lib/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  fetchUser: () => Promise<void>;
  clearUser: () => void;
}

const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,

  fetchUser: async () => {
    try {
      const { data } = await api.get<User>("/auth/me");
      set({ user: data, isLoading: false });
    } catch {
      // 401 or network error — user is not authenticated
      set({ user: null, isLoading: false });
    }
  },

  clearUser: () => set({ user: null }),
}));

export default useAuthStore;
