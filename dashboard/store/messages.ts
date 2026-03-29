import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ChatMessage {
  message_id: string;
  from_id:    string;
  to:         string | string[];
  content:    string;
  type:       "chat" | "broadcast" | "a2a" | "system";
  timestamp:  string;
}

const MAX_MESSAGES = 500;

interface MessagesStore {
  messages:   ChatMessage[];
  sessionId:  string;
  push:       (msg: ChatMessage) => void;
  clear:      () => void;
  newSession: () => void;
}

function generateSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const useMessagesStore = create<MessagesStore>()(
  persist(
    (set) => ({
      messages:   [],
      sessionId:  generateSessionId(),

      push: (msg) =>
        set((s) => {
          if (s.messages.some((m) => m.message_id === msg.message_id)) return s;
          const next = [...s.messages, msg];
          return { messages: next.length > MAX_MESSAGES ? next.slice(-MAX_MESSAGES) : next };
        }),

      clear: () => set({ messages: [] }),

      newSession: () => set({ messages: [], sessionId: generateSessionId() }),
    }),
    {
      name:    "secunet-messages",
      version: 1,
    }
  )
);
