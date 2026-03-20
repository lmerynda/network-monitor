from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import re
import subprocess


_DEFAULT_ROUTE_RE = re.compile(r"default via (?P<gateway>\S+) dev (?P<iface>\S+)")
_ADDR_RE = re.compile(r"inet (?P<address>\d+\.\d+\.\d+\.\d+)/(?P<prefix>\d+)")
_NEIGH_RE = re.compile(
    r"(?P<address>\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+lladdr\s+(?P<mac>[0-9a-f:]{17})\s+\S+",
    re.IGNORECASE,
)


@dataclass(slots=True)
class DiscoveredDevice:
    name: str
    address: str
    mac_address: str | None
    kind: str
    source: str = "discovery"


@dataclass(slots=True)
class NetworkContext:
    gateway_ip: str
    interface: str | None
    subnet: str


def detect_network_context(subnet_config: str, gateway_fallback: str) -> NetworkContext:
    gateway_ip = gateway_fallback
    interface = None

    try:
        route = _run_command(["ip", "route", "show", "default"])
        match = _DEFAULT_ROUTE_RE.search(route)
        if match:
            gateway_ip = match.group("gateway")
            interface = match.group("iface")
    except RuntimeError:
        pass

    subnet = subnet_config
    if subnet == "auto":
        try:
            subnet = _detect_subnet(interface)
        except RuntimeError:
            subnet = _guess_subnet_from_gateway(gateway_ip)

    return NetworkContext(gateway_ip=gateway_ip, interface=interface, subnet=subnet)


def discover_devices(subnet: str, max_workers: int = 32) -> list[DiscoveredDevice]:
    network = ipaddress.ip_network(subnet, strict=False)
    discovered: list[DiscoveredDevice] = []

    hosts = [str(host) for host in network.hosts()]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ping_host, host): host for host in hosts}
        for future in as_completed(futures):
            host = futures[future]
            if future.result():
                discovered.append(
                    DiscoveredDevice(
                        name=f"lan-{host}",
                        address=host,
                        mac_address=None,
                        kind="discovered",
                    )
                )

    mac_map = _read_neighbor_table()
    for device in discovered:
        device.mac_address = mac_map.get(device.address)
    return sorted(discovered, key=lambda item: tuple(int(part) for part in item.address.split(".")))


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_subnet(interface: str | None) -> str:
    if not interface:
        raise RuntimeError("Unable to auto-detect subnet without an interface")

    output = _run_command(["ip", "-o", "-f", "inet", "addr", "show", "dev", interface])
    match = _ADDR_RE.search(output)
    if not match:
        raise RuntimeError(f"Unable to detect subnet for interface {interface}")

    address = match.group("address")
    prefix = match.group("prefix")
    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return str(network)


def _read_neighbor_table() -> dict[str, str]:
    try:
        output = _run_command(["ip", "neigh", "show"])
    except RuntimeError:
        return {}
    mapping: dict[str, str] = {}
    for line in output.splitlines():
        match = _NEIGH_RE.search(line)
        if match:
            mapping[match.group("address")] = match.group("mac")
    return mapping


def _ping_host(host: str) -> bool:
    completed = subprocess.run(
        ["ping", "-4", "-c", "1", "-W", "1", host],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def _run_command(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"Command failed: {' '.join(command)} {stderr}")
    return completed.stdout


def _guess_subnet_from_gateway(gateway_ip: str) -> str:
    network = ipaddress.ip_network(f"{gateway_ip}/24", strict=False)
    return str(network)
