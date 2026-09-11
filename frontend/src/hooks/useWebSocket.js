import { useEffect, useRef, useState } from "react";
import { getAuthToken } from "../services/api";

export default function useWebSocket() {
  const [message, setMessage] = useState(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);

  useEffect(() => {
    let disposed = false;
    let socket;
    const connect = () => {
      const token = getAuthToken();
      const url = `ws://127.0.0.1:8000/ws?token=${encodeURIComponent(token || "")}`;
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
  }, []);

  return { message, connected };
}
