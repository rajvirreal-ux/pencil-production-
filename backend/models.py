"""
Core domain types: enums, dataclasses, and the Pencil work-item.
No network or config dependencies — safe to import in tests with no .env.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import time


class MachineState(Enum):
    STOPPED  = 0
    RUNNING  = 1
    PAUSED   = 2
    FAULTED  = 3


class StationState(Enum):
    IDLE       = "idle"
    PROCESSING = "processing"
    PASS       = "pass"
    REJECT     = "reject"


class PencilStatus(Enum):
    IN_PROGRESS = "in_progress"
    GOOD        = "good"
    DEFECTIVE   = "defective"


# ── Station identifiers ──────────────────────────────────────────────────────

class StationID(Enum):
    CORE_INSERTION  = 1
    BODY_BONDING    = 2
    FERRULE_CRIMPING = 3
    ERASER_INSERTION = 4


STATION_NAMES = {
    StationID.CORE_INSERTION:   "Core Insertion",
    StationID.BODY_BONDING:     "Body Bonding",
    StationID.FERRULE_CRIMPING: "Ferrule Crimping",
    StationID.ERASER_INSERTION: "Eraser Insertion",
}

STATION_PARAMS = {
    StationID.CORE_INSERTION:   "insertion_force_N",
    StationID.BODY_BONDING:     "cure_temp_C",
    StationID.FERRULE_CRIMPING: "crimp_pressure_bar",
    StationID.ERASER_INSERTION: "insertion_depth_mm",
}


# ── Per-station result ───────────────────────────────────────────────────────

@dataclass
class StationResult:
    station_id:    StationID
    passed:        bool
    measured_value: float        # the sampled parameter value
    param_name:    str           # human-readable parameter name
    reason:        Optional[str] = None   # defect reason code if failed
    detail:        Optional[str] = None   # human-readable explanation


# ── Work item ────────────────────────────────────────────────────────────────

@dataclass
class Pencil:
    id:              int
    created_at:      float = field(default_factory=time.time)
    station_results: list[StationResult] = field(default_factory=list)
    status:          PencilStatus = PencilStatus.IN_PROGRESS
    rejecting_station: Optional[StationID] = None
    reject_reason:   Optional[str] = None
    reject_detail:   Optional[str] = None

    def mark_defective(self, result: StationResult) -> None:
        self.status = PencilStatus.DEFECTIVE
        self.rejecting_station = result.station_id
        self.reject_reason = result.reason
        self.reject_detail = result.detail

    def mark_good(self) -> None:
        self.status = PencilStatus.GOOD

    def reject_summary(self) -> str:
        if self.status != PencilStatus.DEFECTIVE:
            return ""
        name = STATION_NAMES.get(self.rejecting_station, "?")
        return f"REJECT @ {name} — {self.reject_reason}: {self.reject_detail}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "reject_reason": self.reject_reason,
            "reject_detail": self.reject_detail,
            "rejecting_station": self.rejecting_station.value if self.rejecting_station else None,
            "station_results": [
                {
                    "station_id": r.station_id.value,
                    "station_name": STATION_NAMES[r.station_id],
                    "passed": r.passed,
                    "measured_value": round(r.measured_value, 2),
                    "param_name": r.param_name,
                    "reason": r.reason,
                    "detail": r.detail,
                }
                for r in self.station_results
            ],
        }
