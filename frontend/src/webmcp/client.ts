/**
 * WebMCP WebSocket JSON-RPC 2.0 Client.
 * Connects to /ws/webmcp and coordinates bidirectional calls between browser and ADK.
 */

let socket: WebSocket | null = null;
let rpcIdCounter = 1;
const pendingRequests = new Map<number, { resolve: (val: any) => void; reject: (err: any) => void }>();

export function getWebSocketUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000/ws/webmcp";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host || "localhost:8000";
  return `${protocol}//${host}/ws/webmcp`;
}

export function connectWebMcp(onStateUpdate?: (state: any) => void): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const url = getWebSocketUrl();
    console.log(`[WebMCP Bridge] Connecting to WebSocket: ${url}`);
    socket = new WebSocket(url);

    socket.onopen = () => {
      console.log("[WebMCP Bridge] Connected to Python Google ADK backend.");
      // Send initialization handshake
      sendRpcRequest("initialize", {}).catch(console.error);
      resolve(socket!);
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        // Emit to WebMCP Inspector
        window.dispatchEvent(
          new CustomEvent("webmcp:jsonrpc", {
            detail: { direction: "INBOUND", message, timestamp: new Date().toISOString() },
          })
        );

        // Check if response to a pending request
        if (message.id && pendingRequests.has(message.id)) {
          const { resolve, reject } = pendingRequests.get(message.id)!;
          pendingRequests.delete(message.id);
          if (message.error) {
            reject(message.error);
          } else {
            resolve(message.result);
          }
          return;
        }

        // Handle server push notifications
        if (message.method === "state/snapshot" && onStateUpdate) {
          onStateUpdate(message.params);
          window.dispatchEvent(new CustomEvent("webmcp:state", { detail: message.params }));
        }

        if (message.method === "audit/event") {
          window.dispatchEvent(new CustomEvent("webmcp:auditLogged", { detail: message.params }));
        }
      } catch (err) {
        console.error("[WebMCP Bridge] Failed to parse message:", err);
      }
    };

    socket.onerror = (err) => {
      console.error("[WebMCP Bridge] WebSocket error:", err);
      reject(err);
    };

    socket.onclose = () => {
      console.warn("[WebMCP Bridge] Disconnected. Reconnecting in 3s...");
      setTimeout(() => connectWebMcp(onStateUpdate), 3000);
    };
  });
}

export function sendRpcRequest<T = any>(method: string, params: any = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      reject(new Error("WebMCP WebSocket bridge is not connected."));
      return;
    }

    const id = rpcIdCounter++;
    const payload = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    pendingRequests.set(id, { resolve, reject });

    // Emit to WebMCP Inspector
    window.dispatchEvent(
      new CustomEvent("webmcp:jsonrpc", {
        detail: { direction: "OUTBOUND", message: payload, timestamp: new Date().toISOString() },
      })
    );

    socket.send(JSON.stringify(payload));
  });
}
