"""
Loads and validates all required environment variables at import time.
Fails fast with a descriptive message so the app never starts half-configured.
"""
import os
from dotenv import load_dotenv

load_dotenv()

def _require(name: str, hint: str) -> str:
    val = os.getenv(name, "").strip()
    if not val or val.startswith("paste-your"):
        raise EnvironmentError(
            f"\n  Missing required env var: {name}\n  {hint}\n"
            f"  Copy .env.example → .env and fill in the real value."
        )
    return val

INFLUX_URL    = _require("INFLUX_URL",    "Your InfluxDB Cloud URL (cloud2.influxdata.com region URL)")
INFLUX_ORG    = _require("INFLUX_ORG",    "Your InfluxDB Cloud organisation name (e.g. Srh)")
INFLUX_BUCKET = _require("INFLUX_BUCKET", "Your InfluxDB Cloud bucket name (e.g. uni)")
INFLUX_TOKEN  = _require("INFLUX_TOKEN",  "InfluxDB → Load Data → API Tokens → All Access token")

GRAFANA_URL   = _require("GRAFANA_URL",   "Your Grafana Cloud stack URL (e.g. https://yourname.grafana.net)")
GRAFANA_TOKEN = _require(
    "GRAFANA_SERVICE_ACCOUNT_TOKEN",
    "Grafana → Administration → Service Accounts → service-account token with Admin role",
)

APP_PORT = int(os.getenv("APP_PORT", "8000"))

# ── Simulation tuning knobs ──────────────────────────────────────────────────
CYCLE_TIME_S          = float(os.getenv("CYCLE_TIME_S", "1.5"))   # seconds per conveyor tick
DEFECT_RATE_S1        = float(os.getenv("DEFECT_RATE_S1", "0.05"))
DEFECT_RATE_S2        = float(os.getenv("DEFECT_RATE_S2", "0.07"))
DEFECT_RATE_S3        = float(os.getenv("DEFECT_RATE_S3", "0.04"))
DEFECT_RATE_S4        = float(os.getenv("DEFECT_RATE_S4", "0.03"))
OVERHEAT_PROB         = float(os.getenv("OVERHEAT_PROB", "0.008"))  # per tick at S2
OVERHEAT_TEMP_LIMIT   = float(os.getenv("OVERHEAT_TEMP_LIMIT", "90.0"))  # °C
MAINTENANCE_INTERVAL  = int(os.getenv("MAINTENANCE_INTERVAL", "50"))     # cycles
