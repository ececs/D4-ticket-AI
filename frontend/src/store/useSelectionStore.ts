import { create } from 'zustand';

interface SelectionState {
  selectedTicketIds: string[];
  toggleTicket: (id: string) => void;
  setSelection: (ids: string[]) => void;
  clearSelection: () => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selectedTicketIds: [],
  
  toggleTicket: (id) => set((state) => ({
    selectedTicketIds: state.selectedTicketIds.includes(id)
      ? state.selectedTicketIds.filter((tId) => tId !== id)
      : [...state.selectedTicketIds, id]
  })),

  setSelection: (ids) => set({ selectedTicketIds: ids }),
  
  clearSelection: () => set({ selectedTicketIds: [] }),
}));
