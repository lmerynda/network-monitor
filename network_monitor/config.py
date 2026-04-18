from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ExtraTarget:
    name: str
    address: str
    kind: str = "extra"
    enabled: bool = True


@dataclass(slots=True)
class KnownDevice:
    name: str
    address: str
    mac_address: str | None = None
    kind: str = "known"
    probe: bool = True
    enabled: bool = True


@dataclass(slots=True)
class MonitorConfig:
    db_path: Path
    interval_seconds: int = 10
    discovery_interval_seconds: int = 300
    subnet: str = "auto"
    gateway_ip_fallback: str = "192.168.1.254"
    probe_discovered_devices: bool = False
    discovery_method: str = "auto"
    first_upstream_hop: str = "107.220.56.1"
    internet_icmp: list[str] = field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    dns_names: list[str] = field(default_factory=lambda: ["google.com", "cloudflare.com"])
    http_urls: list[str] = field(
        default_factory=lambda: ["https://connectivitycheck.gstatic.com/generate_204"]
    )
    known_devices: list[KnownDevice] = field(default_factory=list)
    extra_targets: list[ExtraTarget] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "MonitorConfig":
        config_path = Path(path)
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        monitor = raw.get("monitor", {})
        targets = raw.get("targets", {})
        known_devices = [
            KnownDevice(
                name=item["name"],
                address=item["address"],
                mac_address=item.get("mac_address"),
                kind=item.get("kind", "known"),
                probe=item.get("probe", True),
                enabled=item.get("enabled", True),
            )
            for item in raw.get("known_devices", [])
        ]
        extra_targets = [
            ExtraTarget(
                name=item["name"],
                address=item["address"],
                kind=item.get("kind", "extra"),
                enabled=item.get("enabled", True),
            )
            for item in raw.get("extra_targets", [])
        ]

        db_path = Path(monitor.get("db_path", "data/network-monitor.sqlite3"))
        if not db_path.is_absolute():
            db_path = (config_path.parent / db_path).resolve()

        return cls(
            db_path=db_path,
            interval_seconds=int(monitor.get("interval_seconds", 10)),
            discovery_interval_seconds=int(monitor.get("discovery_interval_seconds", 300)),
            subnet=str(monitor.get("subnet", "auto")),
            gateway_ip_fallback=str(monitor.get("gateway_ip_fallback", "192.168.1.254")),
            probe_discovered_devices=bool(monitor.get("probe_discovered_devices", False)),
            discovery_method=str(monitor.get("discovery_method", "auto")),
            first_upstream_hop=str(targets.get("first_upstream_hop", "107.220.56.1")),
            internet_icmp=_as_list(targets, "internet_icmp", ["1.1.1.1", "8.8.8.8"]),
            dns_names=_as_list(targets, "dns_names", ["google.com", "cloudflare.com"]),
            http_urls=_as_list(
                targets,
                "http_urls",
                ["https://connectivitycheck.gstatic.com/generate_204"],
            ),
            known_devices=[device for device in known_devices if device.enabled],
            extra_targets=[target for target in extra_targets if target.enabled],
        )


def _as_list(raw: dict[str, Any], key: str, default: list[str]) -> list[str]:
    value = raw.get(key, default)
    if not isinstance(value, list):
        raise ValueError(f"Expected list for {key}")
    return [str(item) for item in value]
