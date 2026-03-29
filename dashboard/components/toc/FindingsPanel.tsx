"use client";
import { useFindingsStore, type Severity } from "@/store/findings";
import { AGENT_COLORS } from "@/store/agents";
import { format } from "date-fns";
import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "#FF3B30",
  high:     "#FF6B35",
  medium:   "#FFB300",
  low:      "#00C851",
  info:     "#00D4FF",
};

const SEVERITY_BG: Record<Severity, string> = {
  critical: "rgba(255, 59, 48, 0.12)",
  high:     "rgba(255, 107, 53, 0.10)",
  medium:   "rgba(255, 179, 0, 0.10)",
  low:      "rgba(0, 200, 81, 0.08)",
  info:     "rgba(0, 212, 255, 0.08)",
};

export default function FindingsPanel() {
  const findings = useFindingsStore((s) => s.findings);
  const open     = findings.filter((f) => !f.remediated);
  const counts: Partial<Record<Severity, number>> = {
    critical: open.filter((f) => f.severity === "critical").length,
    high:     open.filter((f) => f.severity === "high").length,
    medium:   open.filter((f) => f.severity === "medium").length,
    low:      open.filter((f) => f.severity === "low").length,
  };

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <ShieldAlert className="w-3 h-3" />
        Findings
        {open.length > 0 && (
          <span className="ml-auto text-[#FF3B30] font-mono text-[10px] font-bold">
            {open.length} open
          </span>
        )}
      </div>

      {/* Severity summary bar */}
      {open.length > 0 && (
        <div className="flex gap-2 px-3 py-1.5 border-b border-border">
          {(["critical", "high", "medium", "low"] as Severity[]).map((sev) => (
            (counts[sev] ?? 0) > 0 && (
              <div key={sev} className="flex items-center gap-1">
                <div
                  className="w-2 h-2 rounded-sm"
                  style={{ backgroundColor: SEVERITY_COLORS[sev] }}
                />
                <span
                  className="text-[10px] font-mono font-bold"
                  style={{ color: SEVERITY_COLORS[sev] }}
                >
                  {counts[sev] ?? 0}
                </span>
              </div>
            )
          ))}
        </div>
      )}

      <div className="panel-body space-y-1.5">
        {findings.length === 0 && (
          <div className="text-[10px] text-muted-foreground font-mono text-center py-8">
            — no findings yet —
          </div>
        )}
        {findings.map((f) => (
          <div
            key={f.finding_id}
            className={`rounded border px-2.5 py-2 space-y-1 ${f.remediated ? "opacity-40" : ""}`}
            style={{
              borderColor: `${SEVERITY_COLORS[f.severity]}33`,
              backgroundColor: SEVERITY_BG[f.severity],
            }}
          >
            <div className="flex items-start gap-1.5">
              {f.remediated
                ? <CheckCircle2 className="w-3 h-3 text-[#00C851] shrink-0 mt-0.5" />
                : <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" style={{ color: SEVERITY_COLORS[f.severity] }} />
              }
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className="text-[10px] font-mono font-bold uppercase"
                    style={{ color: SEVERITY_COLORS[f.severity] }}
                  >
                    {f.severity}
                  </span>
                  {f.cve && (
                    <span className="text-[10px] font-mono text-[#FF6B35]">{f.cve}</span>
                  )}
                  {f.technique && (
                    <span className="text-[10px] font-mono text-muted-foreground">{f.technique}</span>
                  )}
                </div>
                <div className="text-xs font-mono text-foreground leading-snug">{f.title}</div>
                {f.host && (
                  <div className="text-[10px] font-mono text-primary">{f.host}</div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
              <span style={{ color: AGENT_COLORS[f.agent_id] ?? "#5A6A7E" }}>
                {f.agent_id.replace("-agent", "").toUpperCase()}
              </span>
              <span>·</span>
              <span>{format(new Date(f.timestamp), "HH:mm:ss")}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
