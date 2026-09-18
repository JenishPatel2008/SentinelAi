import { useEffect, useRef, useState } from "react";
import { createZone, deleteZone, getStreamPreviewUrl, getZones, setZoneEnabled, updateZone } from "../../services/api";

const types = ["restricted", "high_security", "vehicle_restricted", "monitoring"];

export default function ZoneEditor({ cameras, cameraId: activeCameraId, onCameraChange, previewActive = false }) {
  const [cameraId, setCameraId] = useState(cameras[0]?.id || "");
  const [zones, setZones] = useState([]);
  const [points, setPoints] = useState([]);
  const [name, setName] = useState("");
  const [zoneType, setZoneType] = useState(types[0]);
  const [securityMode, setSecurityMode] = useState("MONITORED");
  const [message, setMessage] = useState("");
  const [previewAttempt, setPreviewAttempt] = useState(0);
  const [previewState, setPreviewState] = useState("connecting");
  const retryTimer = useRef(null);
  const selectedCameraId = activeCameraId || cameraId;

  useEffect(() => {
    if (!selectedCameraId) return;
    getZones(selectedCameraId)
      .then(setZones)
      .catch((error) => { setZones([]); setMessage(error.message); });
  }, [selectedCameraId]);

  useEffect(() => {
    // Reset the preview retry state when the camera or stream state changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewAttempt(0);
    setPreviewState("connecting");
    return () => clearTimeout(retryTimer.current);
  }, [selectedCameraId, previewActive]);

  function reconnectPreview() {
    setPreviewState("reconnecting");
    clearTimeout(retryTimer.current);
    retryTimer.current = setTimeout(() => {
      setPreviewAttempt((current) => current + 1);
      setPreviewState("connecting");
    }, 1800);
  }

  function addPoint(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    setPoints((current) => [...current, { x: Number(((event.clientX - bounds.left) / bounds.width).toFixed(4)), y: Number(((event.clientY - bounds.top) / bounds.height).toFixed(4)) }]);
  }

  async function saveZone() {
    if (!selectedCameraId || points.length < 3 || !name.trim()) { setMessage("Choose a camera, add at least three points, and name the zone."); return; }
    try {
      const saved = await createZone(selectedCameraId, { name: name.trim(), zone_type: zoneType, security_mode: securityMode, trusted_person_policy: securityMode === "PROTECTED" ? "ONLY_TRUSTED" : "NO_SPECIAL_POLICY", polygon_points: points, enabled: true });
      setZones((current) => [...current, saved]); setPoints([]); setName(""); setMessage("Zone saved");
    } catch (error) { setMessage(error.message); }
  }

  async function removeZone(id) { try { await deleteZone(id); setZones((current) => current.filter((zone) => zone.id !== id)); } catch (error) { setMessage(error.message); } }
  async function toggleZone(zone) { try { const updated = await setZoneEnabled(zone.id, !zone.enabled); setZones((current) => current.map((item) => item.id === zone.id ? updated : item)); } catch (error) { setMessage(error.message); } }
  async function changeSecurityMode(zone, value) { try { const updated = await updateZone(zone.id, { security_mode: value, trusted_person_policy: value === "PROTECTED" ? "ONLY_TRUSTED" : "NO_SPECIAL_POLICY" }); setZones((current) => current.map((item) => item.id === zone.id ? updated : item)); } catch (error) { setMessage(error.message); } }
  function changeCamera(value) { setPoints([]); setCameraId(value); onCameraChange?.(value); }

  const selected = cameras.find((camera) => camera.id === Number(selectedCameraId));
  return <section className="zone-editor panel"><div className="section-title"><div><h2>Configure Surveillance Zones</h2><small>Draw normalized polygons for the selected camera.</small></div><span className="tag blue">{zones.length} ZONES</span></div><div className="zone-controls"><select value={selectedCameraId} onChange={(event) => changeCamera(event.target.value)}>{cameras.map((camera) => <option value={camera.id} key={camera.id}>{camera.camera_code} - {camera.name}</option>)}</select><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Zone name" /><select value={zoneType} onChange={(event) => setZoneType(event.target.value)}>{types.map((type) => <option key={type} value={type}>{type.replace("_", " ")}</option>)}</select><select value={securityMode} onChange={(event) => setSecurityMode(event.target.value)}><option value="OPEN">Open</option><option value="MONITORED">Monitored</option><option value="PROTECTED">Protected: trusted only</option></select><button onClick={() => setPoints([])}>Clear Polygon</button><button className="primary" onClick={saveZone}>Save Zone</button></div><div className="zone-canvas" onClick={addPoint}><div className="zone-frame">{previewActive && selected ? <><img className="zone-preview" src={getStreamPreviewUrl(selected.id, previewAttempt)} alt={`${selected.camera_code} live preview`} onLoad={() => setPreviewState("live")} onError={reconnectPreview} />{previewState !== "live" && <span className="zone-preview-state">{previewState === "reconnecting" ? "RECONNECTING LIVE FEED" : "CONNECTING LIVE FEED"}</span>}</> : selected?.stream_url || "Start the camera stream to preview this source"}<svg viewBox="0 0 1 1" preserveAspectRatio="none">{zones.map((zone) => <polygon key={zone.id} points={zone.polygon_points.map((point) => `${point.x},${point.y}`).join(" ")} className={zone.enabled ? "zone-polygon" : "zone-polygon disabled"} />)}{points.length > 1 && <polyline points={points.map((point) => `${point.x},${point.y}`).join(" ")} className="drawing-line" />}{points.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r=".012" className="drawing-point" />)}</svg></div></div><div className="zone-list">{zones.map((zone) => <div className="zone-list-item" key={zone.id}><span><b>{zone.name}</b><small>{zone.zone_type} | {zone.security_mode || "MONITORED"}</small></span><select value={zone.security_mode || "MONITORED"} onChange={(event) => changeSecurityMode(zone, event.target.value)}><option value="OPEN">Open</option><option value="MONITORED">Monitored</option><option value="PROTECTED">Protected</option></select><button onClick={() => toggleZone(zone)}>{zone.enabled ? "Disable" : "Enable"}</button><button onClick={() => removeZone(zone.id)}>Delete</button></div>)}</div>{message && <small className="zone-message">{message}</small>}</section>;
}
