from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .config import MetricConfig
from .proposal import FileEdit, IterationProposal


class WorkspaceSecurityError(ValueError):
    """Raised when a generated file path tries to escape the output directory."""


class GeneratedWorkspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.agent_dir = self.root / ".harness_agent"
        self.iterations_dir = self.agent_dir / "iterations"

    def prepare(self, task: str, metrics: MetricConfig) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.iterations_dir.mkdir(parents=True, exist_ok=True)
        (self.agent_dir / "task.md").write_text(task, encoding="utf-8")
        (self.agent_dir / "metrics.json").write_text(
            json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def apply(self, proposal: IterationProposal) -> list[Path]:
        changed: list[Path] = []
        for edit in proposal.files:
            target = safe_join(self.root, edit.path)
            if edit.delete:
                self._delete(target)
                changed.append(target)
                continue
            if edit.content is None:
                raise ValueError(f"File edit for {edit.path!r} has no content.")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(edit.content, encoding="utf-8", newline="")
            changed.append(target)
        return changed

    def snapshot(self, *, max_files: int = 40, max_bytes_per_file: int = 12000, max_total: int = 60000) -> str:
        if not self.root.exists():
            return "<workspace does not exist>"

        chunks: list[str] = []
        total = 0
        files = [
            path
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not _is_ignored(path.relative_to(self.root))
        ]
        for path in files[:max_files]:
            rel = path.relative_to(self.root).as_posix()
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if len(content.encode("utf-8")) > max_bytes_per_file:
                content = content[:max_bytes_per_file] + "\n...[file truncated]"
            chunk = f"\n--- FILE: {rel} ---\n{content}"
            if total + len(chunk) > max_total:
                chunks.append("\n...[workspace snapshot truncated]")
                break
            chunks.append(chunk)
            total += len(chunk)

        if not chunks:
            return "<empty workspace>"
        return "\n".join(chunks)

    def record_iteration(
        self,
        iteration: int,
        *,
        raw_response: str,
        proposal: IterationProposal | None,
        evaluation: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        self.iterations_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "iteration": iteration,
            "raw_response": raw_response,
            "proposal": proposal.to_dict() if proposal else None,
            "evaluation": evaluation,
            "error": error,
        }
        path = self.iterations_dir / f"{iteration:03d}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _delete(self, target: Path) -> None:
        if not target.exists():
            return
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


def safe_join(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise WorkspaceSecurityError(f"Absolute paths are not allowed: {relative_path}")
    if any(part in {"..", ""} for part in candidate.parts):
        raise WorkspaceSecurityError(f"Unsafe relative path: {relative_path}")
    resolved = (root / candidate).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise WorkspaceSecurityError(f"Path escapes workspace: {relative_path}")
    return resolved


def _is_ignored(path: Path) -> bool:
    ignored_parts = {".git", ".harness_agent", "__pycache__", ".pytest_cache", ".mypy_cache"}
    return any(part in ignored_parts for part in path.parts)
