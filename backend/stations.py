"""
4-station production line — each station samples a realistic sensor value,
checks it against tolerance, and returns a StationResult.
All randomness is seeded via the standard library — no network, no config import.
"""
from __future__ import annotations
import random
import math
from backend.models import (
    StationID, StationResult, STATION_PARAMS,
    MachineState,
)


# ── Shared helpers ───────────────────────────────────────────────────────────

def _normal(mean: float, std: float) -> float:
    return random.gauss(mean, std)


# ── Station 1 — Core Insertion ───────────────────────────────────────────────
# Key parameter: insertion force (N), spec 8–16 N.
# Defects: CORE_MISALIGNED (value not sampled but geometric error) or
#          CORE_FRACTURED (force > 18 N).

FORCE_MEAN   = 11.5   # N  — nominal in-spec centre
FORCE_STD    = 2.0
FORCE_LO     = 8.0
FORCE_HI     = 16.0
FORCE_FRACTURE = 18.0  # hard upper limit → fracture

def _temp_s1(cycle: int) -> float:
    """Idle station; slight drift due to friction heat."""
    return 24.0 + 0.5 * math.sin(cycle * 0.1) + random.gauss(0, 0.3)


def station1_process(defect_rate: float, cycle: int) -> tuple[StationResult, float]:
    """Returns (result, temperature)."""
    force = _normal(FORCE_MEAN, FORCE_STD)
    temp  = _temp_s1(cycle)

    if force > FORCE_FRACTURE:
        result = StationResult(
            station_id=StationID.CORE_INSERTION,
            passed=False,
            measured_value=force,
            param_name=STATION_PARAMS[StationID.CORE_INSERTION],
            reason="CORE_FRACTURED",
            detail=f"{force:.1f} N (limit 18 N — core fractured)",
        )
    elif random.random() < defect_rate:
        # Geometric misalignment — sampled in-spec force but wrong placement
        offset = random.uniform(0.4, 1.2)  # mm offset
        result = StationResult(
            station_id=StationID.CORE_INSERTION,
            passed=False,
            measured_value=force,
            param_name=STATION_PARAMS[StationID.CORE_INSERTION],
            reason="CORE_MISALIGNED",
            detail=f"core offset {offset:.2f} mm (tolerance ±0.3 mm)",
        )
    else:
        result = StationResult(
            station_id=StationID.CORE_INSERTION,
            passed=True,
            measured_value=force,
            param_name=STATION_PARAMS[StationID.CORE_INSERTION],
        )

    return result, temp


# ── Station 2 — Body Bonding ─────────────────────────────────────────────────
# Key parameter: cure temperature (°C), spec 55–75 °C.
# Defects: WEAK_BOND, BODY_MISALIGNED, CURE_TEMP_OUT_OF_RANGE.
# Special: overheat event can push temp > overheat_limit → machine FAULTED.

CURE_MEAN  = 64.0   # °C
CURE_STD   = 5.0
CURE_LO    = 55.0
CURE_HI    = 75.0

def _temp_s2(cycle: int, overheat: bool) -> float:
    base = 62.0 + 3.0 * math.sin(cycle * 0.07)
    if overheat:
        return 92.0 + random.gauss(0, 1.0)   # fault-triggering spike
    return base + random.gauss(0, 1.5)


def station2_process(
    defect_rate: float,
    overheat_prob: float,
    overheat_limit: float,
    cycle: int,
) -> tuple[StationResult, float, bool]:
    """Returns (result, temperature, is_overheat_fault)."""
    overheat = random.random() < overheat_prob
    temp     = _temp_s2(cycle, overheat)

    if overheat or temp >= overheat_limit:
        # Hard fault — line must stop
        result = StationResult(
            station_id=StationID.BODY_BONDING,
            passed=False,
            measured_value=temp,
            param_name=STATION_PARAMS[StationID.BODY_BONDING],
            reason="CURE_TEMP_OUT_OF_RANGE",
            detail=f"{temp:.1f} °C (overheat ≥ {overheat_limit} °C — line FAULTED)",
        )
        return result, temp, True

    cure_temp = _normal(CURE_MEAN, CURE_STD)

    if cure_temp < CURE_LO or cure_temp > CURE_HI:
        result = StationResult(
            station_id=StationID.BODY_BONDING,
            passed=False,
            measured_value=cure_temp,
            param_name=STATION_PARAMS[StationID.BODY_BONDING],
            reason="CURE_TEMP_OUT_OF_RANGE",
            detail=f"{cure_temp:.1f} °C (spec {CURE_LO}–{CURE_HI} °C)",
        )
    elif random.random() < defect_rate * 0.6:
        coverage = random.uniform(50.0, 79.0)
        result = StationResult(
            station_id=StationID.BODY_BONDING,
            passed=False,
            measured_value=cure_temp,
            param_name=STATION_PARAMS[StationID.BODY_BONDING],
            reason="WEAK_BOND",
            detail=f"glue coverage {coverage:.0f}% (min 80%)",
        )
    elif random.random() < defect_rate * 0.4:
        offset = random.uniform(0.31, 0.8)
        result = StationResult(
            station_id=StationID.BODY_BONDING,
            passed=False,
            measured_value=cure_temp,
            param_name=STATION_PARAMS[StationID.BODY_BONDING],
            reason="BODY_MISALIGNED",
            detail=f"offset {offset:.2f} mm (tolerance 0.3 mm)",
        )
    else:
        result = StationResult(
            station_id=StationID.BODY_BONDING,
            passed=True,
            measured_value=cure_temp,
            param_name=STATION_PARAMS[StationID.BODY_BONDING],
        )

    return result, temp, False


# ── Station 3 — Ferrule Crimping ─────────────────────────────────────────────
# Key parameter: crimp pressure (bar), spec 4–9 bar.
# Defects: FERRULE_LOOSE, FERRULE_NOT_SEATED.

CRIMP_MEAN = 6.2
CRIMP_STD  = 0.9
CRIMP_LO   = 4.0
CRIMP_HI   = 9.0

def _temp_s3(cycle: int) -> float:
    return 28.0 + 1.2 * math.sin(cycle * 0.12) + random.gauss(0, 0.4)


def station3_process(defect_rate: float, cycle: int) -> tuple[StationResult, float]:
    pressure = _normal(CRIMP_MEAN, CRIMP_STD)
    temp     = _temp_s3(cycle)

    if pressure < CRIMP_LO:
        result = StationResult(
            station_id=StationID.FERRULE_CRIMPING,
            passed=False,
            measured_value=pressure,
            param_name=STATION_PARAMS[StationID.FERRULE_CRIMPING],
            reason="FERRULE_LOOSE",
            detail=f"{pressure:.2f} bar (min {CRIMP_LO} bar)",
        )
    elif random.random() < defect_rate:
        gap = random.uniform(0.1, 0.5)
        result = StationResult(
            station_id=StationID.FERRULE_CRIMPING,
            passed=False,
            measured_value=pressure,
            param_name=STATION_PARAMS[StationID.FERRULE_CRIMPING],
            reason="FERRULE_NOT_SEATED",
            detail=f"axial gap {gap:.2f} mm detected",
        )
    else:
        result = StationResult(
            station_id=StationID.FERRULE_CRIMPING,
            passed=True,
            measured_value=pressure,
            param_name=STATION_PARAMS[StationID.FERRULE_CRIMPING],
        )

    return result, temp


# ── Station 4 — Eraser Insertion ─────────────────────────────────────────────
# Key parameter: insertion depth (mm), spec 5–8 mm.
# Defects: ERASER_MISSING, ERASER_LOOSE.

DEPTH_MEAN = 6.4
DEPTH_STD  = 0.5
DEPTH_LO   = 5.0
DEPTH_HI   = 8.0

def _temp_s4(cycle: int) -> float:
    return 23.5 + 0.3 * math.sin(cycle * 0.09) + random.gauss(0, 0.2)


def station4_process(defect_rate: float, cycle: int) -> tuple[StationResult, float]:
    depth = _normal(DEPTH_MEAN, DEPTH_STD)
    temp  = _temp_s4(cycle)

    # Rare "feeder jammed" scenario — no eraser loaded
    if random.random() < defect_rate * 0.3:
        result = StationResult(
            station_id=StationID.ERASER_INSERTION,
            passed=False,
            measured_value=0.0,
            param_name=STATION_PARAMS[StationID.ERASER_INSERTION],
            reason="ERASER_MISSING",
            detail="no eraser detected by sensor",
        )
    elif depth < DEPTH_LO:
        result = StationResult(
            station_id=StationID.ERASER_INSERTION,
            passed=False,
            measured_value=depth,
            param_name=STATION_PARAMS[StationID.ERASER_INSERTION],
            reason="ERASER_LOOSE",
            detail=f"retention depth {depth:.2f} mm (min {DEPTH_LO} mm)",
        )
    else:
        result = StationResult(
            station_id=StationID.ERASER_INSERTION,
            passed=True,
            measured_value=depth,
            param_name=STATION_PARAMS[StationID.ERASER_INSERTION],
        )

    return result, temp
