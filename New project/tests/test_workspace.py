import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from harness_agent.proposal import FileEdit, IterationProposal
from harness_agent.workspace import GeneratedWorkspace, WorkspaceSecurityError, safe_join


REPO_TMP = Path(__file__).resolve().parents[1] / ".harness_tmp"


@contextmanager
def temp_dir():
    REPO_TMP.mkdir(exist_ok=True)
    path = REPO_TMP / f"workspace_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class WorkspaceTests(unittest.TestCase):
    def test_safe_join_rejects_parent_escape(self):
        with temp_dir() as temp:
            with self.assertRaises(WorkspaceSecurityError):
                safe_join(Path(temp), "../outside.py")

    def test_apply_writes_inside_workspace(self):
        with temp_dir() as temp:
            workspace = GeneratedWorkspace(temp)
            proposal = IterationProposal(
                analysis="",
                architecture="",
                files=[FileEdit(path="src/harness.py", content="VALUE = 1\n")],
                commands=[],
            )
            changed = workspace.apply(proposal)
            self.assertEqual(len(changed), 1)
            self.assertEqual((Path(temp) / "src" / "harness.py").read_text(encoding="utf-8"), "VALUE = 1\n")


if __name__ == "__main__":
    unittest.main()
