import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

export interface StreamEvent {
  type: "log" | "state" | "end";
  id?: number | null;
  level?: string;
  stage?: string | null;
  message?: string;
  created_at?: string;
  status?: string;
}

export function useExecutionStream(
  executionId: number | null,
  onEvent: (event: StreamEvent) => void,
  enabled: boolean,
): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!executionId || !enabled) {
      setConnected(false);
      return;
    }
    const source = new EventSource(api.streamUrl(executionId));
    source.onopen = () => setConnected(true);
    source.onmessage = (event) => {
      try {
        handlerRef.current(JSON.parse(event.data) as StreamEvent);
      } catch {
        // Ignore malformed SSE frames; the backend remains the source of truth.
      }
    };
    source.onerror = () => setConnected(false);
    return () => {
      source.close();
      setConnected(false);
    };
  }, [executionId, enabled]);

  return { connected };
}
