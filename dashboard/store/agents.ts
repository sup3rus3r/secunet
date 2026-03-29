import { create } from "zustand";

export type AgentStatus = "online" | "idle" | "running" | "error" | "offline";

export interface AgentInfo {
  agent_id:       string;
  status:         AgentStatus;
  last_heartbeat: string | null;
  current_task:   string | null;
  color:          string;
}

// Canonical agent roster with assigned colors
export const AGENT_COLORS: Record<string, string> = {
  "recon-agent":     "#00D4FF",
  "exploit-agent":   "#FF3B30",
  "detect-agent":    "#FFB300",
  "remediate-agent": "#00C851",
  "monitor-agent":   "#9B59B6",
  "commander":       "#FF6B35",
};

const DEFAULT_AGENTS: AgentInfo[] = Object.entries(AGENT_COLORS).map(([id, color]) => ({
  agent_id:       id,
  status:         "offline",
  last_heartbeat: null,
  current_task:   null,
  color,
}));

interface AgentsStore {
  agents: Record<string, AgentInfo>;
  upsert: (agent: Partial<AgentInfo> & { agent_id: string }) => void;
  setStatus: (agent_id: string, status: AgentStatus) => void;
  heartbeat: (agent_id: string) => void;
}

export const useAgentsStore = create<AgentsStore>((set) => ({
  agents: Object.fromEntries(DEFAULT_AGENTS.map((a) => [a.agent_id, a])),

  upsert: (incoming) =>
    set((s) => {
      const existing = s.agents[incoming.agent_id] ?? {
        agent_id:       incoming.agent_id,
        status:         "offline",
        last_heartbeat: null,
        current_task:   null,
        color:          AGENT_COLORS[incoming.agent_id] ?? "#5A6A7E",
      };
      return {
        agents: {
          ...s.agents,
          [incoming.agent_id]: { ...existing, ...incoming },
        },
      };
    }),

  setStatus: (agent_id, status) =>
    set((s) => {
      const existing = s.agents[agent_id];
      if (!existing) return s;
      return { agents: { ...s.agents, [agent_id]: { ...existing, status } } };
    }),

  heartbeat: (agent_id) =>
    set((s) => {
      const existing = s.agents[agent_id];
      if (!existing) return s;
      return {
        agents: {
          ...s.agents,
          [agent_id]: {
            ...existing,
            status: "online",
            last_heartbeat: new Date().toISOString(),
          },
        },
      };
    }),
}));
