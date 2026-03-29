"use client";
import { useState } from "react";
import { useCoverageStore, TechniqueState } from "@/store/coverage";
import { ChevronDown, ChevronUp, Crosshair } from "lucide-react";

// ── MITRE ATT&CK technique data ────────────────────────────────────────────
const TECHNIQUES: Record<string, { name: string; tactic: string }> = {
  "T1595":     { name: "Active Scanning",                        tactic: "Reconnaissance" },
  "T1592":     { name: "Gather Victim Host Info",                tactic: "Reconnaissance" },
  "T1590":     { name: "Gather Victim Network Info",             tactic: "Reconnaissance" },
  "T1589":     { name: "Gather Victim Identity Info",            tactic: "Reconnaissance" },
  "T1190":     { name: "Exploit Public-Facing Application",      tactic: "Initial Access" },
  "T1133":     { name: "External Remote Services",               tactic: "Initial Access" },
  "T1059":     { name: "Command and Scripting Interpreter",      tactic: "Execution" },
  "T1059.001": { name: "PowerShell",                             tactic: "Execution" },
  "T1059.004": { name: "Unix Shell",                             tactic: "Execution" },
  "T1203":     { name: "Exploitation for Client Execution",      tactic: "Execution" },
  "T1053":     { name: "Scheduled Task/Job",                     tactic: "Persistence" },
  "T1505.003": { name: "Web Shell",                              tactic: "Persistence" },
  "T1068":     { name: "Exploitation for Privilege Escalation",  tactic: "Privilege Escalation" },
  "T1548":     { name: "Abuse Elevation Control Mechanism",      tactic: "Privilege Escalation" },
  "T1078":     { name: "Valid Accounts",                         tactic: "Defense Evasion" },
  "T1055":     { name: "Process Injection",                      tactic: "Defense Evasion" },
  "T1562":     { name: "Impair Defenses",                        tactic: "Defense Evasion" },
  "T1070":     { name: "Indicator Removal",                      tactic: "Defense Evasion" },
  "T1027":     { name: "Obfuscated Files or Information",        tactic: "Defense Evasion" },
  "T1110":     { name: "Brute Force",                            tactic: "Credential Access" },
  "T1110.001": { name: "Password Guessing",                      tactic: "Credential Access" },
  "T1110.003": { name: "Password Spraying",                      tactic: "Credential Access" },
  "T1003":     { name: "OS Credential Dumping",                  tactic: "Credential Access" },
  "T1046":     { name: "Network Service Discovery",              tactic: "Discovery" },
  "T1018":     { name: "Remote System Discovery",                tactic: "Discovery" },
  "T1082":     { name: "System Information Discovery",           tactic: "Discovery" },
  "T1083":     { name: "File and Directory Discovery",           tactic: "Discovery" },
  "T1087":     { name: "Account Discovery",                      tactic: "Discovery" },
  "T1057":     { name: "Process Discovery",                      tactic: "Discovery" },
  "T1049":     { name: "System Network Connections Discovery",   tactic: "Discovery" },
  "T1021":     { name: "Remote Services",                        tactic: "Lateral Movement" },
  "T1021.001": { name: "Remote Desktop Protocol",                tactic: "Lateral Movement" },
  "T1021.004": { name: "SSH",                                    tactic: "Lateral Movement" },
  "T1210":     { name: "Exploitation of Remote Services",        tactic: "Lateral Movement" },
  "T1213":     { name: "Data from Information Repositories",     tactic: "Collection" },
  "T1560":     { name: "Archive Collected Data",                 tactic: "Collection" },
  "T1074":     { name: "Data Staged",                            tactic: "Collection" },
  "T1071":     { name: "Application Layer Protocol",             tactic: "Command and Control" },
  "T1105":     { name: "Ingress Tool Transfer",                  tactic: "Command and Control" },
  "T1048":     { name: "Exfiltration Over Alternative Protocol", tactic: "Exfiltration" },
  "T1041":     { name: "Exfiltration Over C2 Channel",           tactic: "Exfiltration" },
};

// Canonical tactic order
const TACTIC_ORDER = [
  "Reconnaissance",
  "Initial Access",
  "Execution",
  "Persistence",
  "Privilege Escalation",
  "Defense Evasion",
  "Credential Access",
  "Discovery",
  "Lateral Movement",
  "Collection",
  "Command and Control",
  "Exfiltration",
];

// Short tactic labels for compact header
const TACTIC_SHORT: Record<string, string> = {
  "Reconnaissance":      "RECON",
  "Initial Access":      "INIT",
  "Execution":           "EXEC",
  "Persistence":         "PERS",
  "Privilege Escalation":"PRIVESC",
  "Defense Evasion":     "EVASION",
  "Credential Access":   "CREDS",
  "Discovery":           "DISC",
  "Lateral Movement":    "LATERAL",
  "Collection":          "COLLECT",
  "Command and Control": "C2",
  "Exfiltration":        "EXFIL",
};

const STATE_COLOR: Record<TechniqueState, string> = {
  attempted:  "#FF6B35",
  detected:   "#FFB300",
  remediated: "#00C851",
};

const STATE_BG: Record<TechniqueState, string> = {
  attempted:  "rgba(255,107,53,0.15)",
  detected:   "rgba(255,179,0,0.15)",
  remediated: "rgba(0,200,81,0.12)",
};

// Group techniques by tactic
const byTactic = TACTIC_ORDER.reduce<Record<string, { id: string; name: string }[]>>(
  (acc, tactic) => {
    acc[tactic] = Object.entries(TECHNIQUES)
      .filter(([, v]) => v.tactic === tactic)
      .map(([id, v]) => ({ id, name: v.name }));
    return acc;
  },
  {}
);

const TOTAL = Object.keys(TECHNIQUES).length;

export default function AttackCoverage() {
  const [expanded, setExpanded] = useState(false);
  const [tooltip, setTooltip]   = useState<{ id: string; name: string; state?: TechniqueState } | null>(null);
  const techniques               = useCoverageStore((s) => s.techniques);

  const covered    = Object.keys(techniques).length;
  const attempted  = Object.values(techniques).filter((s) => s === "attempted").length;
  const detected   = Object.values(techniques).filter((s) => s === "detected").length;
  const remediated = Object.values(techniques).filter((s) => s === "remediated").length;
  const coveragePct = Math.round((covered / TOTAL) * 100);

  return (
    <div className="panel">
      {/* Header — always visible, click to expand */}
      <button
        className="panel-header w-full text-left flex items-center gap-2 cursor-pointer select-none"
        onClick={() => setExpanded((v) => !v)}
      >
        <Crosshair className="w-3 h-3 text-primary shrink-0" />
        <span>ATT&amp;CK Coverage</span>

        {/* Mini stats */}
        <div className="flex items-center gap-2 ml-2">
          <span className="font-mono text-[9px] text-[#FF6B35]">{attempted} attempted</span>
          <span className="font-mono text-[9px] text-[#FFB300]">{detected} detected</span>
          <span className="font-mono text-[9px] text-[#00C851]">{remediated} remediated</span>
        </div>

        {/* Coverage bar */}
        <div className="flex items-center gap-1 ml-auto">
          <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${coveragePct}%`,
                background: coveragePct > 60 ? "#00C851" : coveragePct > 30 ? "#FFB300" : "#FF6B35",
              }}
            />
          </div>
          <span className="font-mono text-[10px] text-primary font-bold w-8">{coveragePct}%</span>
        </div>

        {expanded
          ? <ChevronUp className="w-3 h-3 text-muted-foreground ml-1 shrink-0" />
          : <ChevronDown className="w-3 h-3 text-muted-foreground ml-1 shrink-0" />
        }
      </button>

      {/* Matrix — only when expanded */}
      {expanded && (
        <div className="px-2 pb-2 pt-1 overflow-x-auto">
          <div className="flex gap-1 min-w-max relative">
            {TACTIC_ORDER.map((tactic) => {
              const cells = byTactic[tactic] ?? [];
              return (
                <div key={tactic} className="flex flex-col gap-0.5">
                  {/* Tactic header */}
                  <div className="text-[8px] font-mono text-muted-foreground tracking-wider text-center mb-0.5 px-0.5">
                    {TACTIC_SHORT[tactic]}
                  </div>
                  {/* Technique cells */}
                  {cells.map(({ id, name }) => {
                    const state = techniques[id];
                    return (
                      <div
                        key={id}
                        className="relative w-[52px] h-[18px] rounded-sm flex items-center justify-center cursor-default transition-all duration-200"
                        style={{
                          backgroundColor: state ? STATE_BG[state] : "rgba(30,45,71,0.5)",
                          border: `1px solid ${state ? STATE_COLOR[state] : "rgba(30,45,71,0.4)"}`,
                        }}
                        onMouseEnter={() => setTooltip({ id, name, state })}
                        onMouseLeave={() => setTooltip(null)}
                      >
                        <span
                          className="font-mono text-[7.5px] font-bold truncate px-0.5"
                          style={{ color: state ? STATE_COLOR[state] : "#3A4A60" }}
                        >
                          {id}
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Tooltip */}
          {tooltip && (
            <div className="mt-2 flex items-center gap-2 px-2 py-1 rounded bg-[#0D1321] border border-[#1E2D47]">
              <span
                className="font-mono text-[9px] font-bold"
                style={{ color: tooltip.state ? STATE_COLOR[tooltip.state] : "#5A7090" }}
              >
                {tooltip.id}
              </span>
              <span className="font-mono text-[9px] text-muted-foreground">{tooltip.name}</span>
              <span
                className="ml-auto font-mono text-[8px] font-bold uppercase"
                style={{ color: tooltip.state ? STATE_COLOR[tooltip.state] : "#3A4A60" }}
              >
                {tooltip.state ?? "untested"}
              </span>
            </div>
          )}

          {/* Legend */}
          <div className="flex items-center gap-4 mt-2 pt-1.5 border-t border-border">
            {(["attempted", "detected", "remediated"] as TechniqueState[]).map((s) => (
              <div key={s} className="flex items-center gap-1">
                <div
                  className="w-2.5 h-2.5 rounded-sm"
                  style={{ backgroundColor: STATE_BG[s], border: `1px solid ${STATE_COLOR[s]}` }}
                />
                <span className="font-mono text-[8px] text-muted-foreground capitalize">{s}</span>
              </div>
            ))}
            <div className="flex items-center gap-1">
              <div className="w-2.5 h-2.5 rounded-sm bg-[rgba(30,45,71,0.5)] border border-[#1E2D47]" />
              <span className="font-mono text-[8px] text-muted-foreground">untested</span>
            </div>
            <span className="ml-auto font-mono text-[8px] text-muted-foreground">
              {covered}/{TOTAL} techniques covered
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
