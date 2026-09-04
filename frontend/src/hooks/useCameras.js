import { useCallback, useEffect, useState } from "react";
import { getCameras } from "../services/api";

export default function useCameras() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadCameras = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await getCameras();

      setCameras(Array.isArray(data) ? data : data.cameras || []);
    } catch (err) {
      console.error("Failed to load cameras:", err);
      setError(err.message || "Failed to load cameras");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch camera data when the dashboard mounts.
    // This is intentionally a state update caused by an external API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCameras();
  }, [loadCameras]);

  return {
    cameras,
    loading,
    error,
    reload: loadCameras,
  };
}
