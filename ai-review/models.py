"""
Pydantic data models for AI Code Review structured output.

These models define the contract between Gemini AI responses and the
rest of the application. All review results are validated through these
schemas before being saved or displayed.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """Issue severity levels — Critical issues block CI/CD deployment."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class IssueCategory(str, Enum):
    """Categories of detected issues for structured classification."""
    LOGIC_BUG = "logic_bug"
    RUNTIME_BUG = "runtime_bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    KUBERNETES = "kubernetes"
    CICD = "cicd"
    CODE_SMELL = "code_smell"
    BEST_PRACTICE = "best_practice"


class ReviewIssue(BaseModel):
    """A single issue detected during AI code review."""
    severity: SeverityLevel = Field(description="Issue severity level")
    category: IssueCategory = Field(description="Issue category classification")
    line: Optional[int] = Field(default=None, description="Line number where issue occurs")
    issue: str = Field(description="Short description of the issue")
    explanation: str = Field(description="Detailed explanation of why this is a problem")
    suggestion: str = Field(description="How to fix the issue")
    corrected_code: Optional[str] = Field(default=None, description="Corrected code snippet")


class FileReview(BaseModel):
    """AI review result for a single file."""
    filename: str = Field(description="Path of the reviewed file")
    score: int = Field(ge=0, le=100, description="Quality score 0-100")
    issues: list[ReviewIssue] = Field(default_factory=list, description="List of detected issues")
    summary: str = Field(default="", description="Brief summary of the file review")


class ReviewReport(BaseModel):
    """Aggregated review report across all changed files."""
    overall_score: int = Field(ge=0, le=100, description="Overall quality score 0-100")
    total_files_reviewed: int = Field(default=0, description="Number of files reviewed")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of the review"
    )
    commit_sha: Optional[str] = Field(default=None, description="Git commit SHA")
    branch: Optional[str] = Field(default=None, description="Git branch name")
    file_reviews: list[FileReview] = Field(default_factory=list, description="Per-file reviews")
    critical_count: int = Field(default=0, description="Number of Critical issues")
    high_count: int = Field(default=0, description="Number of High issues")
    medium_count: int = Field(default=0, description="Number of Medium issues")
    low_count: int = Field(default=0, description="Number of Low issues")
    total_issues: int = Field(default=0, description="Total number of issues")

    def compute_counts(self) -> None:
        """Recompute issue severity counts from file reviews."""
        self.critical_count = 0
        self.high_count = 0
        self.medium_count = 0
        self.low_count = 0
        for fr in self.file_reviews:
            for issue in fr.issues:
                if issue.severity == SeverityLevel.CRITICAL:
                    self.critical_count += 1
                elif issue.severity == SeverityLevel.HIGH:
                    self.high_count += 1
                elif issue.severity == SeverityLevel.MEDIUM:
                    self.medium_count += 1
                elif issue.severity == SeverityLevel.LOW:
                    self.low_count += 1
        self.total_issues = (
            self.critical_count + self.high_count + self.medium_count + self.low_count
        )
        self.total_files_reviewed = len(self.file_reviews)

    def has_critical_issues(self) -> bool:
        """Returns True if any Critical issues exist — used as CI/CD quality gate."""
        return self.critical_count > 0


# ---------------------------------------------------------------------------
# Kubernetes Diagnosis Models
# ---------------------------------------------------------------------------

class K8sIssue(BaseModel):
    """A single issue found during Kubernetes pod diagnosis."""
    severity: SeverityLevel = Field(description="Issue severity")
    problem: str = Field(description="What went wrong")
    root_cause: str = Field(description="Why it happened")
    fix: str = Field(description="How to fix it")
    kubectl_command: Optional[str] = Field(
        default=None, description="Kubectl command to apply the fix"
    )


class K8sDiagnosis(BaseModel):
    """AI-generated diagnosis of a Kubernetes pod failure."""
    pod_name: str = Field(description="Name of the diagnosed pod")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    status: str = Field(description="Current pod status (e.g. CrashLoopBackOff)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of the diagnosis"
    )
    issues: list[K8sIssue] = Field(default_factory=list, description="Diagnosed issues")
    summary: str = Field(default="", description="Overall diagnosis summary")
