"use client";
import { useEffect, useRef } from "react";
import { useTerminalStore } from "@/store/terminal";
import { AGENT_COLORS } from "@/store/agents";
import { format } from "date-fns";
import { Terminal, Trash2 } from "lucide-react";

export default function TerminalFeed() {
  const lines   = useTerminalStore((s) => s.lines);
  const clear   = useTerminalStore((s) => s.clear);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <Terminal className="w-3 h-3" />
        Execution Feed
        <button
          onClick={clear}
          className="ml-auto flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-2 font-mono text-[11px] space-y-1 bg-[#050810]">
        {lines.length === 0 && (
          <span className="text-muted-foreground">
            <span className="text-primary">▶</span> awaiting execution output...
          </span>
        )}
        {lines.map((line) => {
          const agentColor = AGENT_COLORS[line.agent_id] ?? "#5A6A7E";
          const ts = format(new Date(line.timestamp), "HH:mm:ss");
          const exitOk = line.exit_code === 0 || line.exit_code === undefined;

          return (
            <div key={line.id} className="space-y-0.5">
              {/* Command header */}
              {line.command && (
                <div className="flex items-center gap-1.5 opacity-70">
                  <span className="text-[10px]" style={{ color: agentColor }}>
                    [{line.agent_id.replace("-agent", "").toUpperCase()}]
                  </span>
                  <span className="text-[10px] text-muted-foreground">{ts}</span>
                  <span className="text-primary">$</span>
                  <span className="text-foreground">{line.command}</span>
                </div>
              )}
              {/* Output lines */}
              {line.output.split("\n").map((row, i) => (
                row.trim() && (
                  <div key={i} className="pl-2 text-[10px] leading-relaxed">
                    <span
                      className={exitOk ? "text-[#9BE8A7]" : "text-[#FF8A80]"}
                    >
                      {row}
                    </span>
                  </div>
                )
              ))}
              {/* Exit code badge */}
              {line.exit_code !== undefined && (
                <div className="pl-2">
                  <span
                    className={`text-[9px] font-bold ${
                      exitOk ? "text-[#00C851]" : "text-[#FF3B30]"
                    }`}
                  >
                    exit:{line.exit_code}
                  </span>
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
