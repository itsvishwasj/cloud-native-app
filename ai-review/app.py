"""
AI Code Review Service — FastAPI Application.

Provides a REST API and web dashboard for AI-powered code review
and Kubernetes diagnosis. Routes include health checks, review
triggers, report retrieval, and the interactive dashboard.

Run with: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from logger import get_logger
from models import ReviewReport

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Code Review Service",
    description="AI-powered code review and Kubernetes diagnosis dashboard",
    version="2.0",
)

# CORS — allow dashboard and external integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Mount reports directory for static file serving
os.makedirs(REPORTS_DIR, exist_ok=True)
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")


# ---------------------------------------------------------------------------
# Health & Status Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def home():
    """Service health check — basic status."""
    return {
        "status": "Running",
        "service": "AI Code Review",
        "version": "2.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check with dependency status."""
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "UP",
        "gemini_api_key_configured": gemini_configured,
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "reports_dir_exists": os.path.isdir(REPORTS_DIR),
    }


# ---------------------------------------------------------------------------
# Dashboard Route
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard():
    """Serve the interactive AI Code Review dashboard."""
    template_path = os.path.join(TEMPLATES_DIR, "dashboard.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Dashboard template not found")

    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    return HTMLResponse(content=html_content)


# ---------------------------------------------------------------------------
# Review API Routes
# ---------------------------------------------------------------------------

@app.post("/api/review", tags=["Review"])
async def trigger_review():
    """Trigger an AI code review on changed files."""
    try:
        from html_report import generate_html
        from review import review_code

        logger.info("API: Triggering AI code review")
        report = review_code()
        generate_html(report)

        return {
            "status": "completed",
            "overall_score": report.overall_score,
            "total_issues": report.total_issues,
            "critical_count": report.critical_count,
            "has_critical_issues": report.has_critical_issues(),
        }
    except Exception as e:
        logger.error("API: Review failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/latest-report", tags=["Review"])
async def get_latest_report():
    """Get the latest consolidated review report."""
    report_path = os.path.join(REPORTS_DIR, "review_report.json")

    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="No review report found")

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error("Failed to load report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports", tags=["Review"])
async def list_reports():
    """List all available review reports."""
    if not os.path.isdir(REPORTS_DIR):
        return {"reports": []}

    reports = []
    for fname in sorted(os.listdir(REPORTS_DIR)):
        fpath = os.path.join(REPORTS_DIR, fname)
        if os.path.isfile(fpath):
            reports.append({
                "filename": fname,
                "size_bytes": os.path.getsize(fpath),
                "type": "json" if fname.endswith(".json") else "html",
            })

    return {"reports": reports}


@app.get("/api/reports/{report_name}", tags=["Review"])
async def get_report(report_name: str):
    """Get a specific report by filename."""
    report_path = os.path.join(REPORTS_DIR, report_name)

    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail=f"Report '{report_name}' not found")

    # Prevent path traversal
    if ".." in report_name or "/" in report_name:
        raise HTTPException(status_code=400, detail="Invalid report name")

    if report_name.endswith(".html"):
        with open(report_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        with open(report_path, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))


# ---------------------------------------------------------------------------
# Kubernetes Diagnosis API Routes
# ---------------------------------------------------------------------------

@app.post("/api/k8s/diagnose", tags=["Kubernetes"])
async def diagnose_k8s(request: Request):
    """
    AI-powered Kubernetes pod diagnosis.

    Accepts kubectl output as JSON body:
    {
        "pod_name": "web-app-xxx",
        "namespace": "default",
        "logs": "<kubectl logs output>",
        "describe": "<kubectl describe pod output>"
    }
    """
    try:
        from k8s_diagnosis import diagnose_from_input

        body = await request.json()
        pod_name = body.get("pod_name", "unknown")
        namespace = body.get("namespace", "default")
        logs = body.get("logs", "")
        describe = body.get("describe", "")

        if not logs and not describe:
            raise HTTPException(
                status_code=400,
                detail="At least one of 'logs' or 'describe' must be provided",
            )

        logger.info("API: Diagnosing pod %s/%s", namespace, pod_name)
        diagnosis = diagnose_from_input(
            pod_name=pod_name,
            namespace=namespace,
            logs=logs,
            describe_output=describe,
        )

        return JSONResponse(content=diagnosis.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API: K8s diagnosis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )
