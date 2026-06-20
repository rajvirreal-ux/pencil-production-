"""
Provisions Grafana Cloud (idempotent):
  1. Creates / updates the InfluxDB Cloud datasource.
  2. Imports production_line_dashboard.json, wired to that datasource.

Run once after verify_influx.py passes.
Usage:  python scripts/setup_grafana.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

try:
    import backend.config as cfg
except EnvironmentError as exc:
    print(f"[FAIL] .env incomplete:\n{exc}")
    sys.exit(1)

import requests

BASE    = cfg.GRAFANA_URL.rstrip("/")
HEADERS = {
    "Authorization": f"Bearer {cfg.GRAFANA_TOKEN}",
    "Content-Type":  "application/json",
}
DS_NAME = "InfluxDB Cloud (pencil-line)"


def _req(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{BASE}{path}"
    r   = requests.request(method, url, headers=HEADERS, timeout=30, **kwargs)
    if not r.ok:
        print(f"[ERROR] {method} {url} → {r.status_code}: {r.text}")
        sys.exit(1)
    return r


# ── 1. Datasource ────────────────────────────────────────────────────────────

ds_payload = {
    "name":   DS_NAME,
    "type":   "influxdb",
    "access": "proxy",
    "url":    cfg.INFLUX_URL,
    "jsonData": {
        "version":       "Flux",
        "organization":  cfg.INFLUX_ORG,
        "defaultBucket": cfg.INFLUX_BUCKET,
        "tlsSkipVerify": False,
    },
    "secureJsonData": {
        "token": cfg.INFLUX_TOKEN,
    },
}

# Check if datasource already exists
r = requests.get(f"{BASE}/api/datasources/name/{requests.utils.quote(DS_NAME)}", headers=HEADERS, timeout=15)
if r.status_code == 200:
    ds_id  = r.json()["id"]
    ds_uid = r.json()["uid"]
    print(f"[INFO] Datasource '{DS_NAME}' already exists (id={ds_id}), updating…")
    _req("PUT", f"/api/datasources/{ds_id}", json=ds_payload)
    print("[OK]  Datasource updated.")
else:
    resp   = _req("POST", "/api/datasources", json=ds_payload)
    ds_id  = resp.json()["datasource"]["id"]
    ds_uid = resp.json()["datasource"]["uid"]
    print(f"[OK]  Datasource created (id={ds_id}, uid={ds_uid}).")

# Re-fetch to get definitive uid
r = requests.get(f"{BASE}/api/datasources/{ds_id}", headers=HEADERS, timeout=15)
ds_uid = r.json()["uid"]

# ── 2. Dashboard import ───────────────────────────────────────────────────────

dashboard_path = Path(__file__).parent.parent / "grafana" / "production_line_dashboard.json"
dashboard      = json.loads(dashboard_path.read_text(encoding="utf-8"))

# Wire the __inputs datasource reference to the real uid
inputs = [
    {
        "name":     inp["name"],
        "type":     "datasource",
        "pluginId": "influxdb",
        "value":    ds_uid,
    }
    for inp in dashboard.get("__inputs", [])
]

import_payload = {
    "dashboard": dashboard,
    "overwrite":  True,
    "inputs":     inputs,
    "folderId":   0,
}

resp = _req("POST", "/api/dashboards/import", json=import_payload)
slug = resp.json().get("slug", "")
url  = f"{BASE}/d/{resp.json().get('uid', '')}/{slug}"
print(f"[OK]  Dashboard imported.")
print(f"\nOpen your Grafana dashboard:\n  {url}\n")
print("Click 'Start' in the HMI and you should see live data within a few seconds.")
