# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

unifi-doctor is a CLI diagnostic and optimization tool for UniFi networks (targeting UDM Pro). It connects to the UniFi local controller API, fetches a live network snapshot, runs analysis modules to detect configuration issues (especially streaming-related), and can recommend/apply channel plans.

## Tech Stack

- Python 3.11+ with Typer (CLI), Rich (output), httpx (async HTTP), Pydantic v2 (models)
- Build backend: Hatchling (PEP 517)
- Package manager: **uv** (not pip/poetry)

## Common Commands

```bash
# Install dependencies (including dev)
uv sync --extra dev

# Run the CLI
uv run unifi-doctor --help

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_rules.py::test_function_name -v

# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Architecture

### Pipeline Flow

`CLI command` → `UniFiClient.fetch_all()` (concurrent async) → `NetworkSnapshot` → `analysis modules` → `Finding[]` + `ChannelPlan[]` → `Rich output / JSON`

### Key Layers

- **`cli.py`** — Typer app with commands: `setup`, `scan`, `clients`, `aps`, `channels`, `apply-plan`, `watch`, `export`. Uses `asyncio.run()` for async calls.
- **`api/client.py`** — `UniFiClient` async context manager (httpx). Cookie-based auth via `/api/auth/login`. `fetch_all()` uses `asyncio.gather()` for concurrent fetching. `NetworkSnapshot` holds all fetched data with property helpers.
- **`api/endpoints.py`** — URL builder functions for UniFi API routes.
- **`models/types.py`** — All Pydantic models. API models use `extra="allow"` to tolerate unknown fields. Diagnostic output uses `Finding` (severity, title, detail, recommendation) and `ChannelPlan`.
- **`analysis/`** — Stateless analysis modules, each exporting `analyze(snapshot, topology) -> list[Finding]`. `rules.py` is the single source of truth for all thresholds/constants.
- **`output/report.py`** — Rich-formatted terminal report. **`output/dashboard.py`** — Live watch mode with `rich.live`.
- **`topology/interview.py`** — Interactive CLI interview for AP physical placement (floor, location, distances).

### Analysis Modules

Each module in `analysis/` is a pure function — no class state:
- `rf.py` — Channel, width, power, interference, neighbor analysis; generates channel plans (returns `tuple[list[Finding], list[ChannelPlan]]`)
- `roaming.py` — Sticky clients, roaming storms, 802.11r/v/k, min RSSI, band steering
- `throughput.py` — PHY rates, legacy devices, mesh backhaul, uplink checks, band ratios
- `settings.py` — UDM settings audit (IDS/IPS, SQM, DPI, DNS, UPnP, DTIM, firmware, PMF)
- `streaming.py` — Streaming device identification by OUI/hostname, per-device signal/band/rate analysis

### Config Storage

User config and topology persist to `~/.unifi-doctor/config.yaml` and `~/.unifi-doctor/topology.yaml`. Env-var overrides: `UNIFI_HOST`, `UNIFI_USER`, `UNIFI_PASS`.

## Conventions

- `from __future__ import annotations` used in all modules
- Ruff: line length 120, rules `E F I N W UP`, target Python 3.11
- pytest with `asyncio_mode = "auto"` (pytest-asyncio)
- All CLI commands support `--verify-ssl`, `--verbose`, and `--json` flags
- JSON output uses Pydantic's `model_dump(mode="json")`
- API endpoint errors are silently swallowed (returns `[]`) to allow partial failures; verbose mode logs these
