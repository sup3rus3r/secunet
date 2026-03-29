"use client";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useMessagesStore, type ChatMessage } from "@/store/messages";
import { AGENT_COLORS, useAgentsStore } from "@/store/agents";
import { sendWsMessage } from "@/lib/ws-client";
import { useSession } from "next-auth/react";
import { format } from "date-fns";
import { MessageSquare, Send } from "lucide-react";

// All mentionable targets in display order
const MENTION_TARGETS = [
  { id: "commander",       label: "COMMANDER" },
  { id: "recon-agent",     label: "RECON"     },
  { id: "exploit-agent",   label: "EXPLOIT"   },
  { id: "detect-agent",    label: "DETECT"    },
  { id: "remediate-agent", label: "REMEDIATE" },
  { id: "monitor-agent",   label: "MONITOR"   },
] as const;

const ENGINEER_COLOR = "#E0E6F0";

function getSenderColor(from_id: string): string {
  return AGENT_COLORS[from_id] ?? ENGINEER_COLOR;
}

function getSenderLabel(from_id: string): string {
  const labels: Record<string, string> = {
    "recon-agent":     "RECON",
    "exploit-agent":   "EXPLOIT",
    "detect-agent":    "DETECT",
    "remediate-agent": "REMEDIATE",
    "monitor-agent":   "MONITOR",
    "commander":       "COMMANDER",
  };
  return labels[from_id] ?? from_id.toUpperCase();
}

function MessageRow({ msg }: { msg: ChatMessage }) {
  const color = getSenderColor(msg.from_id);
  const label = getSenderLabel(msg.from_id);
  const ts    = format(new Date(msg.timestamp), "HH:mm:ss");
  const isEngineer = !AGENT_COLORS[msg.from_id];

  return (
    <div className={`flex flex-col gap-0.5 py-1 ${isEngineer ? "items-end" : ""}`}>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-muted-foreground font-mono">{ts}</span>
        <span className="text-[10px] font-mono font-bold" style={{ color }}>
          {label}
        </span>
        {msg.to && msg.to !== "broadcast" && (
          <span className="text-[10px] text-muted-foreground font-mono">
            → {typeof msg.to === "string" ? msg.to.toUpperCase() : (msg.to as string[]).join(", ").toUpperCase()}
          </span>
        )}
      </div>
      <div
        className={`text-xs font-mono leading-relaxed max-w-[90%] rounded px-2 py-1 ${
          isEngineer
            ? "bg-secondary text-foreground"
            : "bg-card border border-border text-foreground"
        }`}
        style={{ borderColor: `${color}22` }}
      >
        {isEngineer ? msg.content : (
          <ReactMarkdown
            components={{
              p:      ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
              strong: ({ children }) => <strong className="font-bold" style={{ color }}>{children}</strong>,
              em:     ({ children }) => <em className="italic opacity-80">{children}</em>,
              code:   ({ children }) => <code className="bg-black/30 rounded px-1 text-[11px]">{children}</code>,
              pre:    ({ children }) => <pre className="bg-black/30 rounded p-2 overflow-x-auto my-1 text-[11px]">{children}</pre>,
              ul:     ({ children }) => <ul className="list-disc list-inside space-y-0.5 my-1">{children}</ul>,
              ol:     ({ children }) => <ol className="list-decimal list-inside space-y-0.5 my-1">{children}</ol>,
              li:     ({ children }) => <li>{children}</li>,
              h1:     ({ children }) => <p className="font-bold text-sm" style={{ color }}>{children}</p>,
              h2:     ({ children }) => <p className="font-bold" style={{ color }}>{children}</p>,
              h3:     ({ children }) => <p className="font-semibold opacity-90">{children}</p>,
            }}
          >
            {msg.content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}

export default function ChatPanel() {
  const messages     = useMessagesStore((s) => s.messages);
  const agents       = useAgentsStore((s) => s.agents);
  const { data: session } = useSession();
  const [input, setInput] = useState("");
  const bottomRef    = useRef<HTMLDivElement>(null);
  const autoScroll   = useRef(true);
  const listRef      = useRef<HTMLDivElement>(null);
  const inputRef     = useRef<HTMLInputElement>(null);

  // Mention picker state
  const [mentionAnchor, setMentionAnchor] = useState<{ start: number; query: string } | null>(null);
  const [menuIndex, setMenuIndex]         = useState(0);

  const mentionTargets = mentionAnchor
    ? MENTION_TARGETS.filter((t) =>
        t.label.toLowerCase().startsWith(mentionAnchor.query.toLowerCase()) ||
        t.id.toLowerCase().startsWith(mentionAnchor.query.toLowerCase())
      )
    : [];

  function detectMention(value: string, cursor: number) {
    // Walk back from cursor to find an @ not preceded by a word char
    const before = value.slice(0, cursor);
    const match  = before.match(/@([\w-]*)$/);
    if (match) {
      setMentionAnchor({ start: before.length - match[0].length, query: match[1] });
      setMenuIndex(0);
    } else {
      setMentionAnchor(null);
    }
  }

  function applyMention(target: typeof MENTION_TARGETS[number]) {
    if (!mentionAnchor) return;
    const before = input.slice(0, mentionAnchor.start);
    const after  = input.slice(inputRef.current?.selectionStart ?? input.length);
    const next   = `${before}@${target.id} ${after}`;
    setInput(next);
    setMentionAnchor(null);
    // Restore focus and move cursor after inserted mention
    requestAnimationFrame(() => {
      const pos = before.length + target.id.length + 2; // @id + space
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(pos, pos);
    });
  }

  // Scroll to bottom when new messages arrive (if auto-scroll enabled)
  useEffect(() => {
    if (autoScroll.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  function onScroll() {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    autoScroll.current = scrollHeight - scrollTop - clientHeight < 80;
  }

  function send() {
    const text = input.trim();
    if (!text) return;

    const msg = {
      message_id: crypto.randomUUID(),
      from_id:    "engineer",
      to:         "broadcast",
      content:    text,
      type:       "chat" as const,
      timestamp:  new Date().toISOString(),
    };

    // Optimistically push to local store
    useMessagesStore.getState().push(msg);

    // Send via WS to CC comm hub (which routes @mentions, etc.)
    sendWsMessage(msg);

    setInput("");
    autoScroll.current = true;
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (mentionAnchor && mentionTargets.length > 0) {
      if (e.key === "ArrowDown") { e.preventDefault(); setMenuIndex((i) => (i + 1) % mentionTargets.length); return; }
      if (e.key === "ArrowUp")   { e.preventDefault(); setMenuIndex((i) => (i - 1 + mentionTargets.length) % mentionTargets.length); return; }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); applyMention(mentionTargets[menuIndex]); return; }
      if (e.key === "Escape")    { e.preventDefault(); setMentionAnchor(null); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setInput(e.target.value);
    detectMention(e.target.value, e.target.selectionStart ?? e.target.value.length);
  }

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <MessageSquare className="w-3 h-3" />
        Comms Feed
        <span className="ml-auto text-[10px]">{messages.length}</span>
      </div>

      {/* Message list */}
      <div
        ref={listRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5"
      >
        {messages.length === 0 && (
          <div className="text-[10px] text-muted-foreground font-mono text-center py-8">
            — awaiting comms —
          </div>
        )}
        {messages.map((msg) => (
          <MessageRow key={msg.message_id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border p-2 flex gap-2 relative">

        {/* @ mention picker */}
        {mentionAnchor && mentionTargets.length > 0 && (
          <div className="absolute bottom-full left-2 mb-1 bg-card border border-border rounded shadow-lg overflow-hidden z-50 min-w-[160px]">
            {mentionTargets.map((t, i) => {
              const color  = AGENT_COLORS[t.id] ?? "#5A6A7E";
              const status = agents[t.id]?.status ?? "offline";
              const isOnline = status !== "offline";
              return (
                <button
                  key={t.id}
                  onMouseDown={(e) => { e.preventDefault(); applyMention(t); }}
                  onMouseEnter={() => setMenuIndex(i)}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-left transition-colors ${
                    i === menuIndex ? "bg-primary/10" : "hover:bg-secondary/50"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: isOnline ? color : "#3A4A5E" }} />
                  <span className="font-mono text-xs font-bold" style={{ color }}>{t.label}</span>
                  <span className="font-mono text-[10px] text-muted-foreground ml-auto">{status}</span>
                </button>
              );
            })}
          </div>
        )}

        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          placeholder="@commander what did recon find?"
          className="flex-1 bg-input border border-border rounded px-3 py-1.5 text-xs font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-colors"
        />
        <button
          onClick={send}
          disabled={!input.trim()}
          className="flex items-center gap-1 px-3 py-1.5 bg-primary/10 border border-primary/30 text-primary rounded text-xs font-mono hover:bg-primary/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="w-3 h-3" />
          SEND
        </button>
      </div>
    </div>
  );
}
