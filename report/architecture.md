# Architecture

## System Overview

```
┌─────────────────────── LOCAL MACHINE ──────────────────────────────┐
│                                                                     │
│  ┌──────────┐   WebSocket / REST   ┌─────────────────────────────┐ │
│  │ Browser  │◄─────────────────────│  FastAPI (Uvicorn)          │ │
│  │  HMI     │──── POST /api/start  │  backend/main.py            │ │
│  └──────────┘      /stop /reset    │                             │ │
│                                    │  ┌──────────────────────┐  │ │
│                                    │  │  ProductionLine      │  │ │
│                                    │  │  (simulation.py)     │  │ │
│                                    │  │  asyncio run loop    │  │ │
│                                    │  │  ┌────┬────┬────┬───┐│  │ │
│                                    │  │  │ S1 │ S2 │ S3 │S4 ││  │ │
│                                    │  │  └────┴────┴────┴───┘│  │ │
│                                    │  │  QualityControl CMMS │  │ │
│                                    │  └───────────┬──────────┘  │ │
│                                    │              │ async write  │ │
│                                    │  ┌───────────▼──────────┐  │ │
│                                    │  │  InfluxWriter        │  │ │
│                                    │  │  (influx_writer.py)  │  │ │
│                                    │  └───────────┬──────────┘  │ │
│                                    └──────────────┼─────────────┘ │
└──────────────────────────────────────────────────┼────────────────┘
                                                   │ HTTPS
                    ┌──────────────────────────────▼──────────────────┐
                    │              CLOUD                               │
                    │  ┌─────────────────────┐  ┌──────────────────┐  │
                    │  │  InfluxDB Cloud TSM │  │  Grafana Cloud   │  │
                    │  │  (eu-central-1 AWS) │◄─│  (Flux queries)  │  │
                    │  │  bucket: uni        │  │  dashboard       │  │
                    │  └─────────────────────┘  └──────────────────┘  │
                    └─────────────────────────────────────────────────┘
```

## Data Flow

1. The `ProductionLine` asyncio loop ticks every `CYCLE_TIME_S` seconds.
2. Each tick: stations process pencils → QC records outcome → CMMS updates.
3. The tick snapshot is **broadcast** to all WebSocket clients (instant HMI update).
4. The same snapshot is **queued** to `InfluxWriter`, which flushes asynchronously to InfluxDB Cloud over HTTPS. Write errors are caught and logged; the simulation continues regardless.
5. Grafana Cloud polls InfluxDB Cloud every 5 s via Flux queries and updates the dashboard panels.
6. The user controls the line via the HMI's Start / Stop / Reset buttons (POST requests) or directly via the REST API.

## Component Responsibilities

| File | Responsibility |
|------|----------------|
| `config.py` | Load + validate all env vars; fail fast if missing |
| `models.py` | Pure data types — Pencil, StationResult, enums |
| `stations.py` | Sensor sampling + defect logic per station |
| `simulation.py` | Conveyor state machine, belt advancement, tick loop |
| `quality_control.py` | Pass/reject aggregation, yield %, Pareto |
| `cmms.py` | Maintenance tracking, downtime events |
| `influx_writer.py` | Batched async InfluxDB Cloud writes with retry |
| `main.py` | FastAPI app, WebSocket broadcaster, REST control |
| `frontend/` | Static HMI — no build step |
| `scripts/verify_influx.py` | Pre-flight cloud credential check |
| `scripts/setup_grafana.py` | Idempotent datasource + dashboard provisioning |
