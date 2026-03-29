import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  finding_id:  string;
  agent_id:    string;
  host:        string;
  title:       string;
  severity:    Severity;
  cve?:        string;
  technique?:  string;
  description: string;
  timestamp:   string;
  remediated:  boolean;
}

const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 0, high: 1, medium: 2, low: 3, info: 4,
};

interface FindingsStore {
  findings:        Finding[];
  push:            (f: Finding) => void;
  markRemediated:  (finding_id: string) => void;
  clear:           () => void;
}

export const useFindingsStore = create<FindingsStore>()(
  persist(
    (set) => ({
      findings: [],

      push: (f) =>
        set((s) => {
          const deduped = s.findings.filter((x) => x.finding_id !== f.finding_id);
          const next = [...deduped, f].sort(
            (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
          );
          return { findings: next };
        }),

      markRemediated: (finding_id) =>
        set((s) => ({
          findings: s.findings.map((f) =>
            f.finding_id === finding_id ? { ...f, remediated: true } : f
          ),
        })),

      clear: () => set({ findings: [] }),
    }),
    {
      name:    "secunet-findings",
      version: 1,
    }
  )
);
