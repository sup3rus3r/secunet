"use client";
import { useState } from "react";
import { useMissionStore } from "@/store/mission";
import { useMessagesStore } from "@/store/messages";
import { useFindingsStore } from "@/store/findings";
import { useTerminalStore } from "@/store/terminal";
import { useHitlStore } from "@/store/hitl";
import { useCoverageStore } from "@/store/coverage";
import { Wifi, WifiOff, Target, Activity, Pencil, RefreshCw, FilePlus, FileText } from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import SecuNetLogo from "@/components/SecuNetLogo";
import ReportModal from "@/components/toc/ReportModal";

const PHASE_COLORS: Record<string, string> = {
  IDLE:        "text-muted-foreground",
  RECON:       "text-[#00D4FF]",
  EXPLOIT:     "text-[#FF3B30]",
  DETECT:      "text-[#FFB300]",
  REMEDIATE:   "text-agent-remediate",
  MONITOR:     "text-[#9B59B6]",
  REPORTING:   "text-[#FF6B35]",
};

const CC = process.env.NEXT_PUBLIC_CC_URL ?? "http://localhost:8001";

export default function TopBar() {
  const { data: session } = useSession();
  const { mission_name, current_phase, target_scope, coverage_score, ws_connected } =
    useMissionStore();

  const newSession     = useMessagesStore((s) => s.newSession);
  const clearFindings  = useFindingsStore((s) => s.clear);
  const clearTerminal  = useTerminalStore((s) => s.clear);
  const resetCoverage  = useCoverageStore((s) => s.reset);
  const clearHitl      = useHitlStore((s) => s.clear);

  const [editingScope,  setEditingScope]  = useState(false);
  const [scopeDraft,    setScopeDraft]    = useState("");
  const [detecting,     setDetecting]     = useState(false);
  const [confirmNew,    setConfirmNew]    = useState(false);
  const [showReport,    setShowReport]    = useState(false);

  const handleNewSession = async () => {
    if (!confirmNew) { setConfirmNew(true); setTimeout(() => setConfirmNew(false), 3000); return; }
    // Clear all frontend stores
    newSession();
    clearFindings();
    clearTerminal();
    clearHitl();
    resetCoverage();
    setConfirmNew(false);
    // Wipe backend memory: Redis windows, ChromaDB, PostgreSQL, mission state
    try {
      await fetch(`${CC}/mission/reset`, { method: "POST" });
    } catch { /* CC will broadcast clean mission.state via WS */ }
  };

  const openScopeEdit = () => {
    setScopeDraft(target_scope ?? "");
    setEditingScope(true);
  };

  const saveScope = async () => {
    const scope = scopeDraft.trim();
    if (!scope) { setEditingScope(false); return; }
    try {
      await fetch(`${CC}/mission/scope`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ scope }),
      });
    } catch { /* CC will broadcast target_scope back via WS */ }
    setEditingScope(false);
  };

  const detectNetwork = async () => {
    setDetecting(true);
    try {
      const res  = await fetch(`${CC}/network/local`);
      const data = await res.json() as { cidr?: string };
      if (data.cidr) setScopeDraft(data.cidr);
    } catch { }
    setDetecting(false);
  };

  const phaseColor = PHASE_COLORS[current_phase?.toUpperCase()] ?? "text-foreground";

  return (
    <header className="h-14 flex items-center justify-between px-4 border-b border-border bg-card shrink-0 z-10">
      {/* Left — brand + mission */}
      <div className="flex items-center gap-4">
        <SecuNetLogo size={28} />
        <div className="h-4 w-px bg-border" />
        <span className="font-mono text-xs text-foreground font-semibold tracking-wide">
          {mission_name}
        </span>
        {editingScope ? (
          <form
            onSubmit={(e) => { e.preventDefault(); saveScope(); }}
            className="flex items-center gap-1"
          >
            <Target className="w-3 h-3 text-primary shrink-0" />
            <input
              autoFocus
              value={scopeDraft}
              onChange={(e) => setScopeDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && setEditingScope(false)}
              placeholder="10.0.0.0/24"
              className="w-36 bg-transparent border-b border-primary font-mono text-xs text-foreground outline-none px-0.5"
            />
            <button
              type="button"
              title="Auto-detect local network"
              onClick={detectNetwork}
              className="text-muted-foreground hover:text-primary transition-colors ml-0.5"
            >
              <RefreshCw className={`w-3 h-3 ${detecting ? "animate-spin" : ""}`} />
            </button>
            <button
              type="submit"
              className="font-mono text-[10px] text-agent-remediate hover:opacity-80 ml-0.5"
            >
              SET
            </button>
          </form>
        ) : (
          <button
            onClick={openScopeEdit}
            className="flex items-center gap-1 text-xs text-muted-foreground font-mono hover:text-foreground transition-colors group"
          >
            <Target className="w-3 h-3" />
            <span>{target_scope || "set scope"}</span>
            <Pencil className="w-2.5 h-2.5 opacity-0 group-hover:opacity-50 transition-opacity" />
          </button>
        )}
      </div>

      {/* Center — phase indicator */}
      <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-2">
        <Activity className="w-3 h-3 text-muted-foreground" />
        <span className={`font-mono text-xs font-bold tracking-widest ${phaseColor}`}>
          PHASE: {current_phase}
        </span>
      </div>

      {/* Right — coverage + WS status + user */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-mono">COVERAGE</span>
          <div className="flex items-center gap-1">
            <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500"
                style={{ width: `${coverage_score}%` }}
              />
            </div>
            <span className="font-mono text-xs text-primary font-bold w-8">
              {coverage_score}%
            </span>
          </div>
        </div>

        <div className="h-4 w-px bg-border" />

        {/* Report */}
        <button
          onClick={() => setShowReport(true)}
          title="Generate mission report"
          className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-agent-recon transition-colors"
        >
          <FileText className="w-3 h-3" />
          REPORT
        </button>

        <div className="h-4 w-px bg-border" />

        {/* New session */}
        <button
          onClick={handleNewSession}
          title="Start new session (clears comms + findings)"
          className={`flex items-center gap-1 font-mono text-[10px] transition-colors ${
            confirmNew
              ? "text-destructive animate-pulse"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <FilePlus className="w-3 h-3" />
          {confirmNew ? "CONFIRM?" : "NEW SESSION"}
        </button>

        <div className="h-4 w-px bg-border" />

        {/* WS indicator */}
        <div className="flex items-center gap-1">
          {ws_connected ? (
            <Wifi className="w-3.5 h-3.5 text-agent-remediate" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-destructive animate-pulse" />
          )}
          <span className={`font-mono text-xs ${ws_connected ? "text-agent-remediate" : "text-destructive"}`}>
            {ws_connected ? "LIVE" : "RECONNECTING"}
          </span>
        </div>

        <div className="h-4 w-px bg-border" />

        {/* User */}
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="text-xs text-muted-foreground font-mono hover:text-foreground transition-colors"
        >
          {session?.user?.name ?? "engineer"} ×
        </button>
      </div>
    </header>

      {showReport && <ReportModal onClose={() => setShowReport(false)} />}
  );
}
