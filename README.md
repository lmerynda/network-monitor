# Network Monitor

Small Raspberry Pi daemon for monitoring a home network path and storing probe history in SQLite.

## What It Monitors

- Local gateway, auto-detected from the Pi routing table
- First upstream hop, configurable
- Internet reachability by ICMP, DNS, and HTTP
- Optional extra targets from config
- Discovered LAN devices, stored for reference and optional probing

## Why SQLite

SQLite keeps raw history queryable without introducing a separate service. It is a better fit than JSON logs for long-running incident analysis.

## Requirements

- Python 3.10+
- Linux with `ping` and `ip`
- Raspberry Pi connected to the `ryszardyna` network

## Quick Start

1. Copy [config.example.json](/repos/network-monitor/config.example.json) to `config.json`.
2. Adjust the config if needed.
3. Run:

```bash
python3 -m network_monitor.main --config config.json run
```

The monitor creates the SQLite database on first run.

## Install Bundle

Build a transfer bundle on the source machine:

```bash
./scripts/build-package.sh
```

This creates a tarball in `dist/`.

Install on the Raspberry Pi after copying and unpacking the tarball:

```bash
sudo ./install.sh
```

Or deploy directly over SSH from the source machine:

```bash
./scripts/deploy-over-ssh.sh pi@raspberrypi.local
```

This is interactive by design. `scp`, `ssh`, and remote `sudo` can prompt for passwords.

The installer:

- copies the app to `/opt/network-monitor`
- installs config to `/etc/network-monitor/config.json` if missing
- stores data in `/var/lib/network-monitor`
- installs a `systemd` service
- creates `/usr/local/bin/network-monitor`
- enables and starts the service

## CLI

Show recent cycle summaries:

```bash
python3 -m network_monitor.main --config /etc/network-monitor/config.json status --limit 20
```

Show recent non-healthy cycles:

```bash
python3 -m network_monitor.main --config /etc/network-monitor/config.json incidents --limit 20
```

Show probe rows from the latest cycle:

```bash
python3 -m network_monitor.main --config /etc/network-monitor/config.json probes --cycles 1
```

Show discovered LAN devices:

```bash
python3 -m network_monitor.main --config /etc/network-monitor/config.json discovered --limit 50
```

## Default Behavior

- Probe interval: 10 seconds
- Discovery interval: 5 minutes
- Discovery method: `auto` (`nmap` if present, otherwise ping scan)
- Gateway fallback: `192.168.1.254`
- First upstream hop: `107.220.56.1`
- Internet ICMP targets: `1.1.1.1`, `8.8.8.8`
- DNS names: `google.com`, `cloudflare.com`
- HTTP URL: `https://connectivitycheck.gstatic.com/generate_204`

## Nmap Discovery

If `nmap` is installed on the Pi, the monitor automatically prefers `nmap -sn` when `"discovery_method": "auto"`.
It falls back to the built-in ping scan if `nmap` is unavailable.

## Systemd

The installed service runs from [systemd/network-monitor.service](/repos/network-monitor/systemd/network-monitor.service).
