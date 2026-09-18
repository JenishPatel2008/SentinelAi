import { useEffect, useState } from "react";
import { API_BASE_URL, getAuthToken } from "../services/api";

let socket = null;
let reconnectTimer = null;
let lastMessage = null;
let connected = false;
const subscribers = new Set();

function publish(nextMessage = lastMessage) {
  lastMessage = nextMessage;
  subscribers.forEach((setState) => setState({ message: lastMessage, connected }));
}

function scheduleReconnect() {
  if (reconnectTimer || subscribers.size === 0) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    openSocket();
  }, 3000);
}

function openSocket() {
  if (socket || subscribers.size === 0) return;
  const token = getAuthToken();
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  socket = new WebSocket(`${wsBase}/ws?token=${encodeURIComponent(token || "")}`);
  socket.onopen = () => {
    connected = true;
    publish();
  };
  socket.onmessage = (event) => {
    try {
      publish(JSON.parse(event.data));
    } catch {
      // Ignore malformed messages without interrupting the shared connection.
    }
  };
  socket.onclose = () => {
    socket = null;
    connected = false;
    publish();
    scheduleReconnect();
  };
  socket.onerror = () => socket?.close();
}

export default function useWebSocket() {
  const [state, setState] = useState({ message: lastMessage, connected });

  useEffect(() => {
    subscribers.add(setState);
    openSocket();
    return () => {
      subscribers.delete(setState);
      if (subscribers.size === 0) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
        socket?.close();
        socket = null;
        connected = false;
      }
    };
  }, []);

  return state;
}
