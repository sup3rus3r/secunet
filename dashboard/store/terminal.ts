import { create } from "zustand";

export interface TerminalLine {
  id:        string;
  agent_id:  string;
  command?:  string;
  output:    string;
  exit_code?: number;
  timestamp: string;
}

const MAX_LINES = 200;

interface TerminalStore {
  lines:  TerminalLine[];
  push:   (line: TerminalLine) => void;
  clear:  () => void;
}

export const useTerminalStore = create<TerminalStore>((set) => ({
  lines: [],

  push: (line) =>
    set((s) => {
      const next = [...s.lines, line];
      return { lines: next.length > MAX_LINES ? next.slice(-MAX_LINES) : next };
    }),

  clear: () => set({ lines: [] }),
}));
