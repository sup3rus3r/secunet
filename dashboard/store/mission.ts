import { create } from "zustand";

export interface MissionState {
  mission_id:          string;
  mission_name:        string;
  current_phase:       string;
  target_scope:        string;
  hosts_discovered:    number;
  open_findings:       number;
  critical_findings:   number;
  coverage_score:      number; // 0–100
  pending_hitl_requests: number;
  ws_connected:        boolean;
}

interface MissionStore extends MissionState {
  setConnected:  (v: boolean) => void;
  applySnapshot: (snapshot: Partial<MissionState>) => void;
  setMetric:     (field: keyof MissionState, value: unknown) => void;
}

export const useMissionStore = create<MissionStore>((set) => ({
  mission_id:            "",
  mission_name:          "No Active Mission",
  current_phase:         "IDLE",
  target_scope:          "",
  hosts_discovered:      0,
  open_findings:         0,
  critical_findings:     0,
  coverage_score:        0,
  pending_hitl_requests: 0,
  ws_connected:          false,

  setConnected: (v) => set({ ws_connected: v }),

  applySnapshot: (snapshot) => set((s) => ({ ...s, ...snapshot })),

  setMetric: (field, value) => set((s) => ({ ...s, [field]: value })),
}));
