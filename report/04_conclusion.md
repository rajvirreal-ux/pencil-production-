# Task 4 — Conclusion

## Strengths

- **Explainable defects:** every reject carries a station name, reason code, and measured value (e.g. `REJECT @ Body Bonding — CURE_TEMP_OUT_OF_RANGE: 81.4 °C (spec 55–75 °C)`). This is verifiable at a glance in the HMI's reject feed and in Grafana's Pareto panel.
- **Zero-install cloud backend:** InfluxDB Cloud and Grafana Cloud require no local installation. The entire connection is two URLs and two tokens in `.env`. This makes the project fully reproducible from a clean checkout.
- **Fault/recovery loop:** the Body Bonding overheat event exercises the full FAULTED → Reset → STOPPED → RUNNING lifecycle, demonstrating a realistic safety interlock.
- **Resilient writes:** `InfluxWriter` wraps every cloud write in a try/except with a degraded indicator surfaced in the HMI footer. A temporary network outage does not crash the simulation.
- **Test coverage without network:** the unit tests prove all defect logic, state transitions, and QC aggregation with zero cloud dependency.

## Weaknesses

- **Internet dependency:** the simulation's metric recording requires a live connection to InfluxDB Cloud. If the network is unavailable, historical data is lost for that period (though the simulation itself continues). The free tier has data-retention limits (typically 30 days) and a write-rate cap.
- **Simulated sensors, not real hardware:** all sensor values are drawn from a normal distribution. A real line would integrate PLC data via OPC-UA or MQTT.
- **In-memory engine state:** restarting the app clears counters and the in-progress belt. Historical data persists in InfluxDB Cloud, but the live counters reset.
- **No HMI authentication:** the FastAPI app exposes Start/Stop/Reset to anyone on the local network with no credentials.
- **Single production line:** the architecture supports only one line instance per running process.

## Future Work

- **Real hardware integration** via OPC-UA / MQTT broker to pull actual PLC sensor values.
- **Local write buffer / SQLite cache** for offline resilience — flush to InfluxDB Cloud when connectivity returns.
- **Predictive maintenance / ML** on the temperature trend at Body Bonding to predict overheat events before they fault the line.
- **Grafana alerting rules** on yield % dropping below a threshold or temperature exceeding a warning band.
- **Multi-line support** by parameterising the engine and running multiple instances.
- **HMI authentication** (Basic Auth or a session token) before deploying beyond a local machine.

## Operational Requirements

| Requirement | Notes |
|-------------|-------|
| **Internet connectivity** | Required for InfluxDB Cloud writes and Grafana dashboard updates |
| **Cloud tier limits** | InfluxDB Cloud free tier: 30-day retention, 5 MB/5 min write limit. Grafana Cloud free: 14-day metrics retention |
| **Token security** | Rotate InfluxDB and Grafana tokens immediately if ever exposed. Store only in `.env`, never commit |
| **Python runtime** | Python 3.11+, venv with `requirements.txt` |
| **Sensor calibration** | On real hardware: insertion force load cells, K-type thermocouples, and pressure transducers require periodic calibration |
| **Maintenance scheduling** | CMMS alerts at every `MAINTENANCE_INTERVAL` cycles (default 50). On real hardware this maps to a physical inspection checklist |
| **Operator training** | Operator must understand: Start/Stop/Reset workflow, fault acknowledgement, and the meaning of defect codes |
