from __future__ import annotations

import argparse
from pathlib import Path

from .cli import print_discovered, print_incidents, print_latest_probes, print_status
from .config import MonitorConfig
from .dashboard import run_dashboard
from .monitor import Monitor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Home network monitor")
    parser.add_argument("--config", default="config.json", help="Path to JSON config file")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the monitor")
    run_parser.add_argument("--once", action="store_true", help="Run one monitor cycle and exit")

    status_parser = subparsers.add_parser("status", help="Show recent cycle summaries")
    status_parser.add_argument("--limit", type=int, default=10, help="Number of cycles to show")

    incidents_parser = subparsers.add_parser("incidents", help="Show recent non-healthy cycles")
    incidents_parser.add_argument("--limit", type=int, default=20, help="Number of incidents to show")

    probes_parser = subparsers.add_parser("probes", help="Show probe rows from the latest cycles")
    probes_parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="How many recent cycles to include",
    )

    discovered_parser = subparsers.add_parser("discovered", help="Show discovered LAN devices")
    discovered_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of discovered devices to show",
    )

    serve_parser = subparsers.add_parser("serve", help="Run the local dashboard server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host/IP to bind")
    serve_parser.add_argument("--port", type=int, default=8080, help="TCP port to bind")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = MonitorConfig.load(config_path)
    command = args.command or "run"

    if command == "status":
        return print_status(config, limit=args.limit)
    if command == "incidents":
        return print_incidents(config, limit=args.limit)
    if command == "probes":
        return print_latest_probes(config, cycle_limit=args.cycles)
    if command == "discovered":
        return print_discovered(config, limit=args.limit)
    if command == "serve":
        run_dashboard(config, host=args.host, port=args.port)
        return 0

    monitor = Monitor(config)
    if args.once:
        monitor.run_cycle()
        return 0
    monitor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
