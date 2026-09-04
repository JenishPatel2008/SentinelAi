import { useEffect, useRef, useState } from "react";

export default function useWebSocket(url = "ws://127.0.0.1:8000/ws") {
  const [message, setMessage] = useState(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);

  useEffect(() => {
    let disposed = false;
    let socket;
    const connect = () => {
      socket = new WebSocket(url);
      socket.onopen = () => { if (!disposed) setConnected(true); };
      socket.onmessage = (event) => { try { setMessage(JSON.parse(event.data)); } catch { /* Ignore malformed messages. */ } };
      socket.onclose = () => {
        if (disposed) return;
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 3000);
      };
      socket.onerror = () => socket.close();
    };
    connect();
    return () => { disposed = true; clearTimeout(reconnectTimer.current); socket?.close(); };
  }, [url]);

  return { message, connected };
}
