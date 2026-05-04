from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_metrics
from .llm import LLMError, MockLLMClient, OpenAICompatibleClient
from .loop import HarnessEngineeringAgent
from .workspace import GeneratedWorkspace


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness-agent",
        description="Closed-loop agent for generating and tuning harness engineering code.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Generate and iteratively tune a harness codebase.")
    run.add_argument("--task", required=True, help="Task text or path to a task markdown/text file.")
    run.add_argument("--metrics", help="Path to metrics JSON. Defaults to unittest discovery.")
    run.add_argument("--out", required=True, help="Output directory for generated harness code.")
    run.add_argument("--max-iters", type=int, help="Override max_iterations from metrics JSON.")
    run.add_argument("--mock", action="store_true", help="Use deterministic mock LLM client.")
    run.add_argument("--model", help="Model name. Overrides HARNESS_LLM_MODEL.")
    run.add_argument("--base-url", help="OpenAI-compatible base URL. Overrides HARNESS_LLM_BASE_URL.")
    run.add_argument("--api-key-env", default="HARNESS_LLM_API_KEY", help="Environment variable containing API key.")
    run.add_argument("--timeout", type=int, default=120, help="LLM request timeout in seconds.")
    run.add_argument("--temperature", type=float, default=None, help="Optional sampling temperature.")
    return parser


def run_command(args: argparse.Namespace) -> int:
    task = read_task(args.task)
    metrics = load_metrics(args.metrics).with_max_iterations(args.max_iters)
    workspace = GeneratedWorkspace(args.out)

    if args.mock:
        llm = MockLLMClient()
    else:
        try:
            llm = OpenAICompatibleClient.from_env(
                model=args.model,
                base_url=args.base_url,
                api_key_env=args.api_key_env,
                temperature=args.temperature,
                timeout_seconds=args.timeout,
            )
        except LLMError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2

    agent = HarnessEngineeringAgent(llm=llm, workspace=workspace, metrics=metrics)
    try:
        result = agent.run(task)
    except LLMError as exc:
        print(f"LLM error: {exc}", file=sys.stderr)
        return 1

    print(f"output_dir={result.output_dir}")
    print(f"iterations={len(result.iterations)}")
    print(f"passed={result.passed}")
    print(f"best_score={result.best_score:.3f}")
    if result.last_evaluation is not None:
        print(result.last_evaluation.summary())
    return 0 if result.passed else 1


def read_task(value: str) -> str:
    try:
        path = Path(value)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return value
