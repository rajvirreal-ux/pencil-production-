# Pencil Production Line

A real-time manufacturing simulation of a 4-station wooden pencil assembly line.

**Architecture:** Python app runs **locally**. InfluxDB and Grafana are **cloud-hosted** — connected purely via `.env`. No Docker, no local database/dashboard installation.

---

## Production Line

| Station | Operation | Key parameter | Defect codes |
|---------|-----------|---------------|--------------|
| S1 Core Insertion | Place graphite core | Insertion force (N) | `CORE_MISALIGNED`, `CORE_FRACTURED` |
| S2 Body Bonding | Glue + heat-cure halves | Cure temperature (°C) | `WEAK_BOND`, `BODY_MISALIGNED`, `CURE_TEMP_OUT_OF_RANGE` |
| S3 Ferrule Crimping | Crimp metal ring | Crimp pressure (bar) | `FERRULE_LOOSE`, `FERRULE_NOT_SEATED` |
| S4 Eraser Insertion | Seat eraser plug | Insertion depth (mm) | `ERASER_MISSING`, `ERASER_LOOSE` |

A pencil failing **any** station is flagged `DEFECTIVE` with the exact station + reason + measured value. Pass all four → `GOOD`.

---

## Prerequisites

1. **InfluxDB Cloud (TSM)** — sign up at `cloud2.influxdata.com/signup`. Create org `Srh` and bucket `uni`. Generate an All Access API token.
2. **Grafana Cloud** — create a free stack at `grafana.com`. In your stack, go to Administration → Service Accounts → create an account with Admin role → generate a token.
3. **Python 3.11+** installed locally.

---

## Run it

### 1. Copy and fill in `.env`
```bash
cp .env.example .env
# Open .env and paste your real token values — never commit .env
```

### 2. Create venv and install dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Verify cloud credentials
```bash
python scripts/verify_influx.py
```
This writes a test point and queries it back. Fix any errors before proceeding.

### 4. Provision Grafana (one time)
```bash
python scripts/setup_grafana.py
```
Creates the InfluxDB datasource and imports the dashboard into your Grafana Cloud stack.

### 5. Start the app
```bash
# Windows PowerShell:
.\scripts\run.ps1

# Mac/Linux:
bash scripts/run.sh
```

Open the **HMI**: http://localhost:8000  
Open your **Grafana dashboard**: the URL printed by `setup_grafana.py`

---

## Demo guide

| Action | How |
|--------|-----|
| Start the line | Click **START** in HMI |
| Trigger a fault | Wait — overheat at Body Bonding fires ~1% of cycles. Watch for the red FAULT BANNER. |
| Clear a fault | Click **RESET** |
| See defects | Watch the REJECT FEED panel — each entry shows station + reason + measured value |
| View live Grafana | Open the Grafana URL — temperature, machine state, parts produced, defect Pareto |

---

## Tools used

- **Python 3.11** — simulation engine, FastAPI backend
- **FastAPI + Uvicorn** — REST API + WebSocket
- **influxdb-client** — InfluxDB Cloud (v2 Flux, TSM)
- **InfluxDB Cloud** — time-series metric storage
- **Grafana Cloud** — dashboards, provisioned via HTTP API
- **git / GitHub** — version control + GitHub Pages static site
- **Claude Code (AI)** — code generation (see PROMPTS.md)

---

## File map (rubric)

| Rubric item | Key files |
|-------------|-----------|
| Task 1 — Product + line concept | `report/01_introduction.md`, `report/architecture.md` |
| Task 2 — Backend + defect logic | `backend/stations.py`, `backend/simulation.py`, `backend/models.py` |
| Task 2 — HMI | `frontend/`, `backend/main.py` |
| Task 2 — InfluxDB | `backend/influx_writer.py`, `scripts/verify_influx.py` |
| Task 2 — Grafana | `scripts/setup_grafana.py`, `grafana/production_line_dashboard.json` |
| Task 2 — QC + CMMS | `backend/quality_control.py`, `backend/cmms.py` |
| Task 3 — git evidence | commit history, `.github/workflows/deploy-pages.yml` |
| Task 3 — Static site | `docs/` |
| Task 3 — AI tools | `PROMPTS.md` |
| Task 4 — Conclusion | `report/04_conclusion.md` |
| Tests (no network) | `tests/test_simulation.py` |
