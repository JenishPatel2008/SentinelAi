import { Component, useEffect, useRef, useState } from "react";
import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Activity, AlertTriangle, BarChart3, Bell, Camera, ChevronDown, HelpCircle, LayoutDashboard, LogOut, Map, Search, Settings, Shield, Video } from "lucide-react";
import { API_BASE_URL, createCamera, decideAlert, deleteCamera, getAlert, getAlerts, getAnalytics, getCameras, getCamerasWithStatuses, getCurrentUser, getDetections, getEvents, getHealth, getPlateHistory, getSettings, getStreamPreviewUrl, getStreamStatus, loginOperator, logoutOperator, startStream, stopStream, testRtspConnection, updateCamera, updateSettings, uploadVideo } from "./services/api";
import "./App.css";
import ZoneEditor from "./components/zones/ZoneEditor";
import useWebSocket from "./hooks/useWebSocket";

const nav = [["Dashboard", "/dashboard", LayoutDashboard], ["Live Monitoring", "/monitoring", Video], ["Alerts", "/alerts", Bell], ["Analytics", "/analytics", BarChart3], ["Archive", "/events", Activity], ["Plate History", "/plate-history", Search], ["Cameras", "/cameras", Camera], ["Border Map", "/border-map", Map], ["Settings", "/settings", Settings]];
const asArray = (value) => { if (!Array.isArray(value)) throw new Error("Unexpected list response from the surveillance backend."); return value; };
const asObject = (value) => { if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("Unexpected analytics response from the surveillance backend."); return value; };
const MANUAL_STOPS_KEY = "sentinel.manual-stopped-cameras";

function getManualStops() {
  try { return new Set(JSON.parse(window.sessionStorage.getItem(MANUAL_STOPS_KEY) || "[]").map(Number)); } catch { return new Set(); }
}

function setManualStop(cameraId, stopped) {
  const stops = getManualStops();
  if (stopped) stops.add(Number(cameraId)); else stops.delete(Number(cameraId));
  window.sessionStorage.setItem(MANUAL_STOPS_KEY, JSON.stringify([...stops]));
}

function cameraStatus(camera) {
  return camera?.status || (camera?.is_active ? "online" : "offline");
}

function loadCameraRecords() {
  return getCamerasWithStatuses();
}

function useRemote(loader, initial, normalize) {
  const [data, setData] = useState(initial); const [loading, setLoading] = useState(true); const [error, setError] = useState(null); const [version, setVersion] = useState(0);
  useEffect(() => { let mounted = true; loader().then(normalize).then((value) => { if (mounted) setData(value); }).catch((err) => { if (mounted) setError(err.message || "Unable to load surveillance data."); }).finally(() => { if (mounted) setLoading(false); }); return () => { mounted = false; }; }, [loader, normalize, version]);
  function reload() { setLoading(true); setError(null); setVersion((current) => current + 1); }
  return { data, loading, error, reload };
}

class RouteErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <div className="fatal-state"><AlertTriangle size={22} /><div><b>Unable to render this operational view.</b><span>Refresh the page to try again.</span></div></div> : this.props.children; }
}

function ProtectedLayout() {
  const location = useLocation();
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  useEffect(() => {
    let mounted = true;
    getCurrentUser().then(() => { if (mounted) setAuthenticated(true); }).catch(() => { if (mounted) { logoutOperator(); setAuthenticated(false); } }).finally(() => { if (mounted) setChecking(false); });
    return () => { mounted = false; };
  }, []);
  if (checking) return <div className="fatal-state">Checking operator session...</div>;
  if (!authenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <><StreamSupervisor /><AlertNotification /><Outlet /></>;
}

function Header() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  function search(event) { event.preventDefault(); navigate(query.trim() ? `/alerts?search=${encodeURIComponent(query.trim())}` : "/alerts"); }
  function logout() { logoutOperator(); navigate("/login", { replace: true }); }
  return <header className="topbar"><div className="mobile-logo">SENTINEL AI</div><div className="system-pill"><i /> SYSTEM STATUS</div><form className="header-search" onSubmit={search}><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search alerts, events..." aria-label="Search alerts and events" /><button type="submit" aria-label="Search"><Search size={14} /></button></form><div className="header-tools"><button className="header-icon" aria-label="Open settings" onClick={() => navigate("/settings")}><Settings size={19} /></button><button className="header-icon" aria-label="Open help" onClick={() => setHelpOpen((open) => !open)}><HelpCircle size={19} /></button><button className="header-icon notification" aria-label="Open alerts" onClick={() => navigate("/alerts")}><Bell size={19} /><b /></button><button className="avatar" aria-label="Open operator menu" onClick={() => setProfileOpen((open) => !open)}>OP</button><button className="header-icon" aria-label="Toggle operator menu" onClick={() => setProfileOpen((open) => !open)}><ChevronDown size={15} /></button>{profileOpen && <div className="header-menu"><strong>Operator</strong><small>Authenticated session</small><button onClick={logout}><LogOut size={15} /> Log out</button></div>}</div>{helpOpen && <aside className="header-help"><strong>Operator help</strong><p>Use Monitoring to start or stop a source, Cameras to edit registrations, and Alerts to review active incidents.</p><button onClick={() => setHelpOpen(false)}>Close</button></aside>}</header>;
}
function Sidebar() { const navigate = useNavigate(); return <aside className="sidebar"><div className="brand"><div className="brand-mark"><Shield size={22} /></div><div><strong>Sentinel AI</strong><small>Border Control Unit</small></div></div><nav>{nav.map(([label, path, Icon]) => <NavLink key={path} to={path} className={({ isActive }) => isActive ? "active" : ""}><Icon size={19} /><span>{label}</span></NavLink>)}</nav><div className="sidebar-foot"><button onClick={() => { logoutOperator(); navigate("/login", { replace: true }); }}><LogOut size={19} /><span>Log Out</span></button><small>Operator Profile</small></div></aside>; }
function Shell({ children }) { return <div className="app-shell"><Sidebar /><div className="main"><Header />{children}</div></div>; }
function PageHead({ eyebrow, title, sub, actions }) { return <div className="page-head"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</div>; }
function State({ loading, error, empty, children, reload }) { if (loading) return <div className="state"><div className="spinner" /> Loading operational data...</div>; if (error) return <div className="state error-state"><AlertTriangle size={18} /><span>{error}</span>{reload && <button className="retry-btn" onClick={reload}>Retry</button>}</div>; if (empty) return <div className="state">{empty}</div>; return children; }
function Stat({ label, value, detail, tone = "", action }) { return <div className={`stat ${tone}`}><span>{label}</span><strong>{value ?? "Unavailable"}</strong>{detail && <small>{detail}</small>}{action && <button className="retry-btn" onClick={action}>{"Retry"}</button>}</div>; }

function useStreamSupervisor(cameras) {
  const startsInFlight = useRef(new Set());

  useEffect(() => {
    let disposed = false;
    async function ensureStreams() {
      const manualStops = getManualStops();
      await Promise.all(cameras.filter((camera) => camera.is_active && camera.stream_url && !manualStops.has(Number(camera.id))).map(async (camera) => {
        if (startsInFlight.current.has(camera.id)) return;
        try {
          const status = await getStreamStatus(camera.id);
          if (disposed || ["online", "starting"].includes(status.status)) return;
          startsInFlight.current.add(camera.id);
          try {
            await startStream(camera.id);
          } finally {
            setTimeout(() => startsInFlight.current.delete(camera.id), 3000);
          }
        } catch {
          // The next supervisor pass retries a source that is temporarily unavailable.
        }
      }));
    }
    ensureStreams();
    const timer = setInterval(ensureStreams, 8000);
    return () => { disposed = true; clearInterval(timer); };
  }, [cameras]);
}

function StreamSupervisor() {
  const [cameras, setCameras] = useState([]);
  useEffect(() => {
    let disposed = false;
    async function refreshCameras() {
      try {
        const data = asArray(await getCameras());
        if (!disposed) setCameras(data);
      } catch {
        // The next refresh retries without blocking the visible dashboard.
      }
    }
    refreshCameras();
    const timer = setInterval(refreshCameras, 30000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  useStreamSupervisor(cameras);
  return null;
}

function LivePreview({ camera, alt }) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState("connecting");
  const retryTimer = useRef(null);
  const source = getStreamPreviewUrl(camera.id, attempt);

  useEffect(() => {
    // Reset the image retry state when the selected camera changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAttempt(0);
    setState("connecting");
    return () => clearTimeout(retryTimer.current);
  }, [camera.id]);

  function reconnect() {
    setState("reconnecting");
    clearTimeout(retryTimer.current);
    retryTimer.current = setTimeout(() => {
      setAttempt((current) => current + 1);
      setState("connecting");
    }, 1800);
  }

  if (!camera.is_active || !camera.stream_url) return <div className="camera-offline">OFFLINE / NO SOURCE</div>;
  return <>{state !== "live" && <div className="camera-stream-state">{state === "reconnecting" ? "RECONNECTING LIVE FEED" : "CONNECTING LIVE FEED"}</div>}<img className="camera-preview" src={source} alt={alt} onLoad={() => setState("live")} onError={reconnect} /></>;
}

function CameraTile({ camera }) { const status = cameraStatus(camera); return <div className="camera-tile"><div className="camera-feed"><LivePreview camera={camera} alt={`${camera.camera_code} live preview`} /><div className="feed-top"><b>{camera.camera_code}</b><span className={status === "online" ? "live" : "down"}>{status.toUpperCase()}</span></div><div className="feed-bottom"><span>{camera.sector}</span><time>{camera.name}</time></div></div><div className="tile-meta"><div><b>{camera.name}</b><small>{camera.stream_url || "No stream source configured"}</small></div><span className={status}>{status}</span></div></div>; }

function AlertNotification() {
  const navigate = useNavigate();
  const { message } = useWebSocket();
  const [alert, setAlert] = useState(null);
  const dismissedIds = useRef(new Set());
  const newestAlertId = useRef(0);

  useEffect(() => {
    if (message?.type !== "alert" || !message.data || dismissedIds.current.has(message.data.id)) return;
    // WebSocket delivery is immediate; REST recovery handles alerts emitted during reconnects.
    newestAlertId.current = Math.max(newestAlertId.current, Number(message.data.id) || 0);
    setAlert(message.data);
  }, [message]);

  useEffect(() => {
    let disposed = false;

    async function recoverActiveAlert() {
      try {
        const [activeAlerts, cameras] = await Promise.all([getAlerts("active"), getCameras()]);
        if (disposed) return;
        const cameraById = new Map(cameras.map((camera) => [camera.id, camera]));
        const candidate = activeAlerts.find((item) => (Number(item.id) || 0) > newestAlertId.current && !dismissedIds.current.has(item.id));
        if (candidate) {
          const camera = cameraById.get(candidate.camera_id);
          newestAlertId.current = Math.max(newestAlertId.current, Number(candidate.id) || 0);
          setAlert({ ...candidate, camera_name: camera?.name, camera_code: camera?.camera_code });
        }
      } catch {
        // WebSocket remains the primary notification path when REST recovery is unavailable.
      }
    }

    recoverActiveAlert();
    const timer = setInterval(recoverActiveAlert, 3000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);

  if (!alert) return null;
  function dismissAlert() {
    dismissedIds.current.add(alert.id);
    setAlert(null);
  }
  function openAlert() { dismissAlert(); navigate(`/alerts/${alert.id}`); }
  return <aside className="intrusion-notification" role="alert" onClick={openAlert}><button className="notification-close" aria-label="Dismiss notification" onClick={(event) => { event.stopPropagation(); dismissAlert(); }}>x</button><div className="notification-kicker"><AlertTriangle size={16} /> INTRUSION DETECTED</div><h2>{alert.alert_name || alert.reason || "Restricted zone intrusion"}</h2><strong>{alert.camera_name || `Camera ${alert.camera_id}`}{alert.camera_code ? ` (${alert.camera_code})` : ""}</strong><p>{alert.object_type || "Object"} #{alert.track_id ?? "-"} entered {alert.zone || "a restricted zone"}</p>{alert.plate_number && <p className="plate-highlight">Plate: <b>{alert.plate_number}</b>{alert.watchlist_match ? " | WATCHLIST MATCH" : ""}</p>}<small>Severity: {alert.severity || "Unknown"} | Score: {alert.score ?? "-"} | Confidence: {alert.confidence == null ? "-" : `${(Number(alert.confidence) * 100).toFixed(1)}%`}</small><small>Zone type: {alert.zone_type || "Unavailable"} | {alert.timestamp || "Time unavailable"}</small><button className="primary notification-action" onClick={(event) => { event.stopPropagation(); openAlert(); }}>Review intrusion</button></aside>;
}

function AddCameraForm({ onCancel, onSaved }) {
  const [form, setForm] = useState({ camera_code: "", name: "", sector: "", source_type: "mp4", stream_url: "" });
  const [file, setFile] = useState(null); const [saving, setSaving] = useState(false); const [testing, setTesting] = useState(false); const [error, setError] = useState(null); const [testResult, setTestResult] = useState(null);
  function update(field, value) { setForm((current) => ({ ...current, [field]: value })); }
  function changeSourceType(value) { update("source_type", value); setFile(null); setTestResult(null); setError(null); }
  async function testRtsp() {
    setError(null); setTestResult(null);
    if (!/^rtsp:\/\/[^/\s]+(?:\/\S*)?$/i.test(form.stream_url.trim())) { setError("Enter a valid RTSP URL before testing."); return; }
    setTesting(true);
    try { setTestResult(await testRtspConnection(form.stream_url.trim())); } catch (requestError) { setError(requestError.message); } finally { setTesting(false); }
  }
  async function submit(event) {
    event.preventDefault(); setError(null);
    if (form.source_type === "mp4" && !file) { setError("Select an MP4 file before saving this camera."); return; }
    if (form.source_type === "rtsp" && !form.stream_url.trim().startsWith("rtsp://")) { setError("Enter a valid RTSP URL."); return; }
    setSaving(true);
    try {
      const uploaded = form.source_type === "mp4" ? await uploadVideo(file) : null;
      await createCamera({ camera_code: form.camera_code.trim(), name: form.name.trim(), sector: form.sector.trim(), source_type: form.source_type, stream_url: uploaded?.stream_url || (form.source_type === "webcam" ? form.stream_url.trim() || "0" : form.stream_url.trim()), is_active: true, status: "offline" });
      onSaved();
    } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }
  return <form className="camera-form panel" onSubmit={submit}><div className="section-title"><div><h2>Add Camera Source</h2><small>Register a real MP4, webcam, or RTSP source.</small></div><button type="button" onClick={onCancel}>Cancel</button></div><div className="camera-form-grid"><label>Camera Code<input required value={form.camera_code} onChange={(event) => update("camera_code", event.target.value)} placeholder="CAM-02" /></label><label>Camera Name<input required value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="South Perimeter" /></label><label>Sector<input required value={form.sector} onChange={(event) => update("sector", event.target.value)} placeholder="Sector 02" /></label><label>Source Type<select value={form.source_type} onChange={(event) => changeSourceType(event.target.value)}>{[["mp4", "Video / MP4"], ["webcam", "Webcam"], ["rtsp", "RTSP / IP Camera"]].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>{form.source_type === "mp4" && <label>MP4 Video<input required type="file" accept=".mp4,video/mp4" onChange={(event) => setFile(event.target.files?.[0] || null)} />{file && <small>{file.name}</small>}</label>}{form.source_type === "webcam" && <label>Webcam Device Index<input value={form.stream_url} onChange={(event) => update("stream_url", event.target.value)} placeholder="0" /></label>}{form.source_type === "rtsp" && <label>RTSP URL<input required value={form.stream_url} onChange={(event) => { update("stream_url", event.target.value); setTestResult(null); }} placeholder="rtsp://user:password@host/stream" /><button type="button" onClick={testRtsp} disabled={testing || saving}>{testing ? "Testing..." : "Test Connection"}</button>{testResult && <small className={testResult.reachable ? "connection-ok" : "form-error"}>{testResult.message}</small>}</label>}</div>{error && <div className="form-error">{error}</div>}<div className="page-actions"><button type="submit" className="primary" disabled={saving}>{saving ? "Saving..." : "Save Camera"}</button></div></form>;
}

function EditCameraForm({ camera, onCancel, onSaved }) {
  const [form, setForm] = useState({ camera_code: camera.camera_code, name: camera.name, sector: camera.sector, is_active: camera.is_active });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  function update(field, value) { setForm((current) => ({ ...current, [field]: value })); }
  async function submit(event) {
    event.preventDefault(); setSaving(true); setError(null);
    try { await updateCamera(camera.id, { ...form, camera_code: form.camera_code.trim(), name: form.name.trim(), sector: form.sector.trim() }); onSaved(form.is_active ? camera.id : null); }
    catch (requestError) { setError(requestError.message); }
    finally { setSaving(false); }
  }
  return <form className="camera-form panel" onSubmit={submit}><div className="section-title"><div><h2>Edit {camera.camera_code}</h2><small>Update registration details and enable or disable automatic processing.</small></div><button type="button" onClick={onCancel}>Cancel</button></div><div className="camera-form-grid"><label>Camera Code<input required value={form.camera_code} onChange={(event) => update("camera_code", event.target.value)} /></label><label>Camera Name<input required value={form.name} onChange={(event) => update("name", event.target.value)} /></label><label>Sector<input required value={form.sector} onChange={(event) => update("sector", event.target.value)} /></label><label className="checkbox-field">Automatic Processing<input type="checkbox" checked={form.is_active} onChange={(event) => update("is_active", event.target.checked)} /></label></div>{error && <div className="form-error">{error}</div>}<div className="page-actions"><button type="submit" className="primary" disabled={saving}>{saving ? "Saving..." : "Save Changes"}</button></div></form>;
}

function Dashboard() {
  const cameras = useRemote(loadCameraRecords, [], asArray);
  const alerts = useRemote(getAlerts, [], asArray);
  const analytics = useRemote(getAnalytics, null, asObject);
  const health = useRemote(getHealth, null, asObject);
  const { message, connected } = useWebSocket();
  const liveAlerts = message?.type === "alert" && message.data ? [message.data, ...alerts.data.filter((alert) => alert.id !== message.data.id)] : alerts.data;
  const activeCameraCount = cameras.loading ? "Loading..." : cameras.error ? "Unavailable" : cameras.data.filter((camera) => camera.is_active).length;
  const analyticsDetail = analytics.loading ? "Loading metric..." : analytics.error ? "Analytics unavailable" : undefined;
  const healthValue = health.loading ? "Checking..." : health.error ? "Unavailable" : health.data?.status === "healthy" ? "Healthy" : "Degraded";

  return <Shell><main className="content"><PageHead eyebrow="Monitoring Overview" title="Border Surveillance" sub={`Real-time intelligence from configured surveillance sources. Live alerts: ${connected ? "connected" : "REST fallback"}.`} /><div className="stats"><Stat label="ACTIVE CAMERAS" value={activeCameraCount} /><Stat label="ACTIVE ALERTS" value={analytics.data?.active_alerts} detail={analyticsDetail} tone="critical" action={analytics.error ? analytics.reload : null} /><Stat label="PEOPLE DETECTED" value="Unavailable" detail="Object totals are not provided by the backend" /><Stat label="VEHICLES" value="Unavailable" detail="Object totals are not provided by the backend" /><Stat label="SYSTEM HEALTH" value={healthValue} detail={health.error ? "Backend health unavailable" : health.data?.version || "FastAPI service"} action={health.error ? health.reload : null} /></div><div className="dashboard-grid"><section><div className="section-title"><div><h2>Live Surveillance</h2><small>Configured camera sources</small></div><span className="tag blue">{cameras.data.length} SOURCES</span></div><State loading={cameras.loading} error={cameras.error} reload={cameras.reload} empty={cameras.data.length ? null : "No cameras configured. Add a camera source to begin surveillance."}><div className="camera-grid">{cameras.data.map((camera) => <CameraTile key={camera.id} camera={camera} />)}</div></State></section><section className="alert-panel"><div className="panel-title"><h2><AlertTriangle size={18} /> Active Alerts</h2><span className="tag salmon">{liveAlerts.length}</span></div><State loading={alerts.loading} error={alerts.error} reload={alerts.reload} empty={liveAlerts.length ? null : "No active alerts"}>{liveAlerts.slice(0, 4).map((alert) => <div className="alert-item" key={`${alert.id}-${alert.timestamp || alert.created_at || "live"}`}><div className="alert-row"><b>{alert.severity || "Unknown"}</b><time>{alert.timestamp || alert.created_at || "Unavailable"}</time></div><p>{alert.reason || alert.message || "No description"}</p><code>{alert.zone || "Zone unavailable"}</code></div>)}</State></section></div></main></Shell>;
}
function playLaptopAlarm() {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  const context = new AudioContext();
  const gain = context.createGain();
  gain.connect(context.destination);
  gain.gain.setValueAtTime(0.0001, context.currentTime);
  gain.gain.linearRampToValueAtTime(0.22, context.currentTime + .02);
  gain.gain.setValueAtTime(0.22, context.currentTime + 1.35);
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 1.7);
  context.resume();
  [0, .38, .76, 1.14].forEach((offset) => {
    const oscillator = context.createOscillator();
    oscillator.type = "square";
    oscillator.frequency.value = offset % .76 === 0 ? 880 : 660;
    oscillator.connect(gain);
    oscillator.start(context.currentTime + offset);
    oscillator.stop(context.currentTime + offset + .24);
  });
  setTimeout(() => context.close(), 1900);
}

function AlertDetailPage() {
  const { alertId } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [loadedId, setLoadedId] = useState(null);
  const [error, setError] = useState(null);
  const [decision, setDecision] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    Promise.all([getAlert(alertId), getCameras()]).then(([alertData, cameras]) => {
      if (!mounted) return;
      const camera = cameras.find((item) => item.id === alertData.camera_id);
      setAlert({ ...alertData, camera_name: camera?.name, camera_code: camera?.camera_code });
      setDecision(["confirmed", "declined"].includes(alertData.status) ? alertData.status : null);
    }).catch((requestError) => { if (mounted) setError(requestError.message); }).finally(() => { if (mounted) setLoadedId(alertId); });
    return () => { mounted = false; };
  }, [alertId]);

  async function decide(decisionValue) {
    setSaving(true);
    setError(null);
    if (decisionValue === "confirmed") playLaptopAlarm();
    try {
      const updated = await decideAlert(alertId, decisionValue);
      setAlert((current) => ({ ...current, ...updated }));
      setDecision(decisionValue);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return <Shell><main className="content"><PageHead eyebrow="Incident Response" title="Intrusion Review" sub="Confirm the detection to sound the local operator alarm, or decline it without audio." actions={<button onClick={() => navigate(-1)}>Back</button>} /><State loading={loadedId !== alertId} error={error} empty={alert ? null : "Alert not found"}>{alert && <section className="alert-detail panel"><div className="notification-kicker"><AlertTriangle size={18} /> {decision ? `ALERT ${decision.toUpperCase()}` : "ACTION REQUIRED"}</div><h2>{alert.reason || alert.message || "Intrusion detected"}</h2><div className="alert-detail-grid"><Stat label="CAMERA" value={alert.camera_name || `Camera ${alert.camera_id}`} detail={alert.camera_code || `ID ${alert.camera_id}`} /><Stat label="OBJECT" value={alert.object_type || "Unavailable"} detail={`Track ID ${alert.track_id ?? "Unavailable"}`} /><Stat label="ZONE" value={alert.zone || "Unavailable"} detail={alert.zone_type || "Zone type unavailable"} /><Stat label="THREAT SCORE" value={alert.score ?? "Unavailable"} detail={`Severity ${alert.severity || "Unavailable"}`} /><Stat label="PLATE" value={alert.plate_number || "UNKNOWN"} detail={alert.plate_confidence == null ? "OCR unavailable or low confidence" : `Confidence ${Math.round(alert.plate_confidence * 100)}%`} /></div><div className="alert-detail-meta"><p><b>Detected:</b> {alert.timestamp || alert.created_at || "Unavailable"}</p><p><b>Evidence:</b> {alert.evidence_path ? <a href={`${API_BASE_URL}${alert.evidence_path}`} target="_blank" rel="noreferrer">Open evidence snapshot</a> : "Unavailable"}</p>{alert.watchlist_match && <p className="critical-text"><b>WATCHLIST MATCH:</b> {alert.watchlist_label || alert.plate_number}</p>}</div>{!decision && <div className="decision-actions"><button className="primary" disabled={saving} onClick={() => decide("confirmed")}>Confirm Intrusion and Sound Alarm</button><button disabled={saving} onClick={() => decide("declined")}>Decline Intrusion</button></div>}{decision && <div className={`decision-result ${decision}`}>{decision === "confirmed" ? "Intrusion confirmed. Local alarm sounded." : "Intrusion declined. No alarm was played."}</div>}{error && <div className="form-error">{error}</div>}</section>}</State></main></Shell>;
}
function Alerts() { const result = useRemote(getAlerts, [], asArray); const [searchParams] = useSearchParams(); const query = (searchParams.get("search") || "").toLowerCase(); const alerts = result.data.filter((alert) => !query || [alert.reason, alert.message, alert.zone, alert.object_type, alert.plate_number, alert.camera_id].some((value) => String(value ?? "").toLowerCase().includes(query))); return <Shell><main className="content"><PageHead eyebrow="Incident Response" title="Active Alerts" sub={query ? `Active alerts matching "${query}".` : "Only alerts with active operator review status are shown."} /><State loading={result.loading} error={result.error} reload={result.reload} empty={alerts.length ? null : query ? "No active alerts match this search" : "No active alerts"}><div className="table-wrap"><table><thead><tr><th>ID</th><th>SEVERITY</th><th>EVENT</th><th>PLATE</th><th>SOURCE</th><th>TRACK / OBJECT</th><th>ZONE / SCORE</th><th>TIMESTAMP</th><th>EVIDENCE</th></tr></thead><tbody>{alerts.map((alert) => <tr key={alert.id}><td>{alert.id}</td><td><span className={`severity ${(alert.severity || "unknown").toLowerCase()}`}>{alert.severity || "Unknown"}</span></td><td><strong>{alert.reason || alert.message || "No description"}</strong>{alert.watchlist_match && <small className="critical-text">WATCHLIST MATCH</small>}</td><td>{alert.plate_number || "UNKNOWN"}</td><td>{alert.camera_id ?? "Unavailable"}</td><td>{alert.track_id ?? "Unavailable"} / {alert.object_type || "Unavailable"}</td><td>{alert.zone || "Unavailable"} / {alert.score ?? "-"}</td><td>{alert.timestamp || alert.created_at || "Unavailable"}</td><td>{alert.evidence_path ? <a href={`${API_BASE_URL}${alert.evidence_path}`} target="_blank" rel="noreferrer">Open</a> : "Unavailable"}</td></tr>)}</tbody></table></div></State></main></Shell>; }
function Cameras() { const result = useRemote(loadCameraRecords, [], asArray); const [adding, setAdding] = useState(false); const [editing, setEditing] = useState(null); const [actionError, setActionError] = useState(null); async function removeCamera(camera) { if (!window.confirm(`Delete ${camera.camera_code}?`)) return; setActionError(null); try { setManualStop(camera.id, true); await deleteCamera(camera.id); result.reload(); } catch (error) { setActionError(error.message); } } function saved(enabledCameraId) { if (enabledCameraId) setManualStop(enabledCameraId, false); setAdding(false); setEditing(null); result.reload(); } return <Shell><main className="content"><PageHead eyebrow="Network Infrastructure" title="Border Cameras" sub="Manage configured network streams and detection endpoints." actions={<button className="primary" onClick={() => { setAdding(true); setEditing(null); setActionError(null); }}>Add Camera</button>} />{adding && <AddCameraForm onCancel={() => setAdding(false)} onSaved={saved} />}{editing && <EditCameraForm camera={editing} onCancel={() => setEditing(null)} onSaved={saved} />}{actionError && <div className="state error-state">{actionError}</div>}<State {...result} empty={result.data.length ? null : "No cameras configured. Add a camera source to begin surveillance."}><div className="stats four"><Stat label="TOTAL CAMERAS" value={result.data.length} /><Stat label="ONLINE" value={result.data.filter((camera) => cameraStatus(camera) === "online").length} /><Stat label="OFFLINE / DEGRADED" value={result.data.filter((camera) => cameraStatus(camera) !== "online").length} tone="critical" /><Stat label="AI ACTIVE NODES" value={result.data.filter((camera) => camera.is_active && cameraStatus(camera) === "online").length} detail="Online processing workers" /></div><div className="table-wrap"><table><thead><tr><th>CAMERA ID</th><th>NAME / LOCATION</th><th>SECTOR</th><th>STATUS</th><th>SOURCE</th><th>DETECTION</th><th>ACTIONS</th></tr></thead><tbody>{result.data.map((camera) => <tr key={camera.id}><td>{camera.camera_code}</td><td>{camera.name}</td><td>{camera.sector}</td><td>{cameraStatus(camera)}</td><td>{camera.stream_url || "Not configured"}</td><td><span className="tag blue">{camera.is_active ? "ENABLED" : "DISABLED"}</span></td><td><button className="small-btn" onClick={() => { setEditing(camera); setAdding(false); }}>Edit</button><button className="small-btn" onClick={() => removeCamera(camera)}>Delete</button></td></tr>)}</tbody></table></div></State></main></Shell>; }
function Events() { const result = useRemote(getEvents, [], asArray); return <Shell><main className="content"><PageHead eyebrow="Historical Intelligence" title="Event Archive" sub="Recorded events returned by the surveillance backend." /><State {...result} empty={result.data.length ? null : "No events recorded"}><div className="table-wrap"><table><thead><tr><th>EVENT ID</th><th>TYPE</th><th>CAMERA</th><th>PLATE</th><th>SEVERITY</th><th>DESCRIPTION</th><th>TIMESTAMP</th></tr></thead><tbody>{result.data.map((event) => <tr key={event.id}><td>{event.id}</td><td>{event.event_type || "Unavailable"}</td><td>{event.camera_id ?? "Unavailable"}</td><td>{event.plate_number || "UNKNOWN"}{event.watchlist_match && <small className="critical-text">WATCHLIST MATCH</small>}</td><td>{event.severity || "Unavailable"}</td><td>{event.description || "No description"}</td><td>{event.timestamp || "Unavailable"}</td></tr>)}</tbody></table></div></State></main></Shell>; }

function PlateHistory() { const result = useRemote(getPlateHistory, [], asArray); const [query, setQuery] = useState(""); const normalized = query.trim().toLowerCase(); const rows = result.data.filter((item) => !normalized || [item.plate_number, item.camera_code, item.camera_name, item.vehicle_type].some((value) => String(value ?? "").toLowerCase().includes(normalized))); return <Shell><main className="content"><PageHead eyebrow="Vehicle Intelligence" title="Plate History" sub="Search persisted plate observations from MP4 and RTSP processing." /><div className="archive-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search plate number, camera, or vehicle" aria-label="Search plate history" /></div><State loading={result.loading} error={result.error} reload={result.reload} empty={rows.length ? null : normalized ? "No plate observations match this search" : "No plate observations recorded"}><div className="table-wrap"><table><thead><tr><th>PLATE</th><th>CAMERA</th><th>VEHICLE</th><th>TRACK</th><th>CONFIDENCE</th><th>TIME</th><th>EVIDENCE</th></tr></thead><tbody>{rows.map((item) => <tr key={item.id}><td><strong>{item.plate_number}</strong>{item.watchlist_label && <small className="critical-text">{item.watchlist_label}</small>}</td><td>{item.camera_code || item.camera_name || item.camera_id}</td><td>{item.vehicle_type}</td><td>{item.track_id}</td><td>{Math.round(item.plate_confidence * 100)}%</td><td>{item.timestamp}</td><td>{item.original_crop_path ? <a href={`${API_BASE_URL}${item.original_crop_path}`} target="_blank" rel="noreferrer">Open crop</a> : "Unavailable"}</td></tr>)}</tbody></table></div></State></main></Shell>; }
function Analytics() { const result = useRemote(getAnalytics, null, asObject); const detections = useRemote(getDetections, [], asArray); const reload = () => { result.reload(); detections.reload(); }; const analytics = result.data || {}; return <Shell><main className="content"><PageHead eyebrow="Operational Intelligence" title="Security Analytics" sub="Metrics calculated from stored detections, alerts, and events." /><State loading={result.loading || detections.loading} error={result.error || detections.error} reload={reload} empty={result.data ? null : "Analytics data unavailable"}><div className="stats four"><Stat label="TOTAL DETECTIONS" value={analytics.total_detections ?? "Unavailable"} /><Stat label="ACTIVE ALERTS" value={analytics.active_alerts ?? "Unavailable"} tone="critical" /><Stat label="CRITICAL ALERTS" value={analytics.critical_alerts ?? "Unavailable"} /><Stat label="TOTAL EVENTS" value={analytics.total_events ?? "Unavailable"} /><Stat label="NIGHT MOVEMENTS" value={analytics.night_movements ?? 0} /><Stat label="NIGHT INTRUSIONS" value={analytics.night_intrusions ?? 0} tone="critical" /><Stat label="NIGHT VEHICLES" value={analytics.night_vehicle_movements ?? 0} /></div><div className="chart-grid"><Chart title="Detection Trends" count={detections.data.length} /><Chart title="Alert Distribution" count={analytics.critical_alerts} /><Chart title="Stored Activity" count={analytics.total_events} /></div></State></main></Shell>; }
function Chart({ title, count }) { return <section className="chart panel"><h2>{title}</h2>{Number.isFinite(count) && count > 0 ? <div className="chart-value">{count}<small> records available</small></div> : <div className="chart-placeholder">No data available</div>}</section>; }
function Monitoring() { const result = useRemote(loadCameraRecords, [], asArray); const [selectedCameraId, setSelectedCameraId] = useState(""); const [manualStopped, setManualStopped] = useState(() => getManualStops()); const [streamError, setStreamError] = useState(null); const { message: liveMessage } = useWebSocket(); const selectedCamera = result.data.find((camera) => camera.id === Number(selectedCameraId)) || result.data[0]; const status = cameraStatus(selectedCamera); const previewActive = selectedCamera && !manualStopped.has(Number(selectedCamera.id)) && ["starting", "online"].includes(status); const plateEvent = liveMessage?.type === "anpr" && Number(liveMessage.data?.camera_id) === Number(selectedCamera?.id) ? liveMessage.data : null; const scene = selectedCamera?.stream_status?.scene || {}; async function toggleStream() { if (!selectedCamera) return; setStreamError(null); const shouldStop = previewActive || status === "stopping"; try { setManualStop(selectedCamera.id, shouldStop); setManualStopped(getManualStops()); if (shouldStop) await stopStream(selectedCamera.id); else await startStream(selectedCamera.id); await new Promise((resolve) => setTimeout(resolve, 500)); result.reload(); } catch (error) { setStreamError(error.message); } } return <Shell><main className="content"><PageHead eyebrow="Live Monitoring" title="Camera Feed" sub="Select a configured camera to inspect its stream and configure its restricted zones." /><State {...result} empty={result.data.length ? null : "No cameras configured. Add a video source before starting monitoring."}>{selectedCamera && <><div className="monitor-grid"><div className="big-feed"><LivePreview camera={selectedCamera} alt={`${selectedCamera.camera_code} live preview`} /><div className="feed-top"><b>{selectedCamera.camera_code}</b><span className={previewActive ? "live" : "down"}>{previewActive ? "LIVE" : status.toUpperCase()}</span></div><div className="feed-bottom"><span>{selectedCamera.stream_url || "No stream source configured"}</span></div></div><div className="panel monitor-controls"><h2>Camera Selection</h2><select value={selectedCamera.id} onChange={(event) => setSelectedCameraId(event.target.value)}>{result.data.map((camera) => <option value={camera.id} key={camera.id}>{camera.camera_code} - {camera.name}</option>)}</select><button className="primary" onClick={toggleStream}>{previewActive ? "Stop Stream" : "Start Stream"}</button><p className="state">{streamError || (previewActive ? "Processed video with detection overlays is active." : "Start the stream to open this camera source.")}</p><div className="night-context"><b>Scene: {scene.scene_condition || "UNKNOWN"}</b><span>{scene.brightness == null ? "Brightness unavailable" : `Brightness ${scene.brightness}`} | {selectedCamera?.stream_status?.moving_tracks || 0} moving tracked objects</span></div>{plateEvent && <div className="anpr-live-card"><b>Latest ANPR observation</b><strong>{plateEvent.plate_number}</strong><span>{plateEvent.vehicle_type} #{plateEvent.track_id} | {Math.round(plateEvent.plate_confidence * 100)}% confidence</span>{plateEvent.watchlist_match && <em>WATCHLIST MATCH: {plateEvent.watchlist_label}</em>}</div>}</div></div><ZoneEditor cameras={result.data} cameraId={selectedCamera.id} onCameraChange={(value) => setSelectedCameraId(value)} previewActive={previewActive} /></>}</State></main></Shell>; }
function BorderMap() { const result = useRemote(getCameras, [], asArray); const mapped = result.data.filter((camera) => camera.location_lat != null && camera.location_lng != null); return <Shell><main className="content"><PageHead eyebrow="Geospatial Operations" title="Border Map" sub="Configured camera positions and restricted zones." /><State {...result} empty={mapped.length ? null : "Map data unavailable. Configure camera coordinates to display operational positions."}><div className="map-canvas">{mapped.map((camera, index) => <div className={`sensor map-sensor-${index}`} key={camera.id}>o<small>{camera.camera_code}</small></div>)}<div className="map-legend"><b>Map Legend</b><span>o Configured Camera</span></div></div></State></main></Shell>; }
function SettingsPage() {
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { getSettings().then(setSettings).catch((requestError) => setError(requestError.message)); }, []);
  function update(field, value) { setSettings((current) => ({ ...current, [field]: value })); }
  async function save() { setSaving(true); setError(null); try { setSettings(await updateSettings(settings)); } catch (requestError) { setError(requestError.message); } finally { setSaving(false); } }
  const toggles = [["wildlife_suppression", "Wildlife Suppression"], ["severe_weather_compensation", "Severe Weather Compensation"], ["night_vision_filtering", "Night Vision Artifact Filtering"]];
  return <Shell><main className="content"><PageHead eyebrow="System Administration" title="Configuration" sub="Runtime detection settings apply to newly started processing workers." actions={<button className="primary" disabled={!settings || saving} onClick={save}>{saving ? "Saving..." : "Save Settings"}</button>} />{error && <div className="state error-state">{error}</div>}{!settings ? <div className="state">Loading configuration...</div> : <div className="settings-layout"><div className="settings-nav"><b>Detection Thresholds</b><span>Alert Config</span><span>Restricted Zones</span><span>Notification Settings</span><span>Operator Access</span></div><div><section className="settings-card"><h2>AI Sensitivity Calibration</h2><p>Adjust the minimum confidence passed to the active YOLO pipeline. Changes apply when a camera worker starts again.</p><label>Human Detection Confidence <b>{Math.round(settings.detection_confidence * 100)}%</b><input type="range" min="0.1" max="0.99" step="0.01" value={settings.detection_confidence} onChange={(event) => update("detection_confidence", Number(event.target.value))} /></label><label>Vehicle Identification <b>{Math.round(settings.vehicle_confidence * 100)}%</b><input type="range" min="0.1" max="0.99" step="0.01" value={settings.vehicle_confidence} onChange={(event) => update("vehicle_confidence", Number(event.target.value))} /></label></section><section className="settings-card"><h2>Environmental Filters</h2><p>These runtime switches are stored by the backend. They are available for the current operator configuration while the model-specific filters evolve.</p>{toggles.map(([key, name]) => <div className="toggle-row" key={key}><span><b>{name}</b><small>{settings[key] ? "Enabled" : "Disabled"}</small></span><button type="button" className={`setting-toggle ${settings[key] ? "on" : ""}`} aria-pressed={settings[key]} onClick={() => update(key, !settings[key])}><i /></button></div>)}</section></div></div>}</main></Shell>;
}
function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: "operator", password: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  async function submit(event) { event.preventDefault(); setLoading(true); setError(null); try { await loginOperator(form.username.trim(), form.password); navigate(location.state?.from || "/dashboard", { replace: true }); } catch (requestError) { setError(requestError.message); } finally { setLoading(false); } }
  return <main className="login"><Shield size={42} /><h1>Sentinel AI</h1><p>Border Control Unit</p><form className="login-form" onSubmit={submit}><label>Operator ID<input required value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} /></label><label>Password<input required type="password" value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} /></label>{error && <div className="form-error">{error}</div>}<button className="primary" disabled={loading}>{loading ? "Signing in..." : "Enter Command Center"}</button><small>Local operator credentials are configured by the backend environment.</small></form></main>;
}
export default function App() { return <RouteErrorBoundary><BrowserRouter><Routes><Route path="/login" element={<Login />} /><Route element={<ProtectedLayout />}><Route path="/" element={<Dashboard />} /><Route path="/dashboard" element={<Dashboard />} /><Route path="/monitoring" element={<Monitoring />} /><Route path="/alerts" element={<Alerts />} /><Route path="/alerts/:alertId" element={<AlertDetailPage />} /><Route path="/events" element={<Events />} /><Route path="/archive" element={<Events />} /><Route path="/plate-history" element={<PlateHistory />} /><Route path="/cameras" element={<Cameras />} /><Route path="/border-map" element={<BorderMap />} /><Route path="/analytics" element={<Analytics />} /><Route path="/settings" element={<SettingsPage />} /><Route path="*" element={<Dashboard />} /></Route></Routes></BrowserRouter></RouteErrorBoundary>; }
