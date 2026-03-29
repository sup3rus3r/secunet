"use client";
import { useEffect, useRef } from "react";
import { useActivityStore, type ActivityEvent } from "@/store/activity";
import { AGENT_COLORS } from "@/store/agents";
import { format } from "date-fns";
import { Activity, ArrowDownLeft, ArrowUpRight } from "lucide-react";

function getActorColor(actor: string): string {
  return AGENT_COLORS[actor] ?? "#5A6A7E";
}

function getActorLabel(actor: string): string {
  const labels: Record<string, string> = {
    "recon-agent":     "RECON",
    "exploit-agent":   "EXPLOIT",
    "detect-agent":    "DETECT",
    "remediate-agent": "REMEDIATE",
    "monitor-agent":   "MONITOR",
    "commander":       "COMMANDER",
    "engineer":        "ENGINEER",
  };
  return labels[actor] ?? actor.toUpperCase();
}

function ActivityRow({ event }: { event: ActivityEvent }) {
  const color    = getActorColor(event.actor);
  const label    = getActorLabel(event.actor);
  const ts       = format(new Date(event.timestamp), "HH:mm:ss");
  const inbound  = event.direction === "inbound";

  return (
    <div className="flex items-start gap-1.5 py-0.5 border-b border-border/20 last:border-0">
      {/* Direction arrow */}
      <span className="mt-0.5 shrink-0" title={inbound ? "received" : "dispatched"}>
        {inbound
          ? <ArrowDownLeft className="w-3 h-3 text-muted-foreground/60" />
          : <ArrowUpRight  className="w-3 h-3" style={{ color }} />
        }
      </span>

      {/* Timestamp */}
      <span className="text-[10px] font-mono text-muted-foreground shrink-0 mt-0.5">
        {ts}
      </span>

      {/* Actor badge */}
      <span
        className="text-[10px] font-mono font-bold shrink-0 mt-0.5"
        style={{ color }}
      >
        {label}
      </span>

      {/* Summary */}
      <span className="text-[10px] font-mono text-foreground/80 leading-relaxed break-all">
        {event.summary}
      </span>
    </div>
  );
}

export default function ActivityFeed() {
  const events    = useActivityStore((s) => s.events);
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoScroll = useRef(true);
  const listRef    = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [events]);

  function onScroll() {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    autoScroll.current = scrollHeight - scrollTop - clientHeight < 60;
  }

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header">
        <Activity className="w-3 h-3" />
        Activity
        <span className="ml-auto text-[10px]">{events.length}</span>
      </div>

      <div
        ref={listRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto px-2 py-1"
      >
        {events.length === 0 && (
          <div className="text-[10px] text-muted-foreground font-mono text-center py-6">
            — no activity yet —
          </div>
        )}
        {events.map((e) => (
          <ActivityRow key={e.id} event={e} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
