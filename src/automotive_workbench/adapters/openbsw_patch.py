from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        capture_output=True,
    )


def _require_git_repo(repo: Path) -> None:
    if not repo.exists():
        raise ValueError(f"OpenBSW repository does not exist: {repo}")
    result = _git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise ValueError(f"Path is not a Git work tree: {repo}")


def _parse_status(porcelain: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        entries.append(
            {
                "index_status": line[0],
                "worktree_status": line[1],
                "path": line[3:],
            }
        )
    return entries


def prepare_openbsw_patch(repo: Path, output: Path) -> dict[str, Any]:
    """Package local OpenBSW spike edits as reviewable evidence."""
    repo = repo.expanduser().resolve()
    _require_git_repo(repo)

    remote = _git(repo, "config", "--get", "remote.origin.url", check=False)
    commit = _git(repo, "rev-parse", "HEAD").stdout.strip()
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    status_text = _git(repo, "status", "--porcelain=v1").stdout
    patch_text = _git(repo, "diff", "--binary").stdout
    status_entries = _parse_status(status_text)
    untracked = [entry["path"] for entry in status_entries if entry["index_status"] == "?" and entry["worktree_status"] == "?"]
    tracked_dirty = [
        entry["path"]
        for entry in status_entries
        if not (entry["index_status"] == "?" and entry["worktree_status"] == "?")
    ]
    patch_sha256 = hashlib.sha256(patch_text.encode("utf-8")).hexdigest()
    status = "ready" if patch_text else "empty"

    result: dict[str, Any] = {
        "artifact_type": "openbsw-patch-evidence",
        "status": status,
        "repo": str(repo),
        "remote_url": remote.stdout.strip(),
        "commit": commit,
        "branch": branch,
        "dirty_file_count": len(status_entries),
        "tracked_dirty_files": tracked_dirty,
        "untracked_files": untracked,
        "patch_file": str(output / "openbsw-local-changes.patch"),
        "patch_sha256": patch_sha256,
        "notes": [
            "Patch evidence is generated from local working tree changes only.",
            "Untracked files are listed in the manifest but are not included in git diff output.",
            "This artifact does not submit or claim acceptance of an upstream pull request.",
        ],
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / "openbsw-local-changes.patch").write_text(patch_text, encoding="utf-8")
    (output / "openbsw-patch-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = [
        "# OpenBSW Patch Evidence",
        "",
        f"- Status: **{status}**",
        f"- Repository: `{repo}`",
        f"- Remote: `{result['remote_url'] or 'none'}`",
        f"- Commit: `{commit}`",
        f"- Branch: `{branch}`",
        f"- Dirty files: `{len(status_entries)}`",
        f"- Patch SHA-256: `{patch_sha256}`",
        "",
        "## Tracked Dirty Files",
        "",
    ]
    markdown.extend(f"- `{path}`" for path in tracked_dirty)
    if not tracked_dirty:
        markdown.append("- none")
    markdown.extend(["", "## Untracked Files", ""])
    markdown.extend(f"- `{path}`" for path in untracked)
    if not untracked:
        markdown.append("- none")
    markdown.extend(["", "## Boundary", ""])
    markdown.extend(f"- {note}" for note in result["notes"])
    (output / "openbsw-patch-manifest.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return result
