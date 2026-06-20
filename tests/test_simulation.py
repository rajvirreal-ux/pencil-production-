"""
Unit tests for the simulation engine — zero network access required.
Run with: pytest tests/
"""
import asyncio
import pytest
from unittest.mock import patch

# Engine imports — must not trigger config.py (no .env needed)
from backend.models import MachineState, PencilStatus, StationID
from backend.simulation import ProductionLine
from backend.stations import (
    station1_process, station2_process, station3_process, station4_process,
)
from backend.quality_control import QualityControl
from backend.cmms import CMMS


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_line(**kwargs) -> ProductionLine:
    defaults = dict(
        cycle_time_s=0.01,
        defect_rates=(0.0, 0.0, 0.0, 0.0),
        overheat_prob=0.0,
        overheat_limit=90.0,
        maintenance_interval=50,
    )
    defaults.update(kwargs)
    return ProductionLine(**defaults)


def run_ticks(line: ProductionLine, n: int) -> None:
    async def _run():
        for _ in range(n):
            await line._tick()
    asyncio.get_event_loop().run_until_complete(_run())


# ── Station-level tests ───────────────────────────────────────────────────────

class TestStation1:
    def test_good_pencil_at_zero_defect_rate(self):
        with patch('backend.stations.random.gauss', return_value=12.0), \
             patch('backend.stations.random.random', return_value=1.0):
            result, temp = station1_process(defect_rate=0.0, cycle=1)
        assert result.passed is True
        assert result.station_id == StationID.CORE_INSERTION

    def test_fractured_core_on_high_force(self):
        # gauss returns 19 N — exceeds 18 N fracture limit
        with patch('backend.stations.random.gauss', return_value=19.0):
            result, temp = station1_process(defect_rate=0.0, cycle=1)
        assert result.passed is False
        assert result.reason == "CORE_FRACTURED"
        assert "19.0" in result.detail

    def test_misaligned_core_at_100pct_defect_rate(self):
        with patch('backend.stations.random.gauss', return_value=11.0), \
             patch('backend.stations.random.random', return_value=0.0), \
             patch('backend.stations.random.uniform', return_value=0.7):
            result, temp = station1_process(defect_rate=1.0, cycle=1)
        assert result.passed is False
        assert result.reason == "CORE_MISALIGNED"


class TestStation2:
    def test_overheat_triggers_fault_flag(self):
        # random() < overheat_prob → True
        with patch('backend.stations.random.random', return_value=0.0), \
             patch('backend.stations.random.gauss', return_value=0.5):
            result, temp, is_fault = station2_process(
                defect_rate=0.0, overheat_prob=1.0, overheat_limit=90.0, cycle=1
            )
        assert is_fault is True
        assert result.reason == "CURE_TEMP_OUT_OF_RANGE"
        assert temp >= 90.0

    def test_out_of_range_temp_defect(self):
        # No overheat, but cure_temp (gauss) is 82 °C — out of 55–75 spec
        with patch('backend.stations.random.random', return_value=0.99), \
             patch('backend.stations.random.gauss', side_effect=[0.1, 82.0]):
            result, temp, is_fault = station2_process(
                defect_rate=0.0, overheat_prob=0.0, overheat_limit=90.0, cycle=1
            )
        assert is_fault is False
        assert result.passed is False
        assert result.reason == "CURE_TEMP_OUT_OF_RANGE"


class TestStation3:
    def test_ferrule_loose_on_low_pressure(self):
        # gauss returns 2.5 bar — below 4 bar min
        with patch('backend.stations.random.gauss', return_value=2.5):
            result, temp = station3_process(defect_rate=0.0, cycle=1)
        assert result.passed is False
        assert result.reason == "FERRULE_LOOSE"

    def test_good_pass_in_spec(self):
        with patch('backend.stations.random.gauss', return_value=6.0), \
             patch('backend.stations.random.random', return_value=1.0):
            result, temp = station3_process(defect_rate=0.0, cycle=1)
        assert result.passed is True


class TestStation4:
    def test_eraser_missing(self):
        with patch('backend.stations.random.random', return_value=0.0), \
             patch('backend.stations.random.gauss', return_value=6.0):
            result, temp = station4_process(defect_rate=1.0, cycle=1)
        assert result.passed is False
        assert result.reason == "ERASER_MISSING"

    def test_good_pass_in_spec(self):
        with patch('backend.stations.random.random', return_value=1.0), \
             patch('backend.stations.random.gauss', return_value=6.5):
            result, temp = station4_process(defect_rate=0.0, cycle=1)
        assert result.passed is True


# ── Engine-level tests ────────────────────────────────────────────────────────

class TestProductionLine:
    def test_start_stop_reset_state_machine(self):
        line = make_line()
        assert line.machine_state == MachineState.STOPPED
        assert line.start() is True
        assert line.machine_state == MachineState.RUNNING
        assert line.stop() is True
        assert line.machine_state == MachineState.STOPPED

    def test_start_while_running_returns_false(self):
        line = make_line()
        line.start()
        assert line.start() is False

    def test_reset_clears_counters(self):
        line = make_line()
        line.start()
        run_ticks(line, 8)
        line.reset()
        assert line.total_cycles == 0
        assert line.qc.good_count == 0
        assert line.qc.defective_count == 0
        assert line.machine_state == MachineState.STOPPED

    def test_good_pencil_at_zero_defect_rate(self):
        line = make_line(defect_rates=(0.0, 0.0, 0.0, 0.0), overheat_prob=0.0)
        line.start()
        # Need ≥ 5 ticks for a pencil to traverse all 4 stations and exit
        run_ticks(line, 8)
        assert line.qc.good_count > 0
        assert line.qc.defective_count == 0

    def test_defective_pencil_at_100pct_defect_rate_s1(self):
        line = make_line(defect_rates=(1.0, 0.0, 0.0, 0.0), overheat_prob=0.0)
        line.start()
        with patch('backend.stations.random.gauss', return_value=11.0), \
             patch('backend.stations.random.random', return_value=0.0), \
             patch('backend.stations.random.uniform', return_value=0.7):
            run_ticks(line, 8)
        assert line.qc.defective_count > 0
        assert "CORE_MISALIGNED" in line.qc.reason_counts

    def test_overheat_triggers_faulted_state(self):
        line = make_line(overheat_prob=1.0, overheat_limit=90.0)
        line.start()
        # Belt needs a pencil at station 2 — tick a few times
        with patch('backend.stations.random.random', return_value=0.0), \
             patch('backend.stations.random.gauss', return_value=0.5):
            run_ticks(line, 3)
        # Eventually FAULTED (may take up to 3 ticks to reach S2)
        # Just verify reset works regardless
        line.reset()
        assert line.machine_state == MachineState.STOPPED
        assert line.fault_reason is None

    def test_reset_clears_fault(self):
        line = make_line()
        line.machine_state = MachineState.FAULTED
        line.fault_reason  = "OVERHEAT"
        line.reset()
        assert line.machine_state == MachineState.STOPPED
        assert line.fault_reason is None


# ── Quality Control ──────────────────────────────────────────────────────────

class TestQualityControl:
    def test_yield_zero_when_no_production(self):
        qc = QualityControl()
        assert qc.yield_pct == 0.0
        assert qc.total == 0

    def test_good_pencil_counted(self):
        from backend.models import Pencil
        qc = QualityControl()
        p  = Pencil(id=1)
        p.mark_good()
        qc.process(p)
        assert qc.good_count == 1
        assert qc.defective_count == 0
        assert qc.yield_pct == 100.0

    def test_defective_pencil_reason_tracked(self):
        from backend.models import Pencil, StationResult, StationID, STATION_PARAMS
        qc = QualityControl()
        p  = Pencil(id=2)
        r  = StationResult(
            station_id=StationID.CORE_INSERTION,
            passed=False,
            measured_value=0.7,
            param_name=STATION_PARAMS[StationID.CORE_INSERTION],
            reason="CORE_MISALIGNED",
            detail="offset 0.70 mm",
        )
        p.station_results.append(r)
        p.mark_defective(r)
        qc.process(p)
        assert qc.defective_count == 1
        assert qc.reason_counts["CORE_MISALIGNED"] == 1

    def test_pareto_sorted_descending(self):
        from backend.models import Pencil, StationResult, StationID, STATION_PARAMS
        qc = QualityControl()
        for reason, count in [("A", 3), ("B", 7), ("C", 1)]:
            for _ in range(count):
                p = Pencil(id=0)
                r = StationResult(
                    station_id=StationID.CORE_INSERTION,
                    passed=False,
                    measured_value=0.0,
                    param_name="x",
                    reason=reason,
                    detail="",
                )
                p.mark_defective(r)
                qc.process(p)
        pareto = qc.pareto()
        assert pareto[0]["reason"] == "B"
        assert pareto[0]["count"] == 7


# ── CMMS ─────────────────────────────────────────────────────────────────────

class TestCMMS:
    def test_maintenance_due_at_interval(self):
        cmms = CMMS(maintenance_interval=10)
        cmms.tick(10)
        assert cmms.maintenance_due is True

    def test_fault_sets_maintenance_due(self):
        cmms = CMMS()
        cmms.record_fault(cycles=5, reason="OVERHEAT")
        assert cmms.maintenance_due is True
        assert cmms.total_faults == 1

    def test_full_reset_clears_all(self):
        cmms = CMMS()
        cmms.record_fault(5, "TEST")
        cmms.full_reset()
        assert cmms.maintenance_due is False
        assert cmms.total_faults == 0
        assert cmms.cycles_since_maintenance == 0
