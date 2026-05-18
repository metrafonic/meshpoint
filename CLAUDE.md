# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Lint
python -m ruff check src/ tests/

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_auth_service.py -v

# Run with filter
python -m pytest tests/ -k "test_login" -v

# Install (Raspberry Pi only)
sudo bash scripts/install.sh
```

CI runs Python 3.12, installs `requirements.txt` plus `ruff pytest pytest-asyncio httpx`, then runs lint and tests. Crypto and decoder tests are intentionally skipped in CI due to binary dependencies — do not be surprised if those tests are missing from CI runs.

## Architecture

Meshpoint is a Meshtastic base station backend (FastAPI) + browser dashboard (vanilla JS). It captures LoRa packets from hardware, decodes them, persists to SQLite, and streams updates to clients over WebSocket.

### Data flow

```
Hardware (SX1302 concentrator / Meshtastic serial / MeshCore USB)
  → CaptureCoordinator (src/coordinator.py)
  → Decoder / PacketRouter (src/decode/)
  → SQLite repositories (src/storage/)
  → WebSocket broadcast + REST API (src/api/)
  → Frontend dashboard (frontend/)
```

`PipelineCoordinator` in [src/coordinator.py](src/coordinator.py) is the main wiring point — it instantiates and connects all subsystems during FastAPI lifespan startup.

### Key modules

| Path | Role |
|---|---|
| `src/api/server.py` | FastAPI app, lifespan, WebSocket handler |
| `src/coordinator.py` | Wires capture → decode → store → broadcast |
| `src/capture/` | Packet sources: concentrator, serial, MeshCore USB, mock |
| `src/decode/` | Meshtastic & MeshCore decoders, AES crypto, 14 portnum handlers |
| `src/storage/` | SQLite via aiosqlite; repos for packets, nodes, telemetry, messages |
| `src/relay/` | Relay manager + MQTT publisher (relay TX is EXPERIMENTAL) |
| `src/transmit/` | TX service, NodeInfo broadcaster, outgoing message handling |
| `src/api/routes/` | 16 FastAPI route modules |
| `src/api/auth/` | JWT sessions, first-run setup, bcrypt password hashing, lockout |
| `src/analytics/` | Traffic, signal, network-map stats |
| `src/cli/` | `meshpoint` CLI commands (setup wizard, report, status) |
| `frontend/js/` | 21 vanilla-JS modules (map, messaging, radio config, WebSocket client) |

### Authentication

The web UI is JWT-gated. On first run there are no credentials — the user must hit `/setup` to create the admin password. After that, `POST /api/auth/login` issues a short-lived JWT. WebSocket connections authenticate via a token in the query string; a wrong/missing token causes a close with code 4401, which the frontend watches for to redirect to login.

### Configuration

All runtime config lives in `config/default.yaml` (or a user-provided YAML). Key sections: `radio`, `meshtastic` (PSKs), `meshcore`, `capture` (which sources are active), `storage`, `dashboard`, `relay` (EXPERIMENTAL), `upstream` (Meshradar cloud), `transmit`, `web_auth`, `mqtt`.

### Frontend

Single-page app served from `frontend/`. No build step — plain HTML/CSS/JS with Leaflet (map), Chart.js (analytics), and WebSocket for live updates. Follow `docs/DESIGN-SYSTEM.md` for any UI changes.

## Important constraints

- **Relay TX is EXPERIMENTAL** — changes to `src/relay/` and `src/transmit/` require extra care and clear PR notes on hardware/region tested.
- **Radio/protocol changes** (decode/, capture/, transmit/) need hardware testing; CI cannot validate these end-to-end.
- **Frontend changes** must conform to `docs/DESIGN-SYSTEM.md`.
- Target platform is Raspberry Pi 4 aarch64 (64-bit OS). Do not introduce x86-only or 32-bit-only dependencies.
- PRs are squash-merged; keep branches rebased on `main` with no merge commits.
