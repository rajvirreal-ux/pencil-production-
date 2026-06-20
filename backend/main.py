"""
FastAPI application — serves the HMI, REST control endpoints, WebSocket,
and wires the simulation engine to InfluxDB Cloud.
"""
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

import backend.config as cfg
from backend.simulation import ProductionLine
from backend.influx_writer import InfluxWriter

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app     = FastAPI(title="Pencil Production Line HMI")
FRONTEND = Path(__file__).parent.parent / "frontend"

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

# ── Globals ──────────────────────────────────────────────────────────────────

line   = ProductionLine(
    cycle_time_s       = cfg.CYCLE_TIME_S,
    defect_rates       = (
        cfg.DEFECT_RATE_S1,
        cfg.DEFECT_RATE_S2,
        cfg.DEFECT_RATE_S3,
        cfg.DEFECT_RATE_S4,
    ),
    overheat_prob      = cfg.OVERHEAT_PROB,
    overheat_limit     = cfg.OVERHEAT_TEMP_LIMIT,
    maintenance_interval = cfg.MAINTENANCE_INTERVAL,
)

influx = InfluxWriter(
    url    = cfg.INFLUX_URL,
    org    = cfg.INFLUX_ORG,
    token  = cfg.INFLUX_TOKEN,
    bucket = cfg.INFLUX_BUCKET,
)

_ws_clients: set[WebSocket] = set()


# ── Simulation callbacks ──────────────────────────────────────────────────────

async def _broadcast(snapshot: dict) -> None:
    """Push a JSON snapshot to every connected WebSocket client."""
    if not _ws_clients:
        return
    payload = json.dumps(snapshot)
    dead: set[WebSocket] = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def _write_influx(snapshot: dict) -> None:
    await influx.write_snapshot(snapshot)


line._on_tick  = _broadcast
line._on_write = _write_influx


# ── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(line.run_loop())
    log.info("Production line simulation started.")


@app.on_event("shutdown")
async def _shutdown() -> None:
    influx.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "influx_sync": influx.last_status,
        "influx_error": influx.last_error or None,
        "machine_state": line.machine_state.name,
    }


@app.get("/api/state")
async def get_state():
    return JSONResponse(line.snapshot())


@app.post("/api/start")
async def api_start():
    ok = line.start()
    return {"success": ok, "machine_state": line.machine_state.name}


@app.post("/api/stop")
async def api_stop():
    ok = line.stop()
    return {"success": ok, "machine_state": line.machine_state.name}


@app.post("/api/pause")
async def api_pause():
    ok = line.pause()
    return {"success": ok, "machine_state": line.machine_state.name}


@app.post("/api/reset")
async def api_reset():
    ok = line.reset()
    return {"success": ok, "machine_state": line.machine_state.name}


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    # Send current state immediately on connect
    try:
        await ws.send_text(json.dumps(line.snapshot()))
        while True:
            # Keep socket alive; data flows from the simulation push
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)
