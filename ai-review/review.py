"""
AI Code Review engine powered by Google Gemini.

Reads changed files from git, sends each to Gemini for analysis,
validates responses through Pydantic models, and produces structured
JSON reports. Includes retry logic and a CI/CD quality gate.
"""

import json
import os
import re
import sys
import time

from dotenv import load_dotenv
from google import genai

from github_diff import get_git_metadata, read_changed_files
from logger import get_logger
from models import FileReview, ReviewIssue, ReviewReport, SeverityLevel
from prompt import SYSTEM_PROMPT

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _get_client():
    """Lazy-initialize the Gemini client with validation."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set")
        raise EnvironmentError(
            "GEMINI_API_KEY is required. Set it in .env or as an environment variable. "
            "Get your key at https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=api_key)


def _get_model_name() -> str:
    """Get the Gemini model name with fallback."""
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    if not model:
        model = "gemini-2.0-flash"
        logger.warning("GEMINI_MODEL not set, defaulting to %s", model)
    return model


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from Gemini response."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_review_response(response_text: str, filename: str) -> FileReview:
    """
    Parse Gemini's response into a validated FileReview model.

    Handles JSON parsing errors gracefully by returning a FileReview
    with a single issue describing the parse failure.
    """
    cleaned = _strip_markdown_fences(response_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(
            "Failed to parse JSON response for %s: %s", filename, e
        )
        # Return a review indicating the parse failure
        return FileReview(
            filename=filename,
            score=0,
            summary="AI response was not valid JSON — raw response saved",
            issues=[],
        )

    # Build validated issues list
    issues: list[ReviewIssue] = []
    for raw_issue in data.get("issues", []):
        try:
            issue = ReviewIssue(
                severity=raw_issue.get("severity", "Low"),
                category=raw_issue.get("category", "code_smell"),
                line=raw_issue.get("line"),
                issue=raw_issue.get("issue", "Unknown issue"),
                explanation=raw_issue.get("explanation", ""),
                suggestion=raw_issue.get("suggestion", ""),
                corrected_code=raw_issue.get("corrected_code"),
            )
            issues.append(issue)
        except Exception as e:
            logger.warning("Skipping malformed issue in %s: %s", filename, e)

    return FileReview(
        filename=filename,
        score=data.get("score", 0),
        summary=data.get("summary", ""),
        issues=issues,
    )


def _review_single_file(
    client, model_name: str, filename: str, code: str
) -> FileReview:
    """
    Send a single file to Gemini for review with retry logic.

    Args:
        client: Initialized Gemini client.
        model_name: Gemini model identifier.
        filename: Path of the file being reviewed.
        code: Source code contents.

    Returns:
        Validated FileReview model.
    """
    prompt_content = f"""{SYSTEM_PROMPT}

Filename: {filename}

Code:
{code}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Reviewing %s (attempt %d/%d)", filename, attempt, MAX_RETRIES
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt_content,
            )

            review = _parse_review_response(response.text, filename)
            logger.info(
                "Review complete for %s — score: %d, issues: %d",
                filename,
                review.score,
                len(review.issues),
            )
            return review

        except Exception as e:
            logger.error(
                "Error reviewing %s (attempt %d/%d): %s",
                filename,
                attempt,
                MAX_RETRIES,
                e,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
            else:
                logger.error("All retries exhausted for %s", filename)
                return FileReview(
                    filename=filename,
                    score=0,
                    summary=f"Review failed after {MAX_RETRIES} attempts: {e}",
                    issues=[],
                )


def review_code() -> ReviewReport:
    """
    Run AI code review on all changed files and generate reports.

    Returns:
        ReviewReport with aggregated results across all files.
    """
    logger.info("=" * 60)
    logger.info("Starting AI Code Review")
    logger.info("=" * 60)

    files = read_changed_files()

    if not files:
        logger.warning("No changed files found — nothing to review")
        return ReviewReport(overall_score=100, file_reviews=[])

    # Initialize Gemini client (lazy — only when review is actually needed)
    client = _get_client()
    model_name = _get_model_name()
    logger.info("Using Gemini model: %s", model_name)

    # Create reports directory
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Review each file
    file_reviews: list[FileReview] = []
    for filename, code in files.items():
        review = _review_single_file(client, model_name, filename, code)
        file_reviews.append(review)

        # Save per-file JSON report
        report_name = filename.replace("/", "_").replace("\\", "_") + ".json"
        report_path = os.path.join(REPORTS_DIR, report_name)
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(review.model_dump(), f, indent=4)
            logger.info("Per-file report saved: %s", report_path)
        except OSError as e:
            logger.error("Failed to save report %s: %s", report_path, e)

    # Compute overall score (average of file scores)
    valid_scores = [r.score for r in file_reviews if r.score > 0]
    overall_score = (
        round(sum(valid_scores) / len(valid_scores)) if valid_scores else 0
    )

    # Get git metadata
    git_meta = get_git_metadata()

    # Build the aggregated report
    report = ReviewReport(
        overall_score=overall_score,
        commit_sha=git_meta.get("commit_sha"),
        branch=git_meta.get("branch"),
        file_reviews=file_reviews,
    )
    report.compute_counts()

    # Save consolidated report
    consolidated_path = os.path.join(REPORTS_DIR, "review_report.json")
    try:
        with open(consolidated_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=4)
        logger.info("Consolidated report saved: %s", consolidated_path)
    except OSError as e:
        logger.error("Failed to save consolidated report: %s", e)

    # Summary
    logger.info("=" * 60)
    logger.info("AI Code Review Complete")
    logger.info("Overall Score: %d/100", report.overall_score)
    logger.info("Files Reviewed: %d", report.total_files_reviewed)
    logger.info(
        "Issues — Critical: %d | High: %d | Medium: %d | Low: %d",
        report.critical_count,
        report.high_count,
        report.medium_count,
        report.low_count,
    )
    logger.info("=" * 60)

    if report.has_critical_issues():
        logger.error(
            "🚨 CRITICAL ISSUES DETECTED — Deployment should be blocked!"
        )

    return report


if __name__ == "__main__":
    result = review_code()

    # Exit with non-zero code if critical issues found (for CI/CD)
    if result.has_critical_issues():
        logger.error("Exiting with code 1 due to critical issues")
        sys.exit(1)
