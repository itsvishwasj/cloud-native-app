# Dashboard Technical Architecture Document

This document outlines the system architecture, component interactions, and data flow of the Unified Cloud-Native Research & Operations Dashboard.

---

## 1. System Architecture Diagram

```text
                                 [ Browser User Interface ]
                                   (Single Page App SPA)
                                             │
                                     HTTP / JSON APIs
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │   Python Flask Backend Server (:8080)   │
                        │          (dashboard/server.py)          │
                        └────────────────────┬────────────────────┘
                                             │
      ┌──────────────────────┬───────────────┼───────────────┬──────────────────────┐
      │                      │               │               │                      │
      ▼                      ▼               ▼               ▼                      ▼
┌────────────┐        ┌─────────────┐  ┌───────────┐  ┌─────────────┐        ┌─────────────┐
│ Kubernetes │        │ Prometheus  │  │  EMA-TAP  │  │ Research    │        │ Gemini API  │
│ Adapter    │        │ Telemetry   │  │ Forecast  │  │ Data Layer  │        │ AI Engine   │
│ (kubectl)  │        │ (PromQL)    │  │ Predictor │  │ (Phase 7)   │        │ (JSON)      │
└────────────┘        └─────────────┘  └───────────┘  └─────────────┘        └─────────────┘
```

---

## 2. Key Modules & Technical Data Layer

1. **Kubernetes Adapter**: Invokes `kubectl get deployment web-app -o json` and `kubectl get pods` to query real-time pod statuses and replica counts.
2. **Prometheus Telemetry Stream**: Queries Prometheus instant API (`/api/v1/query`) for application request rates, process CPU utilization, memory footprints, and P95/P99 latencies.
3. **EMA-TAP Workload Predictor**: Invokes `predict_service.py` to calculate 15s, 30s, and 60s workload forecasts dynamically.
4. **Research Data Layer**: Parses authoritative JSON and CSV datasets produced in Phase 7 (`dashboard_data.json`, `final_comparison.csv`, `JOURNAL_SAFE_RESULTS.md`) without modifying raw telemetry files.
5. **Gemini AI Diagnostics Adapter**: Sends incident messages to Google Gemini API (`gemini-1.5-flash`), enforcing a strict JSON schema for structured root-cause explanations and fix suggestions with human-in-the-loop approval guards.
