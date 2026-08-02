"""
Git diff utilities for reading changed files from the repository.

Handles edge cases such as shallow clones (common in CI/CD), binary
files, and git command failures. Provides both file content and diff
hunks for richer AI analysis context.
"""

import os
import subprocess

from logger import get_logger

logger = get_logger(__name__)

# File extensions to skip (binary / non-reviewable)
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pyc", ".pyo", ".class", ".o", ".obj",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".db", ".sqlite", ".sqlite3",
    ".lock",
}


def get_repo_root() -> str:
    """Get the root directory of the current git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error("Failed to determine git repo root: %s", e.stderr.strip())
        raise RuntimeError("Not inside a git repository") from e


def get_changed_files() -> list[str]:
    """
    Get the list of files changed in the latest commit.

    Falls back to staged changes if HEAD~1 is unavailable (shallow clone).
    """
    # Strategy 1: diff between HEAD~1 and HEAD (normal clone)
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and result.stdout.strip():
        files = [f for f in result.stdout.splitlines() if f.strip()]
        logger.info("Found %d changed files (HEAD~1..HEAD)", len(files))
        return files

    # Strategy 2: diff of staged changes (shallow clone / first commit)
    logger.warning("HEAD~1 not available, falling back to staged changes")
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "HEAD"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and result.stdout.strip():
        files = [f for f in result.stdout.splitlines() if f.strip()]
        logger.info("Found %d staged files", len(files))
        return files

    # Strategy 3: show files in the latest commit (works with fetch-depth: 1)
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and result.stdout.strip():
        files = [f for f in result.stdout.splitlines() if f.strip()]
        logger.info("Found %d files in HEAD commit (diff-tree)", len(files))
        return files

    logger.warning("No changed files detected by any strategy")
    return []


def _should_skip(filepath: str) -> bool:
    """Check if a file should be skipped based on its extension."""
    _, ext = os.path.splitext(filepath)
    return ext.lower() in SKIP_EXTENSIONS


def read_changed_files() -> dict[str, str]:
    """
    Read the contents of all changed files, skipping binary files.

    Returns:
        Dictionary mapping relative file paths to their contents.
    """
    repo_root = get_repo_root()
    changed_files = get_changed_files()

    file_contents: dict[str, str] = {}

    for filepath in changed_files:
        if _should_skip(filepath):
            logger.debug("Skipping binary/non-reviewable file: %s", filepath)
            continue

        full_path = os.path.join(repo_root, filepath)

        if not os.path.exists(full_path):
            logger.warning("File does not exist (possibly deleted): %s", filepath)
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_contents[filepath] = f.read()
            logger.debug("Read file: %s (%d bytes)", filepath, len(file_contents[filepath]))
        except UnicodeDecodeError:
            logger.warning("Skipping binary file (decode error): %s", filepath)
        except OSError as e:
            logger.error("Failed to read file %s: %s", filepath, e)

    logger.info("Read %d reviewable files out of %d changed", len(file_contents), len(changed_files))
    return file_contents


def get_git_metadata() -> dict[str, str]:
    """Get current git commit SHA and branch name for report metadata."""
    metadata: dict[str, str] = {}

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        metadata["commit_sha"] = result.stdout.strip()
    except subprocess.CalledProcessError:
        metadata["commit_sha"] = "unknown"

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        metadata["branch"] = result.stdout.strip()
    except subprocess.CalledProcessError:
        metadata["branch"] = "unknown"

    return metadata


if __name__ == "__main__":

    print("Repository Root:")
    print(get_repo_root())

    print("\nChanged Files:")
    print(get_changed_files())

    print("\nGit Metadata:")
    print(get_git_metadata())

    print("\nReading Files...\n")

    contents = read_changed_files()

    for file, code in contents.items():
        print("=" * 60)
        print(file)
        print("=" * 60)
        print(code[:500])
