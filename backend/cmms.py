"""
CMMS — Computerised Maintenance Management System.
Tracks cycles since maintenance, triggers maintenance-due alerts,
and logs downtime events.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class MaintenanceEvent:
    timestamp: float
    event_type: str       # "scheduled" | "fault_triggered" | "completed"
    cycles_at_event: int
    note: str = ""


@dataclass
class CMMS:
    maintenance_interval: int = 50   # cycles between scheduled maintenance
    cycles_since_maintenance: int = 0
    maintenance_due: bool = False
    total_faults: int = 0
    downtime_events: list[MaintenanceEvent] = field(default_factory=list)
    fault_start_time: float = 0.0

    def tick(self, cycles: int) -> None:
        """Called each simulation cycle."""
        self.cycles_since_maintenance = cycles % self.maintenance_interval
        if (cycles > 0) and (cycles % self.maintenance_interval == 0):
            self.maintenance_due = True

    def record_fault(self, cycles: int, reason: str) -> None:
        self.total_faults += 1
        self.maintenance_due = True
        self.fault_start_time = time.time()
        self.downtime_events.append(
            MaintenanceEvent(
                timestamp=self.fault_start_time,
                event_type="fault_triggered",
                cycles_at_event=cycles,
                note=reason,
            )
        )

    def record_reset(self, cycles: int) -> None:
        downtime = round(time.time() - self.fault_start_time, 1) if self.fault_start_time else 0.0
        self.downtime_events.append(
            MaintenanceEvent(
                timestamp=time.time(),
                event_type="completed",
                cycles_at_event=cycles,
                note=f"maintenance completed after {downtime}s downtime",
            )
        )
        self.maintenance_due = False
        self.fault_start_time = 0.0

    def full_reset(self) -> None:
        """Called on user Reset — clears cycles counter, clears maintenance flag."""
        self.cycles_since_maintenance = 0
        self.maintenance_due = False
        self.total_faults = 0
        self.fault_start_time = 0.0
        self.downtime_events.clear()

    def to_dict(self) -> dict:
        return {
            "cycles_since_maintenance": self.cycles_since_maintenance,
            "maintenance_interval": self.maintenance_interval,
            "maintenance_due": self.maintenance_due,
            "total_faults": self.total_faults,
            "recent_events": [
                {
                    "type": e.event_type,
                    "cycles": e.cycles_at_event,
                    "note": e.note,
                }
                for e in self.downtime_events[-5:]
            ],
        }
