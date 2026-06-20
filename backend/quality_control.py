"""
Quality Control module — centralises pass/reject decisions, holds the reject bin,
computes yield % and a per-reason Pareto.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from backend.models import Pencil, PencilStatus


@dataclass
class QualityControl:
    reject_bin: list[Pencil] = field(default_factory=list)
    good_count: int = 0
    defective_count: int = 0
    reason_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def process(self, pencil: Pencil) -> None:
        if pencil.status == PencilStatus.GOOD:
            self.good_count += 1
        elif pencil.status == PencilStatus.DEFECTIVE:
            self.defective_count += 1
            self.reject_bin.append(pencil)
            if pencil.reject_reason:
                self.reason_counts[pencil.reject_reason] += 1

    def reset(self) -> None:
        self.reject_bin.clear()
        self.good_count = 0
        self.defective_count = 0
        self.reason_counts.clear()

    @property
    def total(self) -> int:
        return self.good_count + self.defective_count

    @property
    def yield_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.good_count / self.total, 1)

    def pareto(self) -> list[dict]:
        """Sorted list of defect reasons, highest first."""
        return sorted(
            [{"reason": k, "count": v} for k, v in self.reason_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

    def recent_rejects(self, n: int = 20) -> list[dict]:
        return [
            {
                "id": p.id,
                "summary": p.reject_summary(),
                "reason": p.reject_reason,
                "detail": p.reject_detail,
                "station": p.rejecting_station.value if p.rejecting_station else None,
            }
            for p in self.reject_bin[-n:][::-1]
        ]

    def to_dict(self) -> dict:
        return {
            "good": self.good_count,
            "defective": self.defective_count,
            "total": self.total,
            "yield_pct": self.yield_pct,
            "pareto": self.pareto(),
            "recent_rejects": self.recent_rejects(),
        }
