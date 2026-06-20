# Task 1 — Product & Production Line Concept

## The Product: Wooden Pencil

A standard HB wooden pencil consists of four main assembled components:

| Component | Description |
|-----------|-------------|
| **Graphite core** | HB-grade graphite/clay rod, 2 mm diameter, seated in a routed groove |
| **Cedar body halves** | Upper and lower cedar shell bonded with PVA adhesive, heat-cured |
| **Ferrule** | Thin aluminium band crimped at the rear end to secure the eraser holder |
| **Eraser** | Rubber eraser plug inserted and retained inside the ferrule |

## The Production Line — 4 Stations

Each pencil travels as a **work item** along a conveyor past four sequential stations. A defect at any station immediately routes the pencil to a reject bin; it is never counted as a good part.

```
  FEED → [S1 Core Insertion] → [S2 Body Bonding] → [S3 Ferrule Crimping] → [S4 Eraser Insertion] → EXIT
```

### Station 1 — Core Insertion
- **Operation:** Robotic arm places the graphite core into the lower body half's routed groove.
- **Key parameter:** Insertion force (N), nominal 8–16 N.
- **Defects:** `CORE_MISALIGNED` (geometric offset > 0.3 mm), `CORE_FRACTURED` (force > 18 N shatters the core).

### Station 2 — Body Bonding
- **Operation:** PVA adhesive is applied and the upper half pressed onto the lower; a heat lamp cures the bond.
- **Key parameter:** Cure temperature (°C), spec 55–75 °C.
- **Defects:** `WEAK_BOND` (coverage < 80%), `BODY_MISALIGNED` (lateral offset > 0.3 mm), `CURE_TEMP_OUT_OF_RANGE` (outside spec, or ≥ 90 °C triggers a machine fault).

### Station 3 — Ferrule Crimping
- **Operation:** Pneumatic crimper squeezes the aluminium ferrule ring onto the pencil body end.
- **Key parameter:** Crimp pressure (bar), spec 4–9 bar.
- **Defects:** `FERRULE_LOOSE` (pressure < 4 bar), `FERRULE_NOT_SEATED` (axial gap detected by laser sensor).

### Station 4 — Eraser Insertion
- **Operation:** Pneumatic pusher seats the rubber eraser plug into the ferrule cavity.
- **Key parameter:** Insertion depth (mm), spec 5–8 mm.
- **Defects:** `ERASER_MISSING` (feeder jam — no eraser detected), `ERASER_LOOSE` (retention depth < 5 mm).

## Flow Description

A new `Pencil` work item enters S1 every conveyor cycle. As the belt advances, each station processes the pencil in its slot. Pass → advance to the next station. Fail → pencil is marked `DEFECTIVE` with the **exact station, reason code, and measured value**, and is diverted to the Quality Control reject bin. After S4, a pencil that passed all four stations is marked `GOOD`.

The simulation runs a configurable cycle time (default 1.5 s/tick) and reports via WebSocket to the HMI and over HTTPS to InfluxDB Cloud.
