import { useCallback, useEffect, useState } from "react";
import { getAlerts } from "../services/api";
import useWebSocket from "./useWebSocket";

export default function useAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState(null);
  const { message, connected } = useWebSocket();
  const reload = useCallback(async () => {
    try { setAlerts(await getAlerts()); setError(null); }
    catch (err) { setError(err.message || "Unable to load alerts"); }
  }, []);
  // Fetch once when the hook mounts; the request is an external side effect.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { reload(); }, [reload]);
  useEffect(() => {
    // WebSocket messages arrive asynchronously and update the local alert feed.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (message?.type === "alert" && message.data) setAlerts((current) => [message.data, ...current]);
  }, [message]);
  return { alerts, error, connected, reload };
}
