from __future__ import annotations

import argparse
from pathlib import Path

from .config import MonitorConfig
from .monitor import Monitor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Home network monitor")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one monitor cycle and exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = MonitorConfig.load(config_path)
    monitor = Monitor(config)
    if args.once:
        monitor.run_cycle()
        return 0
    monitor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
