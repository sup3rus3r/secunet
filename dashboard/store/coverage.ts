import { create } from "zustand";

export type TechniqueState = "attempted" | "detected" | "remediated";

interface CoverageStore {
  techniques: Record<string, TechniqueState>;
  mark:  (id: string, state: TechniqueState) => void;
  reset: () => void;
}

// Higher priority state always wins — never downgrade
const PRIORITY: Record<TechniqueState, number> = {
  attempted:  1,
  detected:   2,
  remediated: 3,
};

export const useCoverageStore = create<CoverageStore>((set) => ({
  techniques: {},

  mark: (id, state) =>
    set((s) => {
      const current = s.techniques[id];
      if (current && PRIORITY[current] >= PRIORITY[state]) return s;
      return { techniques: { ...s.techniques, [id]: state } };
    }),

  reset: () => set({ techniques: {} }),
}));
