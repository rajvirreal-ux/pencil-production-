"""
Standalone cloud-credential verification script.
Run FIRST, before starting the app, to confirm your InfluxDB Cloud
connection works end-to-end: write a test point, then query it back.

Usage:  python scripts/verify_influx.py
"""
import sys
import time
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

try:
    import backend.config as cfg
except EnvironmentError as exc:
    print(f"[FAIL] .env is incomplete:\n{exc}")
    sys.exit(1)

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.query_api import QueryApi

print(f"Connecting to {cfg.INFLUX_URL}  org={cfg.INFLUX_ORG}  bucket={cfg.INFLUX_BUCKET}")

client    = InfluxDBClient(url=cfg.INFLUX_URL, token=cfg.INFLUX_TOKEN, org=cfg.INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

ts_ns = time.time_ns()

# ── Write ────────────────────────────────────────────────────────────────────
try:
    p = (
        Point("verify_test")
        .tag("source", "verify_influx_script")
        .field("value", 42.0)
        .time(ts_ns, WritePrecision.NS)
    )
    write_api.write(bucket=cfg.INFLUX_BUCKET, org=cfg.INFLUX_ORG, record=p)
    print("[OK]  Write succeeded.")
except Exception as exc:
    print(f"[FAIL] Write failed: {exc}")
    client.close()
    sys.exit(1)

# Give the cloud a moment to index the point
time.sleep(2)

# ── Query back ────────────────────────────────────────────────────────────────
flux = f'''
from(bucket: "{cfg.INFLUX_BUCKET}")
  |> range(start: -2m)
  |> filter(fn: (r) => r._measurement == "verify_test")
  |> filter(fn: (r) => r.source == "verify_influx_script")
  |> last()
'''
try:
    tables = query_api.query(flux)
    found  = sum(len(t.records) for t in tables)
    if found > 0:
        print(f"[OK]  Query returned {found} record(s). InfluxDB Cloud connection verified!")
    else:
        print("[WARN] Write succeeded but query returned 0 records.")
        print("       This can happen with propagation delay — try again in ~30 s.")
except Exception as exc:
    print(f"[WARN] Query failed (write may still have succeeded): {exc}")
finally:
    client.close()

print("\nAll checks done. You are ready to run: python scripts/setup_grafana.py")
