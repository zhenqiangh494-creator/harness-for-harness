from __future__ import annotations

import json

from .config import MetricConfig


SYSTEM_PROMPT = """You are a senior harness engineering agent.

Your job is to generate and iteratively improve a complete harness engineering codebase for the user's task.
You must use the task, evaluation metrics, current workspace files, and previous test feedback to decide whether to patch implementation details or change the harness architecture.

Return only a strict JSON object. Do not wrap it in Markdown.

JSON schema:
{
  "analysis": "brief diagnosis and design rationale",
  "architecture": "current harness architecture and why it fits the metrics",
  "files": [
    {"path": "relative/path.py", "content": "complete file content"},
    {"path": "obsolete/file.py", "delete": true}
  ],
  "commands": ["optional local commands useful when no metric command is configured"],
  "notes": "short operational notes"
}

Rules:
- All paths must be relative and stay inside the generated workspace.
- Emit complete file contents, not diffs.
- Include tests or evaluators that exercise the harness contract.
- Keep secrets in environment variables only.
- Prefer Python standard library unless the task clearly requires a dependency.
- If evaluation failed, use the concrete stdout/stderr feedback to fix the root cause.
- You may redesign modules, interfaces, and test layout when the feedback shows the current architecture is weak.
- Do not game the metric; build a real harness that satisfies the task.
"""


def build_iteration_prompt(
    *,
    task: str,
    metrics: MetricConfig,
    workspace_snapshot: str,
    feedback: str,
    iteration: int,
) -> str:
    metrics_json = json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False)
    return f"""Iteration: {iteration}

Task:
{task}

Evaluation metrics:
```json
{metrics_json}
```

Current generated workspace:
{workspace_snapshot}

Latest feedback:
{feedback or "<no previous feedback>"}

Generate the next complete JSON proposal now. The proposal should either create the first harness architecture or improve the existing one based on feedback.
"""
