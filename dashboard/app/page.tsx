import Link from "next/link";
import SecuNetLogo from "@/components/SecuNetLogo";
import ArchitectureDiagram from "@/components/ArchitectureDiagram";
import { Eye, Zap, Radio, Wrench, Monitor, ArrowRight, Github, Shield, Terminal } from "lucide-react";

const AGENTS = [
  { id: "recon",     icon: Eye,      color: "#00D4FF", name: "Recon",     desc: "Network discovery, service fingerprinting, CVE lookup, Shodan integration." },
  { id: "exploit",   icon: Zap,      color: "#FF3B30", name: "Exploit",   desc: "Automated exploitation with risk assessment and HITL gate on critical actions." },
  { id: "detect",    icon: Radio,    color: "#FFB300", name: "Detect",    desc: "SIEM integration, Sigma rule generation, real-time detection scoring." },
  { id: "remediate", icon: Wrench,   color: "#00C851", name: "Remediate", desc: "Patch generation, fix deployment — always HITL-gated before execution." },
  { id: "monitor",   icon: Monitor,  color: "#9B59B6", name: "Monitor",   desc: "Tripwire deployment, anomaly detection, continuous posture monitoring." },
];

const FEATURES = [
  { icon: Shield,   title: "Purple Team Architecture",  body: "Recon, Exploit, Detect, Remediate, and Monitor agents run in parallel — attack and defend simultaneously." },
  { icon: Terminal, title: "Human-in-the-Loop Controls", body: "Every high-risk action requires engineer approval. Full pause, resume, and kill controls from the dashboard." },
  { icon: Eye,      title: "Tactical Operations Center", body: "Live WebSocket feed, agent status, findings timeline, HITL queue, and terminal output in a single view." },
  { icon: Zap,      title: "LLM Provider Agnostic",      body: "Swap between Anthropic, OpenAI, and local LM Studio models via a single environment variable." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#080C14] text-[#E8EDF5] overflow-x-hidden">

      {/* Nav */}
      <nav className="border-b border-[#1E2D47] px-6 py-4 flex items-center justify-between">
        <SecuNetLogo size={36} />
        <div className="flex items-center gap-6">
          <a
            href="https://github.com/sup3rus3r/secunet"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-[#8B9AB5] hover:text-[#E8EDF5] transition-colors font-mono"
          >
            <Github className="w-4 h-4" />
            GitHub
          </a>
          <Link
            href="/login"
            className="px-4 py-2 border border-[#00D4FF]/40 text-[#00D4FF] rounded text-sm font-mono hover:bg-[#00D4FF]/10 transition-colors"
          >
            Launch TOC
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#00D4FF]/20 bg-[#00D4FF]/05 text-[#00D4FF] text-xs font-mono mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00D4FF] animate-pulse" />
          Open Source · Autonomous Purple Team Platform
        </div>

        <h1 className="text-5xl font-bold tracking-tight mb-6 leading-tight">
          Autonomous security testing,{" "}
          <span className="text-[#00D4FF]">attack and defend</span>{" "}
          in parallel
        </h1>

        <p className="text-lg text-[#8B9AB5] max-w-2xl mx-auto mb-10 leading-relaxed">
          SecuNet deploys a coordinated fleet of AI agents to scan, exploit, detect, remediate,
          and monitor your infrastructure — all from a single tactical operations center.
          You stay in control. Every high-risk action requires your approval.
        </p>

        <div className="flex items-center justify-center gap-4">
          <Link
            href="/login"
            className="flex items-center gap-2 px-6 py-3 bg-[#00D4FF] text-[#080C14] rounded font-mono font-bold text-sm hover:bg-[#00D4FF]/90 transition-colors"
          >
            Open TOC
            <ArrowRight className="w-4 h-4" />
          </Link>
          <a
            href="https://github.com/sup3rus3r/secunet"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-6 py-3 border border-[#1E2D47] text-[#8B9AB5] rounded font-mono text-sm hover:border-[#00D4FF]/40 hover:text-[#E8EDF5] transition-colors"
          >
            <Github className="w-4 h-4" />
            View Source
          </a>
        </div>
      </section>

      {/* Agent fleet grid */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <p className="text-xs font-mono text-[#8B9AB5] tracking-widest text-center mb-8 uppercase">
          Agent Fleet
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {AGENTS.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                className="rounded border bg-[#0D1321] p-4 space-y-2 hover:border-opacity-60 transition-colors"
                style={{ borderColor: `${agent.color}20` }}
              >
                <div
                  className="w-8 h-8 rounded flex items-center justify-center"
                  style={{ backgroundColor: `${agent.color}15` }}
                >
                  <Icon className="w-4 h-4" style={{ color: agent.color }} />
                </div>
                <p className="font-mono font-bold text-sm" style={{ color: agent.color }}>
                  {agent.name}
                </p>
                <p className="text-[11px] text-[#8B9AB5] leading-relaxed">{agent.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-[#1E2D47] bg-[#0D1321]">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div key={f.title} className="flex gap-4">
                  <div className="w-10 h-10 rounded border border-[#1E2D47] bg-[#080C14] flex items-center justify-center shrink-0">
                    <Icon className="w-5 h-5 text-[#00D4FF]" />
                  </div>
                  <div>
                    <h3 className="font-mono font-bold text-sm text-[#E8EDF5] mb-1">{f.title}</h3>
                    <p className="text-sm text-[#8B9AB5] leading-relaxed">{f.body}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Architecture diagram */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <p className="text-xs font-mono text-[#8B9AB5] tracking-widest text-center mb-8 uppercase">
          Architecture
        </p>
        <div className="rounded-lg border border-[#1E2D47] overflow-hidden">
          <ArchitectureDiagram />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#1E2D47] px-6 py-8">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <SecuNetLogo size={24} />
          <p className="text-xs text-[#8B9AB5] font-mono">
            Open source. Use responsibly. Only on networks you own or have written permission to test.
          </p>
        </div>
      </footer>

    </div>
  );
}
