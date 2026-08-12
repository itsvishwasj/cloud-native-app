# Unified Cloud-Native Research & Operations Dashboard

The Unified Dashboard is a single-page web application (SPA) providing visual monitoring, real-time workload forecasting, automated zero-terminal demonstration capabilities, research evaluation metrics, statistical analysis, and AI-assisted DevOps diagnostics.

---

## 1. Quick Start Guide

### Prerequisites
- Python 3.10+
- Flask (`pip install flask`)
- Running Minikube cluster (`kubectl`)
- Prometheus server running on `http://localhost:9090` (optional for live telemetry)

### How to Launch Dashboard
```bash
python3 dashboard/server.py
```
Open your browser at:
`http://localhost:8080`

---

## 2. API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Web dashboard UI entry point |
| `/api/health` | `GET` | System health check (K8s, Docker, Prometheus, Gemini API) |
| `/api/overview` | `GET` | Real-time RPS, CPU%, Memory, P95 latency, replica counts |
| `/api/cicd` | `GET` | CI/CD pipeline automation stage statuses |
| `/api/kubernetes` | `GET` | Active pod list, ready status, replica bounds |
| `/api/workload` | `GET` | Live RPS vs EMA-TAP 15s/30s/60s predicted RPS |
| `/api/prediction` | `GET` | EMA-TAP formula, alpha/beta weights, model MAE/RMSE benchmarks |
| `/api/monitoring` | `GET` | Prometheus telemetry stream |
| `/api/research` | `GET` | Authoritative Phase 7 evaluation dataset (`dashboard_data.json`) |
| `/api/statistics` | `GET` | Statistical paired t-tests, p-values, Cohen's d, 95% CIs |
| `/api/ai-diagnostics` | `POST` / `GET` | Gemini API structured JSON error explanation & fix recommendations |
| `/api/events` | `GET` | Human-readable system event log timeline |
| `/api/demo/start` | `POST` | Trigger automated zero-terminal demonstration |
| `/api/demo/stop` | `POST` | Stop running demonstration |
| `/api/demo/reset` | `POST` | Reset demonstration state |

---

## 3. Gemini API Configuration
To enable live Gemini AI error diagnostics, set your API key environment variable before starting the dashboard server:
```bash
export GEMINI_API_KEY="your-gemini-api-key"
python3 dashboard/server.py
```
If `GEMINI_API_KEY` is not set, the dashboard automatically falls back to deterministic structured JSON diagnostic schema responses.
