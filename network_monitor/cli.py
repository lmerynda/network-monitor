from __future__ import annotations

import json

from .config import MonitorConfig
from .db import Database


def print_status(config: MonitorConfig, limit: int = 10) -> int:
    db = Database(config.db_path)
    try:
        cycles = db.get_recent_cycles(limit=limit)
        if not cycles:
            print("No cycle data recorded yet.")
            return 0

        for row in cycles:
            print(
                f"{row['ts']} classification={row['classification']} "
                f"gateway={row['gateway_ok']} upstream={row['upstream_ok']} "
                f"internet_icmp={row['internet_icmp_ok']} dns={row['dns_ok']} http={row['http_ok']}"
            )
        return 0
    finally:
        db.close()


def print_incidents(config: MonitorConfig, limit: int = 20) -> int:
    db = Database(config.db_path)
    try:
        incidents = db.get_recent_incidents(limit=limit)
        if not incidents:
            print("No non-healthy cycles recorded.")
            return 0

        for row in incidents:
            print(
                f"{row['ts']} classification={row['classification']} "
                f"gateway={row['gateway_ok']} upstream={row['upstream_ok']} "
                f"internet_icmp={row['internet_icmp_ok']} dns={row['dns_ok']} http={row['http_ok']}"
            )
        return 0
    finally:
        db.close()


def print_latest_probes(config: MonitorConfig, cycle_limit: int = 1) -> int:
    db = Database(config.db_path)
    try:
        rows = db.get_latest_probe_results(cycle_limit=cycle_limit)
        if not rows:
            print("No probe results recorded yet.")
            return 0

        for row in rows:
            details = json.loads(row["details_json"])
            print(
                f"{row['ts']} {row['target_kind']} {row['target_name']} "
                f"({row['target_address']}) probe={row['probe_type']} "
                f"success={row['success']} latency_ms={row['latency_ms']} details={details}"
            )
        return 0
    finally:
        db.close()


def print_discovered(config: MonitorConfig, limit: int = 50) -> int:
    db = Database(config.db_path)
    try:
        rows = db.get_discovered_devices_recent(limit=limit)
        if not rows:
            print("No discovered devices recorded yet.")
            return 0

        for row in rows:
            print(
                f"{row['last_seen']} {row['address']} name={row['name']} "
                f"mac={row['mac_address']} kind={row['kind']}"
            )
        return 0
    finally:
        db.close()


def print_inventory(config: MonitorConfig, limit: int = 100) -> int:
    db = Database(config.db_path)
    try:
        rows = db.get_inventory(limit=limit)
        if not rows:
            print("No devices recorded yet.")
            return 0

        for row in rows:
            print(
                f"{row['address']} name={row['name']} mac={row['mac_address']} "
                f"kind={row['kind']} source={row['source']} last_seen={row['last_seen']}"
            )
        return 0
    finally:
        db.close()
