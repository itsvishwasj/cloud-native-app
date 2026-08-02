"""
Professional HTML report generator for AI Code Review results.

Generates modern, responsive HTML reports from ReviewReport Pydantic
models or from JSON report files. Features color-coded score gauges,
severity badges, expandable per-file sections, and syntax-highlighted
corrected code suggestions.
"""

import json
import os
from html import escape

from logger import get_logger
from models import FileReview, ReviewReport, SeverityLevel

logger = get_logger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _score_color(score: int) -> str:
    """Return CSS color based on score value."""
    if score >= 90:
        return "#10b981"  # green
    if score >= 70:
        return "#f59e0b"  # amber
    if score >= 50:
        return "#f97316"  # orange
    return "#ef4444"  # red


def _severity_color(severity: str) -> str:
    """Return CSS color for a severity level."""
    colors = {
        "critical": "#dc2626",
        "high": "#ef4444",
        "medium": "#f59e0b",
        "low": "#22c55e",
    }
    return colors.get(severity.lower(), "#6b7280")


def _severity_bg(severity: str) -> str:
    """Return CSS background color for severity badges."""
    colors = {
        "critical": "rgba(220, 38, 38, 0.15)",
        "high": "rgba(239, 68, 68, 0.15)",
        "medium": "rgba(245, 158, 11, 0.15)",
        "low": "rgba(34, 197, 94, 0.15)",
    }
    return colors.get(severity.lower(), "rgba(107, 114, 128, 0.15)")


def _category_label(category: str) -> str:
    """Human-readable label for issue categories."""
    labels = {
        "logic_bug": "Logic Bug",
        "runtime_bug": "Runtime Bug",
        "security": "Security",
        "performance": "Performance",
        "kubernetes": "Kubernetes",
        "cicd": "CI/CD",
        "code_smell": "Code Smell",
        "best_practice": "Best Practice",
    }
    return labels.get(category, category.replace("_", " ").title())


def generate_html_from_report(report: ReviewReport) -> str:
    """
    Generate a professional HTML report from a ReviewReport model.

    Args:
        report: Validated ReviewReport Pydantic model.

    Returns:
        Complete HTML string.
    """
    score = report.overall_score
    sc = _score_color(score)

    # Build issue rows for each file
    file_sections = ""
    for file_review in report.file_reviews:
        fsc = _score_color(file_review.score)
        issue_rows = ""
        for issue in file_review.issues:
            sev = issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)
            cat = issue.category.value if hasattr(issue.category, "value") else str(issue.category)
            corrected = ""
            if issue.corrected_code:
                corrected = f"""
                <details class="corrected-code">
                  <summary>View Suggested Fix</summary>
                  <pre><code>{escape(issue.corrected_code)}</code></pre>
                </details>"""

            issue_rows += f"""
            <tr>
              <td><span class="severity-badge" style="color:{_severity_color(sev)};background:{_severity_bg(sev)}">{escape(sev)}</span></td>
              <td><span class="category-badge">{escape(_category_label(cat))}</span></td>
              <td class="line-num">{issue.line if issue.line else "—"}</td>
              <td>
                <strong>{escape(issue.issue)}</strong>
                <p class="explanation">{escape(issue.explanation)}</p>
              </td>
              <td>
                {escape(issue.suggestion)}
                {corrected}
              </td>
            </tr>"""

        issue_count = len(file_review.issues)
        file_sections += f"""
        <div class="file-section">
          <div class="file-header" onclick="this.parentElement.classList.toggle('expanded')">
            <div class="file-info">
              <span class="file-icon">📄</span>
              <span class="file-name">{escape(file_review.filename)}</span>
            </div>
            <div class="file-meta">
              <span class="file-score" style="color:{fsc}">{file_review.score}/100</span>
              <span class="issue-count">{issue_count} issue{"s" if issue_count != 1 else ""}</span>
              <span class="expand-icon">▶</span>
            </div>
          </div>
          <div class="file-body">
            {f'<p class="file-summary">{escape(file_review.summary)}</p>' if file_review.summary else ""}
            {"<p class='no-issues'>✅ No issues detected</p>" if not file_review.issues else f'''
            <table class="issues-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Category</th>
                  <th>Line</th>
                  <th>Issue</th>
                  <th>Suggestion</th>
                </tr>
              </thead>
              <tbody>
                {issue_rows}
              </tbody>
            </table>'''}
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Code Review Report</title>
<style>
  :root {{
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-tertiary: #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --border-color: #475569;
    --accent: #3b82f6;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    padding: 2rem;
  }}
  .container {{
    max-width: 1200px;
    margin: 0 auto;
  }}
  .header {{
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color);
  }}
  .header h1 {{
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header .subtitle {{
    color: var(--text-secondary);
    font-size: 0.9rem;
  }}
  .score-section {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 3rem;
    margin: 2rem 0;
    flex-wrap: wrap;
  }}
  .score-gauge {{
    position: relative;
    width: 160px;
    height: 160px;
  }}
  .score-gauge svg {{
    transform: rotate(-90deg);
  }}
  .score-gauge circle {{
    fill: none;
    stroke-width: 10;
  }}
  .score-gauge .bg {{ stroke: var(--bg-tertiary); }}
  .score-gauge .fg {{
    stroke: {sc};
    stroke-dasharray: {score * 4.4} {440 - score * 4.4};
    stroke-linecap: round;
    transition: stroke-dasharray 1s ease;
  }}
  .score-value {{
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
  }}
  .score-value .number {{
    font-size: 2.5rem;
    font-weight: 800;
    color: {sc};
  }}
  .score-value .label {{
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .severity-cards {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }}
  .sev-card {{
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 1rem 1.5rem;
    text-align: center;
    min-width: 100px;
  }}
  .sev-card .count {{
    font-size: 2rem;
    font-weight: 800;
  }}
  .sev-card .sev-label {{
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .meta-bar {{
    display: flex;
    gap: 2rem;
    justify-content: center;
    margin: 1.5rem 0;
    color: var(--text-secondary);
    font-size: 0.85rem;
    flex-wrap: wrap;
  }}
  .meta-bar span {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }}
  .file-section {{
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    margin-bottom: 1rem;
    overflow: hidden;
  }}
  .file-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    cursor: pointer;
    transition: background 0.2s;
  }}
  .file-header:hover {{
    background: var(--bg-tertiary);
  }}
  .file-info {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }}
  .file-name {{
    font-weight: 600;
    font-family: 'Courier New', monospace;
    font-size: 0.95rem;
  }}
  .file-meta {{
    display: flex;
    align-items: center;
    gap: 1rem;
  }}
  .file-score {{
    font-weight: 700;
    font-size: 1rem;
  }}
  .issue-count {{
    color: var(--text-secondary);
    font-size: 0.85rem;
  }}
  .expand-icon {{
    transition: transform 0.2s;
    color: var(--text-secondary);
  }}
  .file-section.expanded .expand-icon {{
    transform: rotate(90deg);
  }}
  .file-body {{
    display: none;
    padding: 0 1.5rem 1.5rem;
  }}
  .file-section.expanded .file-body {{
    display: block;
  }}
  .file-summary {{
    color: var(--text-secondary);
    margin-bottom: 1rem;
    font-style: italic;
  }}
  .no-issues {{
    color: #10b981;
    padding: 1rem;
    text-align: center;
  }}
  .issues-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .issues-table th {{
    background: var(--bg-tertiary);
    padding: 0.75rem 1rem;
    text-align: left;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-color);
  }}
  .issues-table td {{
    padding: 0.75rem 1rem;
    border-bottom: 1px solid rgba(71, 85, 105, 0.5);
    vertical-align: top;
    font-size: 0.9rem;
  }}
  .issues-table tr:last-child td {{
    border-bottom: none;
  }}
  .severity-badge {{
    padding: 0.25rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }}
  .category-badge {{
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.78rem;
    white-space: nowrap;
  }}
  .line-num {{
    font-family: 'Courier New', monospace;
    color: var(--text-secondary);
    text-align: center;
  }}
  .explanation {{
    color: var(--text-secondary);
    font-size: 0.82rem;
    margin-top: 0.3rem;
  }}
  .corrected-code {{
    margin-top: 0.5rem;
  }}
  .corrected-code summary {{
    cursor: pointer;
    color: var(--accent);
    font-size: 0.82rem;
    font-weight: 600;
  }}
  .corrected-code pre {{
    background: var(--bg-primary);
    padding: 0.75rem;
    border-radius: 8px;
    margin-top: 0.5rem;
    overflow-x: auto;
    font-size: 0.82rem;
    border: 1px solid var(--border-color);
  }}
  .corrected-code code {{
    color: #e2e8f0;
    font-family: 'Courier New', monospace;
  }}
  .footer {{
    text-align: center;
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border-color);
    color: var(--text-secondary);
    font-size: 0.8rem;
  }}
  @media (max-width: 768px) {{
    body {{ padding: 1rem; }}
    .score-section {{ gap: 1.5rem; }}
    .severity-cards {{ justify-content: center; }}
    .file-header {{ flex-direction: column; gap: 0.5rem; }}
    .issues-table {{ font-size: 0.8rem; }}
    .issues-table th, .issues-table td {{ padding: 0.5rem; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🤖 AI Code Review Report</h1>
    <p class="subtitle">Automated analysis powered by Google Gemini</p>
  </div>

  <div class="score-section">
    <div class="score-gauge">
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle class="bg" cx="80" cy="80" r="70"/>
        <circle class="fg" cx="80" cy="80" r="70"/>
      </svg>
      <div class="score-value">
        <div class="number">{score}</div>
        <div class="label">Overall Score</div>
      </div>
    </div>
    <div class="severity-cards">
      <div class="sev-card">
        <div class="count" style="color:#dc2626">{report.critical_count}</div>
        <div class="sev-label">Critical</div>
      </div>
      <div class="sev-card">
        <div class="count" style="color:#ef4444">{report.high_count}</div>
        <div class="sev-label">High</div>
      </div>
      <div class="sev-card">
        <div class="count" style="color:#f59e0b">{report.medium_count}</div>
        <div class="sev-label">Medium</div>
      </div>
      <div class="sev-card">
        <div class="count" style="color:#22c55e">{report.low_count}</div>
        <div class="sev-label">Low</div>
      </div>
    </div>
  </div>

  <div class="meta-bar">
    <span>📁 {report.total_files_reviewed} file{"s" if report.total_files_reviewed != 1 else ""} reviewed</span>
    <span>🔍 {report.total_issues} total issue{"s" if report.total_issues != 1 else ""}</span>
    <span>🕐 {report.timestamp}</span>
    {f'<span>🔀 Branch: {escape(report.branch)}</span>' if report.branch else ""}
    {f'<span>📝 Commit: {escape(report.commit_sha[:8]) if report.commit_sha else ""}</span>' if report.commit_sha else ""}
  </div>

  <h2 style="margin:1.5rem 0 1rem;font-size:1.2rem;">📋 File Reviews</h2>

  {file_sections}

  <div class="footer">
    <p>Generated by AI Code Review Service • Powered by Google Gemini</p>
    <p style="margin-top:0.3rem;">{report.timestamp}</p>
  </div>
</div>
</body>
</html>"""

    return html


def generate_html(report: ReviewReport | None = None) -> str:
    """
    Generate HTML report from a ReviewReport or from JSON files on disk.

    Args:
        report: Optional ReviewReport model. If None, reads from reports dir.

    Returns:
        HTML string of the generated report.
    """
    if report is None:
        # Load from consolidated report file
        consolidated_path = os.path.join(REPORTS_DIR, "review_report.json")
        if os.path.exists(consolidated_path):
            logger.info("Loading consolidated report from %s", consolidated_path)
            with open(consolidated_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            report = ReviewReport(**data)
        else:
            # Fallback: load individual JSON reports
            logger.info("No consolidated report found, loading individual reports")
            json_files = [
                f for f in os.listdir(REPORTS_DIR)
                if f.endswith(".json") and f != "review_report.json"
            ]

            if not json_files:
                logger.warning("No JSON reports found in %s", REPORTS_DIR)
                return "<html><body><h1>No reports available</h1></body></html>"

            file_reviews = []
            for jf in json_files:
                try:
                    with open(os.path.join(REPORTS_DIR, jf), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    file_reviews.append(FileReview(**data))
                except Exception as e:
                    logger.warning("Failed to load report %s: %s", jf, e)

            if not file_reviews:
                return "<html><body><h1>No valid reports found</h1></body></html>"

            scores = [fr.score for fr in file_reviews if fr.score > 0]
            overall = round(sum(scores) / len(scores)) if scores else 0

            report = ReviewReport(
                overall_score=overall,
                file_reviews=file_reviews,
            )
            report.compute_counts()

    html = generate_html_from_report(report)

    # Save HTML report
    os.makedirs(REPORTS_DIR, exist_ok=True)
    output_path = os.path.join(REPORTS_DIR, "report.html")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("HTML report generated: %s", output_path)
    except OSError as e:
        logger.error("Failed to save HTML report: %s", e)

    return html


if __name__ == "__main__":
    generate_html()
