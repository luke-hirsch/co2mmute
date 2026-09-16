import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BaseWSClient } from "@/utils/ws";

/** Records every socket the client constructs; never touches the network. */
class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send() {}

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
}

class TestClient extends BaseWSClient {
  protected handleMessage() {}
}

/** Lets the client's deferred socket creation run. */
const nextTask = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BaseWSClient.connect", () => {
  // WebKit stalls a fetch sent in the same task as a new WebSocket, which
  // left the host lobby on its loading screen in Safari.
  it("opens the socket one task later, not synchronously", async () => {
    const client = new TestClient("wss://example.test/ws/game/ABC123/");
    const connected = client.connect();

    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(client.getStatus()).toBe("connecting");

    await nextTask();
    expect(FakeWebSocket.instances).toHaveLength(1);

    const socket = FakeWebSocket.instances[0];
    socket.readyState = FakeWebSocket.OPEN;
    socket.onopen?.();
    await expect(connected).resolves.toBeUndefined();
    expect(client.getStatus()).toBe("open");

    client.disconnect();
  });

  it("opens nothing when disconnect() comes before the socket does", async () => {
    const client = new TestClient("wss://example.test/ws/game/ABC123/");
    const connected = client.connect();
    client.disconnect();

    await nextTask();
    await connected;

    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(client.getStatus()).toBe("closed");
  });

  it("opens one socket when connect() is called twice in the same task", async () => {
    const client = new TestClient("wss://example.test/ws/game/ABC123/");
    void client.connect();
    void client.connect();

    await nextTask();
    await nextTask();

    expect(FakeWebSocket.instances).toHaveLength(1);

    client.disconnect();
  });
});
