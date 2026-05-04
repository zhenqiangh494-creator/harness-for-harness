from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationCommand:
    name: str
    command: str
    timeout_seconds: int = 120
    score_regex: str | None = None
    pass_regex: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationCommand":
        if "name" not in data or "command" not in data:
            raise ValueError("Each evaluation command requires 'name' and 'command'.")
        return cls(
            name=str(data["name"]),
            command=str(data["command"]),
            timeout_seconds=int(data.get("timeout_seconds", 120)),
            score_regex=data.get("score_regex"),
            pass_regex=data.get("pass_regex"),
        )


@dataclass(frozen=True)
class MetricConfig:
    commands: list[EvaluationCommand] = field(default_factory=list)
    max_iterations: int = 5
    target_score: float = 1.0
    stop_on_all_pass: bool = True

    @classmethod
    def default(cls) -> "MetricConfig":
        return cls(
            commands=[
                EvaluationCommand(
                    name="unit",
                    command="python -m unittest discover -s tests",
                    timeout_seconds=120,
                )
            ],
            max_iterations=5,
            target_score=1.0,
            stop_on_all_pass=True,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetricConfig":
        raw_commands = data.get("commands", data.get("evaluation_commands", []))
        commands = [EvaluationCommand.from_dict(item) for item in raw_commands]
        return cls(
            commands=commands,
            max_iterations=int(data.get("max_iterations", 5)),
            target_score=float(data.get("target_score", 1.0)),
            stop_on_all_pass=bool(data.get("stop_on_all_pass", True)),
        )

    def with_max_iterations(self, value: int | None) -> "MetricConfig":
        if value is None:
            return self
        return MetricConfig(
            commands=self.commands,
            max_iterations=value,
            target_score=self.target_score,
            stop_on_all_pass=self.stop_on_all_pass,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_metrics(path: str | Path | None) -> MetricConfig:
    if path is None:
        return MetricConfig.default()

    metrics_path = Path(path)
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Metrics file must contain a JSON object.")
    return MetricConfig.from_dict(data)
