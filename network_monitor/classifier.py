from __future__ import annotations


def classify_cycle(
    *,
    gateway_ok: bool,
    upstream_ok: bool,
    internet_icmp_ok: bool,
    dns_ok: bool,
    http_ok: bool,
) -> str:
    if not gateway_ok:
        return "local_gateway"
    if gateway_ok and not upstream_ok and not internet_icmp_ok:
        return "upstream_handoff"
    if gateway_ok and upstream_ok and not internet_icmp_ok:
        return "provider_path"
    if internet_icmp_ok and not dns_ok:
        return "dns_only"
    if internet_icmp_ok and dns_ok and not http_ok:
        return "http_only"
    if gateway_ok and upstream_ok and internet_icmp_ok and dns_ok and http_ok:
        return "healthy"
    return "unknown"
