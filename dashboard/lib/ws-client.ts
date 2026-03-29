/**
 * WebSocket client — singleton that connects to the Command Center.
 * Dispatches incoming events to the correct Zustand stores.
 *
 * Usage: call `initWs(token)` once on mount. The singleton reconnects
 * automatically on disconnect.
 */
import { useMissionStore }  from "@/store/mission";
import { useAgentsStore }   from "@/store/agents";
import { useMessagesStore } from "@/store/messages";
import { useFindingsStore } from "@/store/findings";
import { useHitlStore }     from "@/store/hitl";
import { useTerminalStore } from "@/store/terminal";
import { useCoverageStore } from "@/store/coverage";
import { useActivityStore } from "@/store/activity";

// CC WebSocket URL — falls back to localhost for dev
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8001/ws";

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_DELAY = 30_000;

let socket:         WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay  = RECONNECT_DELAY_MS;
let authToken:      string | null = null;
let destroyed       = false;

function dispatch(event: Record<string, unknown>) {
  const type = event.type as string;

  if (type === "mission.state" || type === "mission.snapshot") {
    useMissionStore.getState().applySnapshot(event as never);
    return;
  }

  if (type === "mission.metric") {
    const { field, value } = event as { field: string; value: unknown };
    useMissionStore.getState().setMetric(field as never, value);
    return;
  }

  if (type === "agent.status" || type === "agent.health") {
    const { agent_id, status } = event as { agent_id: string; status: string };
    if (agent_id) useAgentsStore.getState().upsert({ agent_id, status: status as never });
    return;
  }

  if (type === "agent.registered") {
    const { agent_id, status } = event as { agent_id: string; status?: string };
    if (agent_id) useAgentsStore.getState().upsert({ agent_id, status: (status ?? "online") as never });
    return;
  }

  if (type === "agent.heartbeat") {
    const { agent_id } = event as { agent_id: string };
    if (agent_id) useAgentsStore.getState().heartbeat(agent_id);
    return;
  }

  // Comms feed — Commander ↔ Engineer dialogue only
  if (type === "human.message") {
    useMessagesStore.getState().push({
      message_id: (event.message_id as string) ?? crypto.randomUUID(),
      from_id:    (event.from_id as string) ?? "engineer",
      to:         (event.to as string) ?? "commander",
      content:    (event.content as string) ?? "",
      type:       "chat",
      timestamp:  (event.timestamp as string) ?? new Date().toISOString(),
    });
    return;
  }

  if (type === "agent.message") {
    const fromId = (event.from_id as string) ?? "";
    // Only Commander replies belong in the Comms feed — agent raw output goes to Activity
    if (fromId === "commander") {
      useMessagesStore.getState().push({
        message_id: (event.message_id as string) ?? crypto.randomUUID(),
        from_id:    fromId,
        to:         (event.to as string) ?? "engineer",
        content:    (event.content as string) ?? "",
        type:       "chat",
        timestamp:  (event.timestamp as string) ?? new Date().toISOString(),
      });
    }
    return;
  }

  if (type === "fix.ready") {
    const { finding_id } = event as { finding_id: string };
    if (finding_id) useFindingsStore.getState().markFixReady(finding_id);
    return;
  }

  if (type === "activity.event") {
    useActivityStore.getState().push({
      id:        (event.id as string) ?? crypto.randomUUID(),
      direction: (event.direction as "inbound" | "outbound") ?? "inbound",
      actor:     (event.actor as string) ?? "unknown",
      summary:   (event.summary as string) ?? "",
      timestamp: (event.timestamp as string) ?? new Date().toISOString(),
    });
    return;
  }

  if (type === "agent.finding" || type === "vulnerability_finding") {
    const technique = event.technique as string | undefined;
    useFindingsStore.getState().push({
      finding_id:  (event.finding_id as string)  ?? (event.event_id as string) ?? crypto.randomUUID(),
      agent_id:    (event.agent_id  as string)   ?? "unknown",
      host:        (event.host      as string)   ?? "",
      title:       (event.title     as string)   ?? (event.event_type as string) ?? "Finding",
      severity:    (event.severity  as never)    ?? "medium",
      cve:         event.cve        as string    | undefined,
      technique,
      description: (event.description as string) ?? "",
      timestamp:   (event.timestamp as string)   ?? new Date().toISOString(),
      remediated:  false,
      fix_ready:   false,
    });
    // Exploit findings = attempted, detect-agent findings = detected
    if (technique && technique !== "T0000") {
      const agentId = (event.agent_id as string) ?? "";
      const state = agentId.includes("detect") ? "detected" : "attempted";
      useCoverageStore.getState().mark(technique, state);
    }
    return;
  }

  if (type === "hitl.request") {
    useHitlStore.getState().push({
      hitl_id:          (event.hitl_id          as string) ?? crypto.randomUUID(),
      requesting_agent: (event.requesting_agent as string) ?? "unknown",
      action:           (event.action           as string) ?? "",
      target:           (event.target           as string) ?? "",
      risk_level:       (event.risk_level       as string) ?? "HIGH",
      context:          (event.context          as string) ?? "",
      proposed_command: event.proposed_command  as string | undefined,
      created_at:       (event.created_at       as string) ?? new Date().toISOString(),
    });
    useMissionStore.getState().setMetric("pending_hitl_requests" as never,
      useHitlStore.getState().queue.length);
    return;
  }

  if (type === "hitl.resolved") {
    const { hitl_id } = event as { hitl_id: string };
    if (hitl_id) {
      useHitlStore.getState().remove(hitl_id);
      useMissionStore.getState().setMetric("pending_hitl_requests" as never,
        useHitlStore.getState().queue.length);
    }
    return;
  }

  if (type === "agent.command_result" || type === "command_execution") {
    useTerminalStore.getState().push({
      id:        (event.event_id  as string) ?? crypto.randomUUID(),
      agent_id:  (event.agent_id  as string) ?? "system",
      command:   event.command    as string  | undefined,
      output:    (event.output    as string) ?? (event.stdout as string) ?? "",
      exit_code: event.exit_code  as number  | undefined,
      timestamp: (event.timestamp as string) ?? new Date().toISOString(),
    });
    // Mark technique coverage from execution events
    const tech = event.technique as string | undefined;
    if (tech && tech !== "T0000") {
      useCoverageStore.getState().mark(tech, "attempted");
    }
    return;
  }

  if (type === "patch_deployed") {
    const tech = event.technique as string | undefined;
    if (tech && tech !== "T0000") {
      useCoverageStore.getState().mark(tech, "remediated");
    }
    return;
  }

  if (type === "detection_score") {
    const tech = event.technique as string | undefined;
    if (tech && tech !== "T0000") {
      useCoverageStore.getState().mark(tech, "detected");
    }
    return;
  }

  // Unknown events are silently dropped — no generic fallback to Comms feed
}

function connect() {
  if (destroyed) return;

  const url = authToken ? `${WS_URL}?token=${authToken}` : WS_URL;
  socket = new WebSocket(url);

  socket.onopen = () => {
    useMissionStore.getState().setConnected(true);
    reconnectDelay = RECONNECT_DELAY_MS; // reset backoff
  };

  socket.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data as string) as Record<string, unknown>;
      dispatch(data);
    } catch {
      // ignore malformed frames
    }
  };

  socket.onclose = () => {
    useMissionStore.getState().setConnected(false);
    scheduleReconnect();
  };

  socket.onerror = () => {
    socket?.close();
  };
}

function scheduleReconnect() {
  if (destroyed) return;
  reconnectTimer = setTimeout(() => {
    reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY);
    connect();
  }, reconnectDelay);
}

/** Send a message through the WebSocket (engineer → CC). */
export function sendWsMessage(payload: Record<string, unknown>) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}

/** Boot the singleton connection. Call once from a client component. */
export function initWs(token?: string | null) {
  if (socket) return; // already initialised
  destroyed = false;
  authToken = token ?? null;
  connect();
}

/** Tear down on logout / unmount. */
export function destroyWs() {
  destroyed = true;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  socket?.close();
  socket = null;
  useMissionStore.getState().setConnected(false);
}
