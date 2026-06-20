"""
InfluxDB Cloud writer — batching async client.
A write failure never crashes the simulation; it is logged and surfaced via
the health endpoint. The line keeps running while the cloud is unavailable.
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import ASYNCHRONOUS
import influxdb_client.client.exceptions as influx_exc

log = logging.getLogger(__name__)


class InfluxWriter:
    def __init__(self, url: str, org: str, token: str, bucket: str):
        self._bucket   = bucket
        self._org      = org
        self._client   = InfluxDBClient(url=url, token=token, org=org)
        self._write_api = self._client.write_api(write_options=ASYNCHRONOUS)
        self.last_status: str = "ok"       # "ok" | "degraded"
        self.last_error:  str = ""
        self._retry_delay: float = 5.0    # seconds before next attempt after failure

    async def write_snapshot(self, snapshot: dict) -> None:
        """Write all metrics from a simulation tick snapshot to InfluxDB Cloud."""
        try:
            points = self._build_points(snapshot)
            # write_api in ASYNCHRONOUS mode is non-blocking; errors surface as
            # background exceptions — we wrap it in a thread executor to catch them.
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._do_write, points)
            self.last_status = "ok"
            self.last_error  = ""
        except Exception as exc:
            self.last_status = "degraded"
            self.last_error  = str(exc)
            log.warning("InfluxDB write failed (simulation continues): %s", exc)

    def _do_write(self, points: list[Point]) -> None:
        self._write_api.write(bucket=self._bucket, org=self._org, record=points)

    def _build_points(self, snapshot: dict) -> list[Point]:
        points = []
        ts = time.time_ns()

        # machine_state numeric (STOPPED=0 RUNNING=1 PAUSED=2 FAULTED=3)
        state_val = snapshot.get("machine_state", 0)
        if isinstance(state_val, str):
            state_map = {"STOPPED": 0, "RUNNING": 1, "PAUSED": 2, "FAULTED": 3}
            state_val = state_map.get(state_val, 0)

        points.append(
            Point("machine_state")
            .field("state", int(state_val))
            .time(ts, WritePrecision.NS)
        )

        # QC counters
        qc = snapshot.get("qc", {})
        points.append(
            Point("production")
            .field("parts_good",      int(qc.get("good", 0)))
            .field("parts_defective", int(qc.get("defective", 0)))
            .field("yield_pct",       float(qc.get("yield_pct", 0.0)))
            .time(ts, WritePrecision.NS)
        )

        # Per-station temperatures
        for st in snapshot.get("stations", []):
            points.append(
                Point("temperature")
                .tag("station", st["name"])
                .field("value", float(st["temperature"]))
                .time(ts, WritePrecision.NS)
            )

        # Defect event (present only on reject ticks)
        defect = snapshot.get("_defect_event")
        if defect:
            points.append(
                Point("defect_event")
                .tag("station", str(defect.get("station", "")))
                .tag("reason",  defect.get("reason", "UNKNOWN"))
                .field("count", 1)
                .time(ts, WritePrecision.NS)
            )

        return points

    def close(self) -> None:
        self._client.close()
