import { create } from "zustand";

export interface HitlRequest {
  hitl_id:          string;
  requesting_agent: string;
  action:           string;
  target:           string;
  risk_level:       string;
  context:          string;
  proposed_command?: string;
  created_at:       string;
}

interface HitlStore {
  queue:   HitlRequest[];
  push:    (r: HitlRequest) => void;
  remove:  (hitl_id: string) => void;
  clear:   () => void;
}

export const useHitlStore = create<HitlStore>((set) => ({
  queue: [],

  push: (r) =>
    set((s) => ({
      queue: s.queue.some((x) => x.hitl_id === r.hitl_id)
        ? s.queue
        : [...s.queue, r],
    })),

  remove: (hitl_id) =>
    set((s) => ({ queue: s.queue.filter((r) => r.hitl_id !== hitl_id) })),

  clear: () => set({ queue: [] }),
}));
