import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from harness_agent.config import EvaluationCommand, MetricConfig
from harness_agent.llm import ChatMessage
from harness_agent.loop import HarnessEngineeringAgent
from harness_agent.workspace import GeneratedWorkspace


REPO_TMP = Path(__file__).resolve().parents[1] / ".harness_tmp"


@contextmanager
def temp_dir():
    REPO_TMP.mkdir(exist_ok=True)
    path = REPO_TMP / f"loop_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages: list[list[ChatMessage]] = []

    def complete(self, messages: list[ChatMessage]) -> str:
        self.messages.append(messages)
        return self.responses.pop(0)


class LoopTests(unittest.TestCase):
    def test_agent_generates_and_evaluates_until_pass(self):
        proposal = {
            "analysis": "create passing harness",
            "architecture": "single module plus unittest",
            "files": [
                {"path": "harness.py", "content": "def run():\n    return 'ok'\n"},
                {
                    "path": "tests/test_contract.py",
                    "content": (
                        "import unittest\n"
                        "import harness\n\n"
                        "class ContractTest(unittest.TestCase):\n"
                        "    def test_run(self):\n"
                        "        self.assertEqual(harness.run(), 'ok')\n\n"
                        "if __name__ == '__main__':\n"
                        "    unittest.main()\n"
                    ),
                },
            ],
            "commands": [],
        }
        command = f'"{sys.executable}" -m unittest discover -s tests'
        metrics = MetricConfig(
            commands=[EvaluationCommand(name="unit", command=command)],
            max_iterations=2,
            target_score=1.0,
        )
        with temp_dir() as temp:
            agent = HarnessEngineeringAgent(
                llm=ScriptedLLM([json.dumps(proposal)]),
                workspace=GeneratedWorkspace(temp),
                metrics=metrics,
            )
            result = agent.run("make a tiny harness")
            self.assertTrue(result.passed)
            self.assertEqual(result.best_score, 1.0)
            self.assertTrue((Path(temp) / "harness.py").exists())


if __name__ == "__main__":
    unittest.main()
