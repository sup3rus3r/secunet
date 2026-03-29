"use client";
import { useMissionStore } from "@/store/mission";
import { useFindingsStore } from "@/store/findings";
import { BarChart3 } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip,
} from "recharts";
import { useRef, useEffect, useState } from "react";

// Build a running history of coverage score samples
const MAX_SAMPLES = 20;

export default function MetricsPanel() {
  const { coverage_score, hosts_discovered, open_findings, critical_findings } =
    useMissionStore();

  const [history, setHistory] = useState<{ t: number; score: number }[]>([
    { t: 0, score: 0 },
  ]);
  const counterRef = useRef(0);

  useEffect(() => {
    counterRef.current += 1;
    setHistory((prev) => {
      const next = [...prev, { t: counterRef.current, score: coverage_score }];
      return next.length > MAX_SAMPLES ? next.slice(-MAX_SAMPLES) : next;
    });
  }, [coverage_score]);

  const findings = useFindingsStore((s) => s.findings);
  const bySeverity = [
    { label: "CRIT",  value: findings.filter((f) => f.severity === "critical" && !f.remediated).length, color: "#FF3B30" },
    { label: "HIGH",  value: findings.filter((f) => f.severity === "high"     && !f.remediated).length, color: "#FF6B35" },
    { label: "MED",   value: findings.filter((f) => f.severity === "medium"   && !f.remediated).length, color: "#FFB300" },
    { label: "LOW",   value: findings.filter((f) => f.severity === "low"      && !f.remediated).length, color: "#00C851" },
  ];

  return (
    <div className="panel">
      <div className="panel-header">
        <BarChart3 className="w-3 h-3" />
        Detection Coverage
      </div>
      <div className="p-3 space-y-3">
        {/* Score gauge */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-muted-foreground font-mono">COVERAGE SCORE</span>
            <span className="text-sm font-mono font-bold text-primary">{coverage_score}%</span>
          </div>
          <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width:      `${coverage_score}%`,
                background: `linear-gradient(90deg, #00D4FF, #00C851)`,
              }}
            />
          </div>
        </div>

        {/* Sparkline */}
        <div className="h-16">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00D4FF" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00D4FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="t" hide />
              <YAxis domain={[0, 100]} hide />
              <Tooltip
                contentStyle={{
                  background: "#0D1321",
                  border: "1px solid rgba(0,212,255,0.2)",
                  borderRadius: 4,
                  fontSize: 10,
                  fontFamily: "var(--font-jetbrains-mono)",
                  color: "#E0E6F0",
                }}
                formatter={(v) => [`${v}%`, "coverage"]}
                labelFormatter={() => ""}
              />
              <Area
                type="monotone"
                dataKey="score"
                stroke="#00D4FF"
                strokeWidth={1.5}
                fill="url(#scoreGrad)"
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Severity breakdown */}
        <div className="grid grid-cols-4 gap-1">
          {bySeverity.map(({ label, value, color }) => (
            <div key={label} className="flex flex-col items-center rounded bg-secondary/40 py-1.5">
              <span className="text-xs font-mono font-bold" style={{ color }}>{value}</span>
              <span className="text-[9px] text-muted-foreground font-mono">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
