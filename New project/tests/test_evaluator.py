import sys
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from harness_agent.config import EvaluationCommand, MetricConfig
from harness_agent.evaluator import EvaluationRunner


REPO_TMP = Path(__file__).resolve().parents[1] / ".harness_tmp"


@contextmanager
def temp_dir():
    REPO_TMP.mkdir(exist_ok=True)
    path = REPO_TMP / f"evaluator_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class EvaluatorTests(unittest.TestCase):
    def test_extracts_score_from_command_output(self):
        command = f'"{sys.executable}" -c "print(\'score=0.75\')"'
        metrics = MetricConfig(
            commands=[
                EvaluationCommand(
                    name="score",
                    command=command,
                    score_regex=r"score=([0-9.]+)",
                )
            ],
            target_score=0.7,
        )
        with temp_dir() as temp:
            report = EvaluationRunner(metrics).run(Path(temp))
        self.assertTrue(report.passed)
        self.assertAlmostEqual(report.aggregate_score, 0.75)

    def test_can_pass_on_score_even_when_command_fails(self):
        command = f'"{sys.executable}" -c "print(\'score=0.80\'); raise SystemExit(1)"'
        metrics = MetricConfig(
            commands=[
                EvaluationCommand(
                    name="score",
                    command=command,
                    score_regex=r"score=([0-9.]+)",
                )
            ],
            target_score=0.8,
            stop_on_all_pass=False,
        )
        with temp_dir() as temp:
            report = EvaluationRunner(metrics).run(Path(temp))
        self.assertTrue(report.passed)
        self.assertFalse(report.results[0].passed)


if __name__ == "__main__":
    unittest.main()
