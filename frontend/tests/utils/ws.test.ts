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
  onclose: ((ev?: { code: number }) => void) | null = null;

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

describe("BaseWSClient reconnect", () => {
  /**
   * Open the client and hand back the socket it built, ready to be closed on.
   *
   * Real timers here on purpose: connect() defers `new WebSocket` by one task
   * (the WebKit fix above), so a fake clock installed before this point stops
   * the socket from ever being created. The fake clock goes in afterwards,
   * where the reconnect backoff is what needs controlling.
   */
  async function openClient() {
    const client = new TestClient("wss://example.test/ws/game/ABC123/");
    const connected = client.connect();
    await nextTask();
    const socket = FakeWebSocket.instances[0];
    socket.readyState = FakeWebSocket.OPEN;
    socket.onopen?.();
    await connected;
    return { client, socket };
  }

  afterEach(() => {
    vi.useRealTimers();
  });

  // The consumers close with 4403 when the seat is not ours any more: the host
  // took it over, someone redeemed a transfer code, or the player was removed.
  // Retrying asks a server that has already decided, five times over.
  it("does not reconnect after an application close code", async () => {
    const { client, socket } = await openClient();
    vi.useFakeTimers();

    socket.onclose?.({ code: 4403 });
    await vi.advanceTimersByTimeAsync(30_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(client.getStatus()).toBe("closed");

    client.disconnect();
  });

  // A dropped connection is the case that matters on a school wifi, and it has
  // to keep working.
  it("reconnects after a transport-level close", async () => {
    const { client, socket } = await openClient();
    vi.useFakeTimers();

    socket.onclose?.({ code: 1006 });
    await vi.advanceTimersByTimeAsync(10_000);

    expect(FakeWebSocket.instances.length).toBeGreaterThan(1);

    client.disconnect();
  });
});
