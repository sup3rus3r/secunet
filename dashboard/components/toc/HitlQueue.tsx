"use client";
import { useHitlStore } from "@/store/hitl";
import { useMissionStore } from "@/store/mission";
import { AGENT_COLORS } from "@/store/agents";
import { format } from "date-fns";
import { AlertOctagon, CheckCheck, XCircle } from "lucide-react";

const CC_URL = process.env.NEXT_PUBLIC_CC_URL ?? "http://localhost:8001";

async function resolve(hitl_id: string, approved: boolean, token?: string) {
  try {
    await fetch(`${CC_URL}/hitl/${hitl_id}/resolve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ hitl_id, approved }),
    });
  } catch (err) {
    console.error("HITL resolve failed:", err);
  }
}

export default function HitlQueue() {
  const queue     = useHitlStore((s) => s.queue);
  const remove    = useHitlStore((s) => s.remove);
  const setMetric = useMissionStore((s) => s.setMetric);

  async function handle(hitl_id: string, approved: boolean) {
    await resolve(hitl_id, approved);
    remove(hitl_id);
    setMetric("pending_hitl_requests" as never, useHitlStore.getState().queue.length);
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <AlertOctagon className="w-3 h-3 text-[#FFB300]" />
        HITL Queue
        {queue.length > 0 && (
          <span className="ml-auto font-mono text-[10px] text-[#FFB300] font-bold animate-pulse">
            {queue.length} pending
          </span>
        )}
      </div>
      <div className="panel-body space-y-2 min-h-[80px]">
        {queue.length === 0 && (
          <div className="text-[10px] text-muted-foreground font-mono text-center py-4">
            — no pending approvals —
          </div>
        )}
        {queue.map((req) => (
          <div
            key={req.hitl_id}
            className="rounded border border-[#FFB300]/30 bg-[#FFB300]/06 px-2.5 py-2 space-y-1.5"
          >
            <div className="flex items-center gap-1.5">
              <AlertOctagon className="w-3 h-3 text-[#FFB300] shrink-0" />
              <span
                className="text-[10px] font-mono font-bold"
                style={{ color: AGENT_COLORS[req.requesting_agent] ?? "#FFB300" }}
              >
                {req.requesting_agent.replace("-agent", "").toUpperCase()}
              </span>
              <span className="text-[10px] font-mono text-[#FF3B30] font-bold ml-auto">
                {req.risk_level.toUpperCase()}
              </span>
            </div>

            <div className="text-xs font-mono text-foreground leading-snug">
              <span className="text-muted-foreground">ACTION: </span>
              {req.action}
            </div>
            {req.target && (
              <div className="text-[10px] font-mono text-primary">{req.target}</div>
            )}
            {req.proposed_command && (
              <div className="text-[10px] font-mono text-[#FFB300] bg-black/30 rounded px-1.5 py-0.5 truncate">
                $ {req.proposed_command}
              </div>
            )}
            {req.context && (
              <div className="text-[10px] text-muted-foreground font-mono leading-snug line-clamp-2">
                {req.context}
              </div>
            )}

            <div className="flex items-center gap-1.5 pt-0.5">
              <button
                onClick={() => handle(req.hitl_id, true)}
                className="flex items-center gap-1 px-2.5 py-1 bg-[#00C851]/10 border border-[#00C851]/40 text-[#00C851] rounded text-[10px] font-mono font-bold hover:bg-[#00C851]/20 transition-colors"
              >
                <CheckCheck className="w-3 h-3" />
                APPROVE
              </button>
              <button
                onClick={() => handle(req.hitl_id, false)}
                className="flex items-center gap-1 px-2.5 py-1 bg-[#FF3B30]/10 border border-[#FF3B30]/40 text-[#FF3B30] rounded text-[10px] font-mono font-bold hover:bg-[#FF3B30]/20 transition-colors"
              >
                <XCircle className="w-3 h-3" />
                DENY
              </button>
              <span className="ml-auto text-[9px] text-muted-foreground font-mono">
                {format(new Date(req.created_at), "HH:mm:ss")}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
