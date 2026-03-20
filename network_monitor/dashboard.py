from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import MonitorConfig
from .db import Database


STATIC_DIR = Path(__file__).resolve().parent / "web"


@dataclass(slots=True)
class DashboardConfig:
    host: str = "0.0.0.0"
    port: int = 8080


def run_dashboard(config: MonitorConfig, host: str = "0.0.0.0", port: int = 8080) -> None:
    db = Database(config.db_path)
    server = ThreadingHTTPServer((host, port), _build_handler(db))
    server.serve_forever()


def _build_handler(db: Database) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._serve_static("index.html", "text/html; charset=utf-8")
                return
            if path == "/app.js":
                self._serve_static("app.js", "application/javascript; charset=utf-8")
                return
            if path == "/styles.css":
                self._serve_static("styles.css", "text/css; charset=utf-8")
                return
            if path == "/api/status":
                self._serve_json(_status_payload(db))
                return
            if path == "/api/incidents":
                hours = _read_hours(parsed.query, default=24)
                self._serve_json(_incidents_payload(db, hours))
                return
            if path == "/api/timeline":
                hours = _read_hours(parsed.query, default=24)
                self._serve_json(_timeline_payload(db, hours))
                return
            if path == "/api/discovered":
                limit = _read_limit(parsed.query, default=50, max_value=500)
                self._serve_json(_discovered_payload(db, limit))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _serve_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, name: str, content_type: str) -> None:
            body = (STATIC_DIR / name).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DashboardHandler


def _status_payload(db: Database) -> dict[str, object]:
    cycle = db.get_latest_cycle()
    if cycle is None:
        return {"status": None, "probes": []}

    probes = []
    for row in db.get_latest_probes_for_cycle(cycle["cycle_id"]):
        probes.append(
            {
                "ts": row["ts"],
                "target_name": row["target_name"],
                "target_address": row["target_address"],
                "target_kind": row["target_kind"],
                "probe_type": row["probe_type"],
                "success": bool(row["success"]),
                "latency_ms": row["latency_ms"],
                "details": json.loads(row["details_json"]),
            }
        )

    return {
        "status": {
            "cycle_id": cycle["cycle_id"],
            "ts": cycle["ts"],
            "classification": cycle["classification"],
            "gateway_ok": bool(cycle["gateway_ok"]),
            "upstream_ok": bool(cycle["upstream_ok"]),
            "internet_icmp_ok": bool(cycle["internet_icmp_ok"]),
            "dns_ok": bool(cycle["dns_ok"]),
            "http_ok": bool(cycle["http_ok"]),
        },
        "probes": probes,
    }


def _incidents_payload(db: Database, hours: int) -> dict[str, object]:
    since = _since_timestamp(hours)
    rows = db.get_cycle_summaries_since(since)
    incidents = []
    current: dict[str, object] | None = None
    previous_ts: str | None = None

    for row in rows:
        classification = row["classification"]
        ts = row["ts"]
        if classification == "healthy":
            if current is not None:
                current["end_ts"] = previous_ts or ts
                incidents.append(current)
                current = None
            previous_ts = ts
            continue

        if current is None or current["classification"] != classification:
            if current is not None:
                current["end_ts"] = previous_ts or ts
                incidents.append(current)
            current = {
                "classification": classification,
                "start_ts": ts,
                "end_ts": ts,
                "cycles": 1,
                "gateway_ok": bool(row["gateway_ok"]),
                "upstream_ok": bool(row["upstream_ok"]),
                "internet_icmp_ok": bool(row["internet_icmp_ok"]),
                "dns_ok": bool(row["dns_ok"]),
                "http_ok": bool(row["http_ok"]),
            }
        else:
            current["end_ts"] = ts
            current["cycles"] = int(current["cycles"]) + 1
        previous_ts = ts

    if current is not None:
        current["end_ts"] = previous_ts or current["start_ts"]
        incidents.append(current)

    incidents.reverse()
    return {"hours": hours, "incidents": incidents}


def _timeline_payload(db: Database, hours: int) -> dict[str, object]:
    since = _since_timestamp(hours)
    rows = db.get_cycle_summaries_since(since)
    series = {
        "gateway": [],
        "upstream": [],
        "internet_icmp": [],
        "dns": [],
        "http": [],
    }
    for row in rows:
        ts = row["ts"]
        series["gateway"].append({"ts": ts, "ok": bool(row["gateway_ok"])})
        series["upstream"].append({"ts": ts, "ok": bool(row["upstream_ok"])})
        series["internet_icmp"].append({"ts": ts, "ok": bool(row["internet_icmp_ok"])})
        series["dns"].append({"ts": ts, "ok": bool(row["dns_ok"])})
        series["http"].append({"ts": ts, "ok": bool(row["http_ok"])})
    return {"hours": hours, "series": series}


def _discovered_payload(db: Database, limit: int) -> dict[str, object]:
    devices = []
    for row in db.get_discovered_devices_recent(limit=limit):
        devices.append(
            {
                "name": row["name"],
                "address": row["address"],
                "mac_address": row["mac_address"],
                "kind": row["kind"],
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
            }
        )
    return {"devices": devices}


def _since_timestamp(hours: int) -> str:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return since.isoformat()


def _read_hours(query: str, default: int) -> int:
    params = parse_qs(query)
    value = params.get("hours", [str(default)])[0]
    try:
        parsed = int(value)
    except ValueError:
        return default
    return min(max(parsed, 1), 24 * 30)


def _read_limit(query: str, default: int, max_value: int) -> int:
    params = parse_qs(query)
    value = params.get("limit", [str(default)])[0]
    try:
        parsed = int(value)
    except ValueError:
        return default
    return min(max(parsed, 1), max_value)
