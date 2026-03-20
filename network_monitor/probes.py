from __future__ import annotations

from dataclasses import dataclass
import re
import socket
import subprocess
import time
from urllib import error, request


_PING_LATENCY_RE = re.compile(r"time=(?P<latency>[0-9.]+)\s*ms")


@dataclass(slots=True)
class ProbeResult:
    probe_type: str
    success: bool
    latency_ms: float | None
    details: dict[str, object]


def ping_target(address: str) -> ProbeResult:
    started = time.monotonic()
    completed = subprocess.run(
        ["ping", "-4", "-c", "1", "-W", "1", address],
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed_ms = (time.monotonic() - started) * 1000
    output = completed.stdout + completed.stderr
    match = _PING_LATENCY_RE.search(output)
    latency_ms = float(match.group("latency")) if match else elapsed_ms if completed.returncode == 0 else None
    return ProbeResult(
        probe_type="icmp",
        success=completed.returncode == 0,
        latency_ms=latency_ms,
        details={"returncode": completed.returncode},
    )


def resolve_dns(name: str) -> ProbeResult:
    started = time.monotonic()
    try:
        infos = socket.getaddrinfo(name, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
        elapsed_ms = (time.monotonic() - started) * 1000
        addresses = sorted({info[4][0] for info in infos})
        return ProbeResult(
            probe_type="dns",
            success=True,
            latency_ms=elapsed_ms,
            details={"addresses": addresses},
        )
    except socket.gaierror as exc:
        elapsed_ms = (time.monotonic() - started) * 1000
        return ProbeResult(
            probe_type="dns",
            success=False,
            latency_ms=elapsed_ms,
            details={"error": str(exc)},
        )


def fetch_http(url: str, timeout_seconds: float = 3.0) -> ProbeResult:
    started = time.monotonic()
    req = request.Request(url, method="GET", headers={"User-Agent": "network-monitor/0.1"})
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            elapsed_ms = (time.monotonic() - started) * 1000
            return ProbeResult(
                probe_type="http",
                success=200 <= response.status < 400,
                latency_ms=elapsed_ms,
                details={"status": response.status},
            )
    except error.URLError as exc:
        elapsed_ms = (time.monotonic() - started) * 1000
        return ProbeResult(
            probe_type="http",
            success=False,
            latency_ms=elapsed_ms,
            details={"error": str(exc)},
        )
