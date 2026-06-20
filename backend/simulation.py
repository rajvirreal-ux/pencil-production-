"""
Production-line engine — pure asyncio state machine, fully decoupled from
FastAPI and InfluxDB so it can be unit-tested without any network access.
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Awaitable

from backend.models import (
    MachineState, StationID, StationState, Pencil, PencilStatus, STATION_NAMES,
)
from backend.stations import (
    station1_process, station2_process, station3_process, station4_process,
)
from backend.quality_control import QualityControl
from backend.cmms import CMMS


# ── Per-station live snapshot ────────────────────────────────────────────────

@dataclass
class StationSnapshot:
    id: int
    name: str
    state: StationState = StationState.IDLE
    temperature: float = 22.0
    last_value: float = 0.0
    param_name: str = ""
    current_pencil_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "temperature": round(self.temperature, 1),
            "last_value": round(self.last_value, 2),
            "param_name": self.param_name,
            "current_pencil_id": self.current_pencil_id,
        }


# ── Production line engine ───────────────────────────────────────────────────

class ProductionLine:
    def __init__(
        self,
        cycle_time_s: float = 1.5,
        defect_rates: tuple[float, ...] = (0.05, 0.07, 0.04, 0.03),
        overheat_prob: float = 0.008,
        overheat_limit: float = 90.0,
        maintenance_interval: int = 50,
    ):
        self.cycle_time_s    = cycle_time_s
        self.defect_rates    = defect_rates
        self.overheat_prob   = overheat_prob
        self.overheat_limit  = overheat_limit

        self.machine_state   = MachineState.STOPPED
        self.fault_reason: Optional[str] = None
        self.total_cycles    = 0
        self._next_pencil_id = 1

        # Conveyor belt: slot per station (None = empty)
        self._belt: list[Optional[Pencil]] = [None, None, None, None]

        self.stations = [
            StationSnapshot(1, "Core Insertion",   param_name="insertion_force_N"),
            StationSnapshot(2, "Body Bonding",     param_name="cure_temp_C"),
            StationSnapshot(3, "Ferrule Crimping", param_name="crimp_pressure_bar"),
            StationSnapshot(4, "Eraser Insertion", param_name="insertion_depth_mm"),
        ]

        self.qc   = QualityControl()
        self.cmms = CMMS(maintenance_interval=maintenance_interval)

        # Callbacks set by main.py
        self._on_tick:   Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_write:  Optional[Callable[[dict], Awaitable[None]]] = None

        self._task: Optional[asyncio.Task] = None

    # ── Control API ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        if self.machine_state in (MachineState.STOPPED, MachineState.PAUSED):
            self.machine_state = MachineState.RUNNING
            return True
        return False

    def stop(self) -> bool:
        if self.machine_state == MachineState.RUNNING:
            self.machine_state = MachineState.STOPPED
            for s in self.stations:
                s.state = StationState.IDLE
                s.current_pencil_id = None
            return True
        return False

    def pause(self) -> bool:
        if self.machine_state == MachineState.RUNNING:
            self.machine_state = MachineState.PAUSED
            return True
        return False

    def reset(self) -> bool:
        """Clears fault, counters, belt — brings line back to STOPPED."""
        self.machine_state  = MachineState.STOPPED
        self.fault_reason   = None
        self.total_cycles   = 0
        self._next_pencil_id = 1
        self._belt          = [None, None, None, None]
        for s in self.stations:
            s.state              = StationState.IDLE
            s.current_pencil_id  = None
        self.qc.reset()
        self.cmms.full_reset()
        return True

    # ── Run loop ─────────────────────────────────────────────────────────────

    async def run_loop(self) -> None:
        while True:
            if self.machine_state == MachineState.RUNNING:
                await self._tick()
            await asyncio.sleep(self.cycle_time_s)

    async def _tick(self) -> None:
        self.total_cycles += 1
        cycle = self.total_cycles

        # ── Advance belt right-to-left so each station processes its pencil ─
        # Station 4 first, then 3, 2, 1 (so we don't overwrite before reading)
        completed_pencil: Optional[Pencil] = None

        # ── S4 → exit ────────────────────────────────────────────────────────
        p4 = self._belt[3]
        if p4 is not None:
            result, temp = station4_process(self.defect_rates[3], cycle)
            p4.station_results.append(result)
            self.stations[3].state       = StationState.REJECT if not result.passed else StationState.PASS
            self.stations[3].temperature = temp
            self.stations[3].last_value  = result.measured_value
            if not result.passed:
                p4.mark_defective(result)
            else:
                p4.mark_good()
            completed_pencil = p4
            self._belt[3]    = None
            self.stations[3].current_pencil_id = None

        # ── S3 → S4 ──────────────────────────────────────────────────────────
        p3 = self._belt[2]
        if p3 is not None:
            result, temp = station3_process(self.defect_rates[2], cycle)
            p3.station_results.append(result)
            self.stations[2].state       = StationState.REJECT if not result.passed else StationState.PASS
            self.stations[2].temperature = temp
            self.stations[2].last_value  = result.measured_value
            if not result.passed:
                p3.mark_defective(result)
            self._belt[3]    = p3
            self._belt[2]    = None
            self.stations[3].current_pencil_id = p3.id
            self.stations[2].current_pencil_id = None

        # ── S2 → S3 ──────────────────────────────────────────────────────────
        p2 = self._belt[1]
        if p2 is not None:
            result, temp, is_overheat = station2_process(
                self.defect_rates[1], self.overheat_prob, self.overheat_limit, cycle
            )
            p2.station_results.append(result)
            self.stations[1].temperature = temp
            self.stations[1].last_value  = result.measured_value

            if is_overheat:
                # Hard fault — stop the whole line
                p2.mark_defective(result)
                self.machine_state = MachineState.FAULTED
                self.fault_reason  = f"Overheat @ Body Bonding: {temp:.1f} °C (limit {self.overheat_limit} °C)"
                self.cmms.record_fault(cycle, self.fault_reason)
                self.stations[1].state = StationState.REJECT
                # Don't advance belt — fault clears on Reset
            else:
                self.stations[1].state = StationState.REJECT if not result.passed else StationState.PASS
                if not result.passed:
                    p2.mark_defective(result)
                self._belt[2]    = p2
                self._belt[1]    = None
                self.stations[2].current_pencil_id = p2.id
                self.stations[1].current_pencil_id = None

        # ── S1 → S2 ──────────────────────────────────────────────────────────
        if self.machine_state == MachineState.RUNNING:
            p1 = self._belt[0]
            if p1 is not None:
                result, temp = station1_process(self.defect_rates[0], cycle)
                p1.station_results.append(result)
                self.stations[0].state       = StationState.REJECT if not result.passed else StationState.PASS
                self.stations[0].temperature = temp
                self.stations[0].last_value  = result.measured_value
                if not result.passed:
                    p1.mark_defective(result)
                self._belt[1]    = p1
                self._belt[0]    = None
                self.stations[1].current_pencil_id = p1.id
                self.stations[0].current_pencil_id = None

            # ── Feed new pencil into S1 ──────────────────────────────────────
            new_pencil = Pencil(id=self._next_pencil_id)
            self._next_pencil_id += 1
            self._belt[0] = new_pencil
            self.stations[0].state            = StationState.PROCESSING
            self.stations[0].current_pencil_id = new_pencil.id

        # ── QC + CMMS ────────────────────────────────────────────────────────
        if completed_pencil is not None:
            self.qc.process(completed_pencil)

        self.cmms.tick(cycle)

        # ── Push snapshot to WebSocket + InfluxDB ────────────────────────────
        snapshot = self.snapshot()
        if self._on_tick:
            await self._on_tick(snapshot)
        if self._on_write and self.machine_state == MachineState.RUNNING:
            await self._on_write(snapshot)
        if completed_pencil is not None and completed_pencil.status == PencilStatus.DEFECTIVE:
            # Also push defect event for InfluxDB tagging
            if self._on_write:
                snapshot["_defect_event"] = {
                    "pencil_id": completed_pencil.id,
                    "station":   completed_pencil.rejecting_station.value if completed_pencil.rejecting_station else 0,
                    "reason":    completed_pencil.reject_reason or "UNKNOWN",
                }
                await self._on_write(snapshot)

    # ── Snapshot ─────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "machine_state":   self.machine_state.name,
            "machine_state_n": self.machine_state.value,
            "fault_reason":    self.fault_reason,
            "total_cycles":    self.total_cycles,
            "stations":        [s.to_dict() for s in self.stations],
            "qc":              self.qc.to_dict(),
            "cmms":            self.cmms.to_dict(),
        }
