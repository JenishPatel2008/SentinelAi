export const API_BASE_URL = "http://127.0.0.1:8000";
export const AUTH_TOKEN_KEY = "sentinel.operator.token";
const REQUEST_TIMEOUT_MS = 15000;

export function getAuthToken() {
  return typeof window === "undefined" ? null : window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getStreamPreviewUrl(cameraId, attempt = 0) {
  const token = getAuthToken();
  const query = new URLSearchParams({ attempt: String(attempt) });
  if (token) query.set("token", token);
  return `${API_BASE_URL}/api/streams/${cameraId}/mjpeg?${query.toString()}`;
}

async function request(endpoint, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      let message = `Request failed with status ${response.status}`;

      try {
        const data = await response.json();

        if (data.detail) {
          message = data.detail;
        }
      } catch {
        // Response wasn't JSON.
      }

      throw new Error(message);
    }

    return response.json();
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`Request timed out while contacting ${endpoint}.`, { cause: error });
    }

    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export function getCameras() {
  return request("/api/cameras");
}

export function getCamera(id) {
  return request(`/api/cameras/${id}`);
}

export function createCamera(camera) {
  return request("/api/cameras", {
    method: "POST",
    body: JSON.stringify(camera),
  });
}

export function deleteCamera(id) {
  return request(`/api/cameras/${id}`, {
    method: "DELETE",
  });
}

export function testRtspConnection(streamUrl) {
  return request("/api/cameras/test-rtsp", {
    method: "POST",
    body: JSON.stringify({ stream_url: streamUrl }),
  });
}

export function updateCamera(id, camera) {
  return request(`/api/cameras/${id}`, { method: "PUT", body: JSON.stringify(camera) });
}

export async function uploadVideo(file) {
  const body = new FormData();
  body.append("file", file);
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/cameras/upload-video`, { method: "POST", body, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) {
    let message = `Video upload failed with status ${response.status}`;
    try { const data = await response.json(); if (data.detail) message = data.detail; } catch { /* Preserve the HTTP error when the response is not JSON. */ }
    throw new Error(message);
  }
  return response.json();
}

export function getAlerts(status = "active") {
  return request(`/api/alerts?status=${encodeURIComponent(status)}`);
}

export function getAlert(id) {
  return request(`/api/alerts/${id}`);
}

export function decideAlert(id, decision) {
  return request(`/api/alerts/${id}/decision`, {
    method: "PATCH",
    body: JSON.stringify({ decision }),
  });
}

export function getEvents() {
  return request("/api/events");
}

export function getDetections() {
  return request("/api/detections");
}

export function getPlateHistory(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== "") params.set(key, value); });
  return request(`/api/plates/history${params.toString() ? `?${params.toString()}` : ""}`);
}

export function getWatchlist() {
  return request("/api/watchlist");
}

export function createWatchlistEntry(entry) {
  return request("/api/watchlist", { method: "POST", body: JSON.stringify(entry) });
}

export function updateWatchlistEntry(id, entry) {
  return request(`/api/watchlist/${id}`, { method: "PUT", body: JSON.stringify(entry) });
}

export function deleteWatchlistEntry(id) {
  return request(`/api/watchlist/${id}`, { method: "DELETE" });
}

export function getAnalytics() {
  return request("/api/analytics");
}

export function getHealth() {
  return request("/health");
}

export function getSettings() {
  return request("/api/settings");
}

export function updateSettings(settings) {
  return request("/api/settings", { method: "PATCH", body: JSON.stringify(settings) });
}

export async function getCamerasWithStatuses() {
  const cameras = await getCameras();
  return Promise.all(cameras.map(async (camera) => {
    try {
      const stream = await getStreamStatus(camera.id);
      return { ...camera, status: stream.status, stream_status: stream };
    } catch {
      return camera;
    }
  }));
}

export async function loginOperator(username, password) {
  const result = await request("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
  window.localStorage.setItem(AUTH_TOKEN_KEY, result.access_token);
  return result;
}

export function getCurrentUser() {
  return request("/api/auth/me");
}

export function logoutOperator() {
  if (typeof window !== "undefined") window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function startStream(cameraId) {
  return request("/api/streams/start", { method: "POST", body: JSON.stringify({ camera_id: cameraId }) });
}

export function stopStream(cameraId) {
  return request("/api/streams/stop", { method: "POST", body: JSON.stringify({ camera_id: cameraId }) });
}

export function getStreamStatus(cameraId) {
  return request(`/api/streams/${cameraId}/status`);
}

export function getZones(cameraId) { return request(`/api/cameras/${cameraId}/zones`); }
export function createZone(cameraId, zone) { return request(`/api/cameras/${cameraId}/zones`, { method: "POST", body: JSON.stringify(zone) }); }
export function updateZone(zoneId, zone) { return request(`/api/zones/${zoneId}`, { method: "PUT", body: JSON.stringify(zone) }); }
export function deleteZone(zoneId) { return request(`/api/zones/${zoneId}`, { method: "DELETE" }); }
export function setZoneEnabled(zoneId, enabled) { return request(`/api/zones/${zoneId}/enabled?enabled=${enabled}`, { method: "PATCH" }); }
