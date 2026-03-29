"use client";
import { useLayoutEffect } from "react";
import { useSession }      from "next-auth/react";
import { useRouter }       from "next/navigation";

import WsBootstrap       from "@/components/toc/WsBootstrap";
import TopBar            from "@/components/toc/TopBar";
import AgentStatusPanel  from "@/components/toc/AgentStatusPanel";
import ChatPanel         from "@/components/toc/ChatPanel";
import ActivityFeed      from "@/components/toc/ActivityFeed";
import FindingsPanel     from "@/components/toc/FindingsPanel";
import HitlQueue         from "@/components/toc/HitlQueue";
import MetricsPanel      from "@/components/toc/MetricsPanel";
import TerminalFeed      from "@/components/toc/TerminalFeed";
import AttackCoverage    from "@/components/toc/AttackCoverage";

export default function TacticalOperationsCenter() {
  const { status } = useSession();
  const router     = useRouter();

  useLayoutEffect(() => {
    if (status === "unauthenticated") router.push("/login");
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <span className="font-mono text-xs text-primary animate-pulse">
          INITIALISING SECUNET...
        </span>
      </div>
    );
  }

  if (status === "unauthenticated") return null;

  return (
    <>
      <WsBootstrap />

      {/* Full-viewport fixed layout — no page scroll */}
      <div className="flex flex-col h-screen w-screen overflow-hidden bg-background">

        {/* ── Top bar ─────────────────────────────────────────────── */}
        <TopBar />

        {/* ── Main grid ───────────────────────────────────────────── */}
        {/*
          3-column layout:
            Left  (240px) — agent fleet + metrics
            Center (flex) — comms feed
            Right (280px) — findings + hitl
        */}
        <div className="flex flex-1 min-h-0 gap-1 p-1">

          {/* Left column */}
          <div className="w-[240px] shrink-0 flex flex-col gap-1 min-h-0">
            <div className="flex-1 min-h-0">
              <AgentStatusPanel />
            </div>
            <div className="shrink-0">
              <MetricsPanel />
            </div>
          </div>

          {/* Center column — activity trail + comms */}
          <div className="flex-1 min-w-0 min-h-0 flex gap-1">
            <div className="flex-1 min-w-0 min-h-0">
              <ActivityFeed />
            </div>
            <div className="flex-1 min-w-0 min-h-0">
              <ChatPanel />
            </div>
          </div>

          {/* Right column — findings + HITL */}
          <div className="w-[280px] shrink-0 flex flex-col gap-1 min-h-0">
            <div className="flex-1 min-h-0">
              <FindingsPanel />
            </div>
            <div className="shrink-0">
              <HitlQueue />
            </div>
          </div>
        </div>

        {/* ── ATT&CK Coverage ──────────────────────────────────────── */}
        <div className="shrink-0 px-1 pb-0">
          <AttackCoverage />
        </div>

        {/* ── Terminal feed ────────────────────────────────────────── */}
        <div className="h-[180px] shrink-0 p-1 pt-0">
          <TerminalFeed />
        </div>

      </div>
    </>
  );
}
