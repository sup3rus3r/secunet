import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ActivityEvent {
  id:        string;
  direction: "inbound" | "outbound";
  actor:     string;
  summary:   string;
  timestamp: string;
}

const MAX_EVENTS = 500;

interface ActivityStore {
  events: ActivityEvent[];
  push:   (event: ActivityEvent) => void;
  clear:  () => void;
}

export const useActivityStore = create<ActivityStore>()(
  persist(
    (set) => ({
      events: [],

      push: (event) =>
        set((s) => {
          if (s.events.some((e) => e.id === event.id)) return s;
          const next = [...s.events, event];
          return { events: next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next };
        }),

      clear: () => set({ events: [] }),
    }),
    {
      name:    "secunet-activity",
      version: 1,
    }
  )
);
