import { useEffect, useState } from "react";

export default function useWebSocket(url = "ws://127.0.0.1:8000/ws") {
  const [message, setMessage] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const socket = new WebSocket(url);
    socket.onopen = () => setConnected(true);
    socket.onmessage = (event) => {
      try { setMessage(JSON.parse(event.data)); } catch { setMessage(null); }
    };
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    return () => socket.close();
  }, [url]);

  return { message, connected };
}
