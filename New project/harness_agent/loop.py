from __future__ import annotations

from dataclasses import dataclass

from .config import MetricConfig
from .evaluator import EvaluationReport, EvaluationRunner
from .llm import ChatMessage, LLMClient
from .prompts import SYSTEM_PROMPT, build_iteration_prompt
from .proposal import IterationProposal, ProposalParseError, parse_proposal
from .workspace import GeneratedWorkspace


@dataclass(frozen=True)
class IterationResult:
    iteration: int
    proposal: IterationProposal | None
    evaluation: EvaluationReport | None
    error: str | None


@dataclass(frozen=True)
class RunResult:
    output_dir: str
    iterations: list[IterationResult]
    passed: bool
    best_score: float

    @property
    def last_evaluation(self) -> EvaluationReport | None:
        for iteration in reversed(self.iterations):
            if iteration.evaluation is not None:
                return iteration.evaluation
        return None


class HarnessEngineeringAgent:
    def __init__(self, llm: LLMClient, workspace: GeneratedWorkspace, metrics: MetricConfig):
        self.llm = llm
        self.workspace = workspace
        self.metrics = metrics
        self.evaluator = EvaluationRunner(metrics)

    def run(self, task: str) -> RunResult:
        self.workspace.prepare(task, self.metrics)
        feedback = ""
        iterations: list[IterationResult] = []
        best_score = 0.0

        for iteration in range(1, self.metrics.max_iterations + 1):
            messages = [
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=build_iteration_prompt(
                        task=task,
                        metrics=self.metrics,
                        workspace_snapshot=self.workspace.snapshot(),
                        feedback=feedback,
                        iteration=iteration,
                    ),
                ),
            ]
            raw_response = self.llm.complete(messages)

            try:
                proposal = parse_proposal(raw_response)
            except ProposalParseError as exc:
                error = f"Model proposal parse error: {exc}"
                self.workspace.record_iteration(
                    iteration,
                    raw_response=raw_response,
                    proposal=None,
                    evaluation=None,
                    error=error,
                )
                iterations.append(
                    IterationResult(
                        iteration=iteration,
                        proposal=None,
                        evaluation=None,
                        error=error,
                    )
                )
                feedback = (
                    f"{error}\nReturn only the required JSON object with complete file contents. "
                    f"Raw response was:\n{raw_response[:4000]}"
                )
                continue

            error = None
            try:
                self.workspace.apply(proposal)
                evaluation = self.evaluator.run(self.workspace.root, fallback_commands=proposal.commands)
            except Exception as exc:  # The feedback still needs to reach the model next round.
                evaluation = None
                error = f"Apply/evaluation error: {type(exc).__name__}: {exc}"

            if evaluation is not None:
                best_score = max(best_score, evaluation.aggregate_score)
                feedback = evaluation.summary()
            else:
                feedback = error or "Unknown error."

            self.workspace.record_iteration(
                iteration,
                raw_response=raw_response,
                proposal=proposal,
                evaluation=evaluation.to_dict() if evaluation else None,
                error=error,
            )
            iterations.append(
                IterationResult(
                    iteration=iteration,
                    proposal=proposal,
                    evaluation=evaluation,
                    error=error,
                )
            )

            if evaluation is not None and evaluation.passed:
                return RunResult(
                    output_dir=str(self.workspace.root),
                    iterations=iterations,
                    passed=True,
                    best_score=best_score,
                )

        return RunResult(
            output_dir=str(self.workspace.root),
            iterations=iterations,
            passed=False,
            best_score=best_score,
        )
