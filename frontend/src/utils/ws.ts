import type { WSStatus, WSClientConfig } from "../types/wsTypes";

type MessageHandler = (data: any) => void;
type StatusListener = (status: WSStatus) => void;

export abstract class BaseWSClient {
  protected ws: WebSocket | null = null;
  protected status: WSStatus = "idle";
  protected url: string;

  // listeners for messages and status changes
  protected messageHandlers: MessageHandler[] = [];
  protected statusListeners: StatusListener[] = [];

  // reconnect stuff
  protected maxReconnectAttempts: number = 5;
  protected initialReconnectDelay: number = 3000;
  protected maxReconnectDelay: number = 30000;
  protected currentReconnectDelay: number = 3000;
  protected reconnectAttempts: number = 0;

  // heartbeat stuff
  protected heartbeatInterval: number = 30000;
  protected heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  constructor(url: string, config: WSClientConfig = {}) {
    // TODO: Initialize configuration from config object with defaults
    this.url = url;
    this.maxReconnectAttempts =
      config.maxReconnectAttempts ?? this.maxReconnectAttempts;
    this.initialReconnectDelay =
      config.initialReconnectDelay ?? this.initialReconnectDelay;
    this.maxReconnectDelay = config.maxReconnectDelay ?? this.maxReconnectDelay;
    this.heartbeatInterval = config.heartbeatInterval ?? this.heartbeatInterval;
    this.currentReconnectDelay = this.initialReconnectDelay;
  }

  async connect(): Promise<void> {
    this.manuallyClosed = false;

    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    // If a reconnect was scheduled, we’re taking control now.
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.setStatus("connecting");

    try {
      this.ws = new WebSocket(this.url);

      return new Promise<void>((resolve, reject) => {
        if (!this.ws) {
          reject(new Error("WebSocket is not initialized"));
          return;
        }
        this.setupEventListeners(resolve, reject);
      });
    } catch (err) {
      this.setStatus("error");
      console.error("WebSocket connection error:", err);
      throw err;
    }
  }

  protected abstract handleMessage(data: any): void;

  send(data: object): boolean {
    if (!this.ws) return false;
    if (this.ws.readyState !== WebSocket.OPEN) return false;

    try {
      this.ws.send(JSON.stringify(data));
      return true;
    } catch {
      this.setStatus("error");
      return false;
    }
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.push(handler);

    return () => {
      const idx = this.messageHandlers.indexOf(handler);
      if (idx >= 0) this.messageHandlers.splice(idx, 1);
    };
  }

  onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.push(listener);

    return () => {
      const idx = this.statusListeners.indexOf(listener);
      if (idx >= 0) this.statusListeners.splice(idx, 1);
    };
  }

  disconnect(): void {
    this.manuallyClosed = true;

    // cancel pending reconnect attempt
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopHeartbeat();

    if (this.ws) {
      // remove event handlers so we don't trigger reconnect
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;

      try {
        this.ws.close(1000, "Client disconnect");
      } catch {
        // ignore errors on close
      }
    }

    this.ws = null;
    this.setStatus("closed");
  }

  getStatus(): WSStatus {
    return this.status;
  }

  isConnected(): boolean {
    return this.status === "open" && this.ws?.readyState === WebSocket.OPEN;
  }
  // ============ Private/Protected helper methods ============

  protected setStatus(newStatus: WSStatus): void {
    if (this.status === newStatus) return;

    this.status = newStatus;
    for (const listener of this.statusListeners) {
      try {
        listener(newStatus);
      } catch {
        // listener bugs shouldn't break the WS client
      }
    }
  }

  protected startHeartbeat(): void {
    this.stopHeartbeat();

    this.heartbeatTimer = setInterval(() => {
      if (!this.isConnected()) return;

      // Convention: ping. Your server may expect a different format.
      this.send({ type: "ping", ts: Date.now() });
    }, this.heartbeatInterval);
  }

  protected stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
  // Reconnect timer + manual disconnect guard
  protected reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  protected manuallyClosed: boolean = false;

  protected attemptReconnect(): void {
    if (this.manuallyClosed) return;

    // Don’t schedule multiple timers
    if (this.reconnectTimer) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error(
        `WebSocket: max reconnect attempts reached (${this.maxReconnectAttempts}). Giving up.`
      );
      return;
    }

    this.reconnectAttempts += 1;

    const delay = this.currentReconnectDelay;
    console.warn(
      `WebSocket: reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`
    );

    this.setStatus("connecting");

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.manuallyClosed) return;

      this.connect().catch((err) => {
        console.warn("WebSocket: reconnect failed:", err);

        this.ws = null;
        this.setStatus("closed");

        // try again (will schedule a new timer)
        this.attemptReconnect();
      });
    }, delay);

    this.currentReconnectDelay = Math.min(
      this.currentReconnectDelay * 2,
      this.maxReconnectDelay
    );
  }

  protected setupEventListeners(
    resolve?: () => void,
    reject?: (err: Error) => void
  ): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.currentReconnectDelay = this.initialReconnectDelay;

      this.setStatus("open");
      this.startHeartbeat();

      resolve?.();
    };

    this.ws.onmessage = (ev: MessageEvent) => {
      let payload: any = ev.data;

      if (typeof ev.data === "string") {
        try {
          payload = JSON.parse(ev.data);
        } catch {
          // leave as string
        }
      }

      // Basic ping handling hook (server-dependent)
      if (payload && typeof payload === "object" && payload.type === "ping") {
        this.handlePing();
        return;
      }

      this.handleMessage(payload);
      for (const h of this.messageHandlers) h(payload);
    };

    this.ws.onerror = () => {
      // Browser doesn’t provide much detail. Still, don’t leave connect() hanging.
      this.setStatus("error");

      if (this.status === "connecting") {
        reject?.(new Error("WebSocket error while connecting"));
      }
    };

    this.ws.onclose = () => {
      const wasConnecting = this.status === "connecting";

      this.stopHeartbeat();
      this.setStatus("closed");

      if (wasConnecting) {
        reject?.(
          new Error("WebSocket closed before connection was established")
        );
        return;
      }

      this.ws = null;

      if (!this.manuallyClosed) {
        this.attemptReconnect();
      }
    };
  }

  // pong
  protected handlePing(): void {
    this.send({ type: "pong", ts: Date.now() });
  }
}
