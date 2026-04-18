from __future__ import annotations

from dataclasses import dataclass
import time
import uuid

from .classifier import classify_cycle
from .config import MonitorConfig
from .db import Database, ProbeRecord
from .discovery import DiscoveredDevice, current_timestamp, detect_network_context, discover_devices
from .probes import fetch_http, ping_target, resolve_dns


@dataclass(slots=True)
class Target:
    name: str
    address: str
    kind: str


class Monitor:
    def __init__(self, config: MonitorConfig) -> None:
        self.config = config
        self.db = Database(config.db_path)
        self.network = detect_network_context(config.subnet, config.gateway_ip_fallback)
        self.last_discovery_at = 0.0

    def run_forever(self) -> None:
        while True:
            started = time.monotonic()
            self.run_cycle()
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, self.config.interval_seconds - elapsed)
            time.sleep(sleep_for)

    def run_cycle(self) -> None:
        now = current_timestamp()
        cycle_id = str(uuid.uuid4())

        self._sync_known_devices(now)
        discovered_targets = self._maybe_refresh_discovery(now)
        static_targets = self._static_targets()
        probe_targets = list(static_targets)
        if self.config.probe_discovered_devices:
            probe_targets.extend(
                Target(name=device.name, address=device.address, kind=device.kind)
                for device in discovered_targets
            )

        records: list[ProbeRecord] = []
        gateway_ok = False
        upstream_ok = False
        internet_icmp_results: list[bool] = []
        dns_results: list[bool] = []
        http_results: list[bool] = []

        for target in probe_targets:
            result = ping_target(target.address)
            records.append(
                ProbeRecord(
                    ts=now,
                    cycle_id=cycle_id,
                    target_name=target.name,
                    target_address=target.address,
                    target_kind=target.kind,
                    probe_type=result.probe_type,
                    success=result.success,
                    latency_ms=result.latency_ms,
                    details=result.details,
                )
            )
            if target.kind == "gateway":
                gateway_ok = result.success
            elif target.kind == "upstream":
                upstream_ok = result.success

        for address in self.config.internet_icmp:
            result = ping_target(address)
            internet_icmp_results.append(result.success)
            records.append(
                ProbeRecord(
                    ts=now,
                    cycle_id=cycle_id,
                    target_name=f"icmp-{address}",
                    target_address=address,
                    target_kind="internet",
                    probe_type=result.probe_type,
                    success=result.success,
                    latency_ms=result.latency_ms,
                    details=result.details,
                )
            )

        for name in self.config.dns_names:
            result = resolve_dns(name)
            dns_results.append(result.success)
            records.append(
                ProbeRecord(
                    ts=now,
                    cycle_id=cycle_id,
                    target_name=f"dns-{name}",
                    target_address=name,
                    target_kind="internet",
                    probe_type=result.probe_type,
                    success=result.success,
                    latency_ms=result.latency_ms,
                    details=result.details,
                )
            )

        for url in self.config.http_urls:
            result = fetch_http(url)
            http_results.append(result.success)
            records.append(
                ProbeRecord(
                    ts=now,
                    cycle_id=cycle_id,
                    target_name=f"http-{url}",
                    target_address=url,
                    target_kind="internet",
                    probe_type=result.probe_type,
                    success=result.success,
                    latency_ms=result.latency_ms,
                    details=result.details,
                )
            )

        internet_icmp_ok = any(internet_icmp_results) if internet_icmp_results else False
        dns_ok = any(dns_results) if dns_results else False
        http_ok = any(http_results) if http_results else False
        classification = classify_cycle(
            gateway_ok=gateway_ok,
            upstream_ok=upstream_ok,
            internet_icmp_ok=internet_icmp_ok,
            dns_ok=dns_ok,
            http_ok=http_ok,
        )

        self.db.insert_probe_results(records)
        self.db.insert_cycle_summary(
            cycle_id=cycle_id,
            ts=now,
            gateway_ok=gateway_ok,
            upstream_ok=upstream_ok,
            internet_icmp_ok=internet_icmp_ok,
            dns_ok=dns_ok,
            http_ok=http_ok,
            classification=classification,
        )

    def _static_targets(self) -> list[Target]:
        targets_by_address: dict[str, Target] = {}

        targets_by_address[self.network.gateway_ip] = Target(
            name="local-gateway",
            address=self.network.gateway_ip,
            kind="gateway",
        )
        targets_by_address[self.config.first_upstream_hop] = Target(
            name="first-upstream-hop",
            address=self.config.first_upstream_hop,
            kind="upstream",
        )

        for device in self.config.known_devices:
            if device.probe:
                targets_by_address[device.address] = Target(
                    name=device.name,
                    address=device.address,
                    kind=device.kind,
                )

        for target in self.config.extra_targets:
            targets_by_address[target.address] = Target(
                name=target.name,
                address=target.address,
                kind=target.kind,
            )
        return list(targets_by_address.values())

    def _maybe_refresh_discovery(self, now: str) -> list[DiscoveredDevice]:
        current = time.monotonic()
        if current - self.last_discovery_at < self.config.discovery_interval_seconds:
            rows = self.db.get_discovered_devices()
            return [
                DiscoveredDevice(
                    name=row["name"],
                    address=row["address"],
                    mac_address=row["mac_address"],
                    kind=row["kind"],
                )
                for row in rows
            ]

        devices = discover_devices(self.network.subnet, method=self.config.discovery_method)
        for device in devices:
            self.db.upsert_device(
                name=device.name,
                address=device.address,
                mac_address=device.mac_address,
                kind=device.kind,
                source=device.source,
                seen_at=now,
            )
        self.last_discovery_at = current
        return devices

    def _sync_known_devices(self, now: str) -> None:
        for device in self.config.known_devices:
            self.db.upsert_device(
                name=device.name,
                address=device.address,
                mac_address=device.mac_address,
                kind=device.kind,
                source="manual",
                seen_at=now,
            )

    def close(self) -> None:
        self.db.close()
