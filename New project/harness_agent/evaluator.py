from __future__ import annotations

import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import EvaluationCommand, MetricConfig


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    score: float
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationReport:
    results: list[CommandResult]
    aggregate_score: float
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "aggregate_score": self.aggregate_score,
            "passed": self.passed,
            "results": [result.to_dict() for result in self.results],
        }

    def summary(self, limit: int = 4000) -> str:
        lines = [f"passed={self.passed} aggregate_score={self.aggregate_score:.3f}"]
        for result in self.results:
            lines.append(
                f"[{result.name}] passed={result.passed} score={result.score:.3f} "
                f"exit={result.exit_code} duration={result.duration_seconds:.2f}s"
            )
            output = _trim("\n".join(part for part in [result.stdout, result.stderr] if part), limit)
            if output:
                lines.append(output)
        return "\n".join(lines)


class EvaluationRunner:
    def __init__(self, metrics: MetricConfig):
        self.metrics = metrics

    def run(self, cwd: Path, fallback_commands: list[str] | None = None) -> EvaluationReport:
        commands = self.metrics.commands
        if not commands and fallback_commands:
            commands = [
                EvaluationCommand(name=f"proposal-{index + 1}", command=command)
                for index, command in enumerate(fallback_commands)
            ]
        if not commands:
            commands = MetricConfig.default().commands

        results = [self._run_command(command, cwd) for command in commands]
        aggregate = sum(result.score for result in results) / len(results)
        if self.metrics.stop_on_all_pass:
            passed = all(result.passed for result in results) and aggregate >= self.metrics.target_score
        else:
            passed = aggregate >= self.metrics.target_score
        return EvaluationReport(results=results, aggregate_score=aggregate, passed=passed)

    def _run_command(self, command: EvaluationCommand, cwd: Path) -> CommandResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command.command,
                cwd=str(cwd),
                shell=True,
                text=True,
                capture_output=True,
                timeout=command.timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            stderr = f"{stderr}\nCommand timed out after {command.timeout_seconds}s.".strip()

        duration = time.monotonic() - started
        combined = f"{stdout}\n{stderr}"
        score = _extract_score(combined, command.score_regex)
        regex_passed = True
        if command.pass_regex:
            regex_passed = re.search(command.pass_regex, combined, flags=re.MULTILINE) is not None
        passed = exit_code == 0 and regex_passed
        if score is None:
            score = 1.0 if passed else 0.0
        return CommandResult(
            name=command.name,
            command=command.command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            score=score,
            passed=passed,
        )


def _extract_score(output: str, score_regex: str | None) -> float | None:
    if not score_regex:
        return None
    match = re.search(score_regex, output, flags=re.MULTILINE)
    if not match:
        return 0.0
    value = match.group(1) if match.groups() else match.group(0)
    try:
        return float(value)
    except ValueError:
        return 0.0


def _trim(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"
