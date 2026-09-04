const API_BASE_URL = "http://127.0.0.1:8000";

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
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
}

export function getCameras() {
  return request("/cameras");
}

export function getCamera(id) {
  return request(`/cameras/${id}`);
}

export function createCamera(camera) {
  return request("/cameras", {
    method: "POST",
    body: JSON.stringify(camera),
  });
}

export function deleteCamera(id) {
  return request(`/cameras/${id}`, {
    method: "DELETE",
  });
}

export function getAlerts() {
  return request("/api/alerts");
}

export function getEvents() {
  return request("/api/events");
}

export function getDetections() {
  return request("/api/detections");
}

export function getAnalytics() {
  return request("/api/analytics");
}

export function startStream(cameraId) {
  return request("/api/streams/start", { method: "POST", body: JSON.stringify({ camera_id: cameraId }) });
}

export function stopStream(cameraId) {
  return request("/api/streams/stop", { method: "POST", body: JSON.stringify({ camera_id: cameraId }) });
}
