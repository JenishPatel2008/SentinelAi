from urllib.parse import quote, urlsplit, urlunsplit


def validate_rtsp_url(value: str | None) -> str:
    """Validate RTSP syntax without attempting a network connection."""
    if not value or not value.strip():
        raise ValueError("RTSP URL is required")

    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Enter a valid RTSP URL") from exc

    if parsed.scheme.lower() != "rtsp" or not hostname or port is not None and not 1 <= port <= 65535:
        raise ValueError("RTSP URL must start with rtsp:// and include a host")
    return candidate


def sanitize_stream_url(value: str | None) -> str | None:
    """Hide RTSP passwords before a source URL leaves the backend."""
    if not value or not value.lower().startswith("rtsp://"):
        return value

    try:
        parsed = urlsplit(value)
        if parsed.password is None:
            return value
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        username = quote(parsed.username or "", safe="")
        netloc = f"{username}:****@{host}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    except ValueError:
        return "rtsp://[credentials hidden]"
