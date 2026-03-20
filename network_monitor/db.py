from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any


@dataclass(slots=True)
class ProbeRecord:
    ts: str
    cycle_id: str
    target_name: str
    target_address: str
    target_kind: str
    probe_type: str
    success: bool
    latency_ms: float | None
    details: dict[str, Any]


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                mac_address TEXT,
                kind TEXT NOT NULL,
                source TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE(address, source)
            );

            CREATE TABLE IF NOT EXISTS probe_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                target_name TEXT NOT NULL,
                target_address TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                probe_type TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency_ms REAL,
                details_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cycle_summaries (
                cycle_id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                gateway_ok INTEGER NOT NULL,
                upstream_ok INTEGER NOT NULL,
                internet_icmp_ok INTEGER NOT NULL,
                dns_ok INTEGER NOT NULL,
                http_ok INTEGER NOT NULL,
                classification TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_probe_results_ts ON probe_results(ts);
            CREATE INDEX IF NOT EXISTS idx_probe_results_cycle ON probe_results(cycle_id);
            CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);
            """
        )
        self.conn.commit()

    def upsert_device(
        self,
        *,
        name: str,
        address: str,
        mac_address: str | None,
        kind: str,
        source: str,
        seen_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO devices (name, address, mac_address, kind, source, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(address, source) DO UPDATE SET
                name=excluded.name,
                mac_address=COALESCE(excluded.mac_address, devices.mac_address),
                kind=excluded.kind,
                last_seen=excluded.last_seen
            """,
            (name, address, mac_address, kind, source, seen_at, seen_at),
        )
        self.conn.commit()

    def insert_probe_results(self, records: list[ProbeRecord]) -> None:
        self.conn.executemany(
            """
            INSERT INTO probe_results (
                ts, cycle_id, target_name, target_address, target_kind, probe_type,
                success, latency_ms, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.ts,
                    record.cycle_id,
                    record.target_name,
                    record.target_address,
                    record.target_kind,
                    record.probe_type,
                    int(record.success),
                    record.latency_ms,
                    json.dumps(record.details, sort_keys=True),
                )
                for record in records
            ],
        )
        self.conn.commit()

    def insert_cycle_summary(
        self,
        *,
        cycle_id: str,
        ts: str,
        gateway_ok: bool,
        upstream_ok: bool,
        internet_icmp_ok: bool,
        dns_ok: bool,
        http_ok: bool,
        classification: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO cycle_summaries (
                cycle_id, ts, gateway_ok, upstream_ok, internet_icmp_ok, dns_ok, http_ok, classification
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                ts,
                int(gateway_ok),
                int(upstream_ok),
                int(internet_icmp_ok),
                int(dns_ok),
                int(http_ok),
                classification,
            ),
        )
        self.conn.commit()

    def get_discovered_devices(self) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT name, address, mac_address, kind, source, last_seen
            FROM devices
            WHERE source = 'discovery'
            ORDER BY address
            """
        )
        return list(cur.fetchall())

    def get_recent_cycles(self, limit: int = 20) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT ts, classification, gateway_ok, upstream_ok, internet_icmp_ok, dns_ok, http_ok
            FROM cycle_summaries
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        )
        return list(cur.fetchall())

    def get_recent_incidents(self, limit: int = 20) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT ts, classification, gateway_ok, upstream_ok, internet_icmp_ok, dns_ok, http_ok
            FROM cycle_summaries
            WHERE classification != 'healthy'
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        )
        return list(cur.fetchall())

    def get_latest_probe_results(self, cycle_limit: int = 1) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT pr.ts, pr.target_name, pr.target_address, pr.target_kind, pr.probe_type,
                   pr.success, pr.latency_ms, pr.details_json
            FROM probe_results pr
            WHERE pr.cycle_id IN (
                SELECT cycle_id
                FROM cycle_summaries
                ORDER BY ts DESC
                LIMIT ?
            )
            ORDER BY pr.ts DESC, pr.target_kind, pr.target_name, pr.probe_type
            """,
            (cycle_limit,),
        )
        return list(cur.fetchall())

    def get_discovered_devices_recent(self, limit: int = 50) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT name, address, mac_address, kind, source, first_seen, last_seen
            FROM devices
            WHERE source = 'discovery'
            ORDER BY last_seen DESC, address
            LIMIT ?
            """,
            (limit,),
        )
        return list(cur.fetchall())
