import unittest

from harness_agent.proposal import ProposalParseError, extract_json_object, parse_proposal


class ProposalParsingTests(unittest.TestCase):
    def test_extracts_balanced_json_with_braces_inside_string(self):
        data = extract_json_object('prefix {"files": [{"path": "x.py", "content": "def f(): return {1: 2}"}]} suffix')
        self.assertEqual(data["files"][0]["path"], "x.py")

    def test_parse_proposal_supports_delete_files(self):
        proposal = parse_proposal(
            """
            {
              "analysis": "x",
              "architecture": "y",
              "files": [{"path": "a.py", "content": "print(1)"}],
              "delete_files": ["old.py"],
              "commands": ["python -m unittest"]
            }
            """
        )
        self.assertEqual(len(proposal.files), 2)
        self.assertTrue(proposal.files[1].delete)

    def test_parse_proposal_rejects_missing_content(self):
        with self.assertRaises(ProposalParseError):
            parse_proposal('{"files": [{"path": "a.py"}]}')


if __name__ == "__main__":
    unittest.main()
