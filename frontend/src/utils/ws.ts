export type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";
import { type WSOptions } from "../types";

export class WSClient {
  private ws: WebSocket | null = null;
  private status: WSStatus = "idle";
  private opts: WSOptions;

  constructor(url: string, opts: WSOptions = {}) {
    this.opts = opts;
    this.connect(url);
  }

  private connect(url: string) {
    this.status = "connecting";
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.status = "open";
      this.opts.onOpen?.();
    };

    ws.onclose = (ev) => {
      this.status = "closed";
      this.opts.onClose?.(ev);
    };

    ws.onerror = (ev) => {
      this.status = "error";
      this.opts.onError?.(ev);
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        this.opts.onMessage?.(data);
      } catch {
        console.error("Failed to parse WebSocket message:", ev.data);
      }
    };
  }

  send(data: unknown): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.ws.send(JSON.stringify(data));
    return true;
  }

  close() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.status = "closed";
    }
  }

  getStatus(): WSStatus {
    return this.status;
  }
}
