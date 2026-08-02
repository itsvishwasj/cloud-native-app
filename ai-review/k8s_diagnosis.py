"""
AI-powered Kubernetes pod diagnosis using Google Gemini.

Analyzes kubectl logs and describe output to diagnose common pod
failures: CrashLoopBackOff, ImagePullBackOff, OOMKilled, probe
failures, volume mount errors, and network issues.

Can run locally with kubectl access or accept pre-captured
output via the FastAPI API endpoint.
"""

import json
import os
import re
import subprocess
import time

from dotenv import load_dotenv
from google import genai

from logger import get_logger
from models import K8sDiagnosis, K8sIssue, SeverityLevel
from prompt import K8S_DIAGNOSIS_PROMPT

load_dotenv()

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _get_client():
    """Lazy-initialize the Gemini client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is required for K8s diagnosis. "
            "Set it in .env or as an environment variable."
        )
    return genai.Client(api_key=api_key)


def _get_model_name() -> str:
    """Get the Gemini model name."""
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from Gemini response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _run_kubectl(args: list[str]) -> str:
    """Run a kubectl command and return its output."""
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("kubectl %s failed: %s", " ".join(args), result.stderr.strip())
            return result.stderr
        return result.stdout
    except FileNotFoundError:
        logger.error("kubectl not found in PATH")
        raise RuntimeError("kubectl is not installed or not in PATH")
    except subprocess.TimeoutExpired:
        logger.error("kubectl command timed out: %s", " ".join(args))
        raise RuntimeError("kubectl command timed out after 30 seconds")


def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 200) -> str:
    """Fetch recent logs from a Kubernetes pod."""
    logger.info("Fetching logs for pod %s/%s (tail=%d)", namespace, pod_name, tail)
    return _run_kubectl([
        "logs", pod_name,
        "-n", namespace,
        "--tail", str(tail),
    ])


def get_pod_describe(pod_name: str, namespace: str = "default") -> str:
    """Fetch describe output for a Kubernetes pod."""
    logger.info("Describing pod %s/%s", namespace, pod_name)
    return _run_kubectl(["describe", "pod", pod_name, "-n", namespace])


def diagnose_from_input(
    pod_name: str,
    namespace: str = "default",
    logs: str = "",
    describe_output: str = "",
) -> K8sDiagnosis:
    """
    Diagnose a Kubernetes pod failure from pre-captured kubectl output.

    This is the primary entry point for the FastAPI API and CI/CD use.

    Args:
        pod_name: Name of the pod.
        namespace: Kubernetes namespace.
        logs: Output from `kubectl logs`.
        describe_output: Output from `kubectl describe pod`.

    Returns:
        K8sDiagnosis model with issues and suggested fixes.
    """
    if not logs and not describe_output:
        logger.warning("No kubectl output provided for diagnosis")
        return K8sDiagnosis(
            pod_name=pod_name,
            namespace=namespace,
            status="Unknown",
            summary="No kubectl output provided for analysis",
            issues=[],
        )

    client = _get_client()
    model_name = _get_model_name()

    prompt = f"""{K8S_DIAGNOSIS_PROMPT}

Pod Name: {pod_name}
Namespace: {namespace}

--- kubectl logs ---
{logs if logs else "(no logs available)"}

--- kubectl describe pod ---
{describe_output if describe_output else "(no describe output available)"}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Diagnosing pod %s/%s (attempt %d/%d)",
                namespace, pod_name, attempt, MAX_RETRIES,
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )

            cleaned = _strip_markdown_fences(response.text)

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse diagnosis JSON: %s", e)
                return K8sDiagnosis(
                    pod_name=pod_name,
                    namespace=namespace,
                    status="Parse Error",
                    summary="AI response was not valid JSON",
                    issues=[],
                )

            # Build validated issues
            issues: list[K8sIssue] = []
            for raw in data.get("issues", []):
                try:
                    issue = K8sIssue(
                        severity=raw.get("severity", "Medium"),
                        problem=raw.get("problem", "Unknown"),
                        root_cause=raw.get("root_cause", ""),
                        fix=raw.get("fix", ""),
                        kubectl_command=raw.get("kubectl_command"),
                    )
                    issues.append(issue)
                except Exception as e:
                    logger.warning("Skipping malformed K8s issue: %s", e)

            diagnosis = K8sDiagnosis(
                pod_name=data.get("pod_name", pod_name),
                namespace=data.get("namespace", namespace),
                status=data.get("status", "Unknown"),
                summary=data.get("summary", ""),
                issues=issues,
            )

            logger.info(
                "Diagnosis complete for %s/%s — %d issues found",
                namespace, pod_name, len(issues),
            )

            # Save diagnosis report
            os.makedirs(REPORTS_DIR, exist_ok=True)
            report_path = os.path.join(
                REPORTS_DIR,
                f"k8s_diagnosis_{namespace}_{pod_name}.json",
            )
            try:
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(diagnosis.model_dump(), f, indent=4)
                logger.info("Diagnosis report saved: %s", report_path)
            except OSError as e:
                logger.error("Failed to save diagnosis report: %s", e)

            return diagnosis

        except Exception as e:
            logger.error(
                "Diagnosis error (attempt %d/%d): %s", attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

    # All retries exhausted
    return K8sDiagnosis(
        pod_name=pod_name,
        namespace=namespace,
        status="Error",
        summary=f"Diagnosis failed after {MAX_RETRIES} attempts",
        issues=[],
    )


def diagnose_pod(pod_name: str, namespace: str = "default") -> K8sDiagnosis:
    """
    Diagnose a pod by fetching kubectl output and running AI analysis.

    Requires kubectl to be configured and accessible.

    Args:
        pod_name: Name of the Kubernetes pod.
        namespace: Kubernetes namespace.

    Returns:
        K8sDiagnosis model with issues and suggested fixes.
    """
    logger.info("=" * 60)
    logger.info("Starting K8s Diagnosis for %s/%s", namespace, pod_name)
    logger.info("=" * 60)

    logs = get_pod_logs(pod_name, namespace)
    describe = get_pod_describe(pod_name, namespace)

    diagnosis = diagnose_from_input(
        pod_name=pod_name,
        namespace=namespace,
        logs=logs,
        describe_output=describe,
    )

    # Print summary
    logger.info("=" * 60)
    logger.info("Diagnosis Summary for %s/%s", namespace, pod_name)
    logger.info("Status: %s", diagnosis.status)
    logger.info("Summary: %s", diagnosis.summary)
    for i, issue in enumerate(diagnosis.issues, 1):
        logger.info(
            "Issue %d [%s]: %s → %s",
            i, issue.severity.value, issue.problem, issue.fix,
        )
    logger.info("=" * 60)

    return diagnosis


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python k8s_diagnosis.py <pod-name> [namespace]")
        print("Example: python k8s_diagnosis.py web-app-abc123 default")
        sys.exit(1)

    pod = sys.argv[1]
    ns = sys.argv[2] if len(sys.argv) > 2 else "default"

    result = diagnose_pod(pod, ns)
    print(json.dumps(result.model_dump(), indent=2))
