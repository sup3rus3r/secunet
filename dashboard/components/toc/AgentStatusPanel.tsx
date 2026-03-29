"use client";
import { useAgentsStore, type AgentStatus } from "@/store/agents";
import { useMissionStore } from "@/store/mission";
import { formatDistanceToNow } from "date-fns";
import { Users, Server, Database, Eye, Wrench, Monitor } from "lucide-react";

const AGENT_ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  "recon-agent":     Eye,
  "exploit-agent":   Server,
  "detect-agent":    Eye,
  "remediate-agent": Wrench,
  "monitor-agent":   Monitor,
  "commander":       Database,
};

const AGENT_LABELS: Record<string, string> = {
  "recon-agent":     "RECON",
  "exploit-agent":   "EXPLOIT",
  "detect-agent":    "DETECT",
  "remediate-agent": "REMEDIATE",
  "monitor-agent":   "MONITOR",
  "commander":       "COMMANDER",
};

const STATUS_DOT: Record<AgentStatus, string> = {
  online:  "bg-[#00C851]",
  running: "bg-[#00D4FF] agent-pulse",
  idle:    "bg-[#FFB300]",
  error:   "bg-[#FF3B30] agent-pulse",
  offline: "bg-muted-foreground",
};

export default function AgentStatusPanel() {
  const agentsMap = useAgentsStore((s) => s.agents);
  const agents = Object.values(agentsMap);
  const { hosts_discovered, open_findings, critical_findings } = useMissionStore();

  const AGENT_ORDER = ["commander", "recon-agent", "exploit-agent", "detect-agent", "remediate-agent", "monitor-agent"];
  const sorted = AGENT_ORDER
    .map((id) => agents.find((a) => a.agent_id === id))
    .filter(Boolean) as typeof agents;

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <Users className="w-3 h-3" />
        Agent Fleet
      </div>
      <div className="panel-body space-y-1 py-2">
        {sorted.map((agent) => {
          const Icon = AGENT_ICONS[agent.agent_id] ?? Server;
          const label = AGENT_LABELS[agent.agent_id] ?? agent.agent_id.toUpperCase();
          const dotClass = STATUS_DOT[agent.status] ?? STATUS_DOT.offline;

          return (
            <div
              key={agent.agent_id}
              className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-secondary/40 transition-colors"
            >
              <Icon className="w-3.5 h-3.5 shrink-0" style={{ color: agent.color }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className="text-xs font-mono font-semibold"
                    style={{ color: agent.color }}
                  >
                    {label}
                  </span>
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotClass}`} />
                </div>
                <div className="text-[10px] text-muted-foreground font-mono truncate">
                  {agent.current_task
                    ? agent.current_task
                    : agent.status === "offline"
                    ? "offline"
                    : agent.last_heartbeat
                    ? formatDistanceToNow(new Date(agent.last_heartbeat), { addSuffix: true })
                    : agent.status}
                </div>
              </div>
            </div>
          );
        })}

        {/* Mission metrics summary */}
        <div className="mt-3 pt-3 border-t border-border space-y-1">
          <MetricRow label="Hosts" value={hosts_discovered} color="#00D4FF" />
          <MetricRow label="Open Findings" value={open_findings} color="#FFB300" />
          <MetricRow label="Critical" value={critical_findings} color="#FF3B30" />
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center justify-between px-2 py-0.5">
      <span className="text-[10px] text-muted-foreground font-mono uppercase">{label}</span>
      <span className="text-xs font-mono font-bold" style={{ color }}>{value}</span>
    </div>
  );
}
