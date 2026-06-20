# PROMPTS.md — AI Tools Usage Log

> Required for the "Use of AI tools" rubric section (Task 3).
> Format: Date | Tool | Prompt (summary) | Output note | Errors found + fix | Benefit

---

## Entry 1 — Project Scaffold
**Date:** 2024-01  
**Tool:** Claude Code (claude-sonnet-4-6)  
**Prompt summary:** Full project specification: wooden pencil production line simulation with 4 stations, InfluxDB Cloud + Grafana Cloud, FastAPI HMI, WebSocket live updates, defect logic per station, CMMS, QC, unit tests, GitHub Pages docs site.  
**AI output:** Complete repo scaffold — all backend modules, frontend HMI, scripts, tests, docs, report stubs, GitHub Actions workflow.  
**Errors found + fix:** Reviewed generated code; confirmed `config.py` fails fast on missing env vars, `.env` is in `.gitignore`, and tokens are never hardcoded.  
**Benefit:** Saved ~10 hours of boilerplate; all architectural decisions (asyncio decoupling, ASYNCHRONOUS influx client, WebSocket fallback to polling) were reasoned through in the generated code.

---

## Entry 2 — (add your entries here as you make further prompts)
**Date:**  
**Tool:**  
**Prompt summary:**  
**AI output:**  
**Errors found + fix:**  
**Benefit:**  

---

*Keep this file updated throughout the project. For each significant AI interaction, record what was generated, what you verified or corrected, and how it saved time or introduced risk.*
