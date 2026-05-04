import { create } from "zustand";

interface UIState {
  isChatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  toggleChat: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  isChatOpen: false,
  setChatOpen: (open) => set({ isChatOpen: open }),
  toggleChat: () => set((state) => ({ isChatOpen: !state.isChatOpen })),
}));
