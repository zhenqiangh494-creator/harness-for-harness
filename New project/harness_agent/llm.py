from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class LLMError(RuntimeError):
    """Raised when the model provider cannot complete a request."""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMClient(Protocol):
    def complete(self, messages: list[ChatMessage]) -> str:
        ...


@dataclass
class OpenAICompatibleClient:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 120
    temperature: float | None = None

    @classmethod
    def from_env(
        cls,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key_env: str = "HARNESS_LLM_API_KEY",
        temperature: float | None = None,
        timeout_seconds: int = 120,
    ) -> "OpenAICompatibleClient":
        api_key = os.environ.get(api_key_env) or os.environ.get("OPENAI_API_KEY")
        resolved_model = model or os.environ.get("HARNESS_LLM_MODEL")
        resolved_base_url = base_url or os.environ.get("HARNESS_LLM_BASE_URL", "https://api.openai.com/v1")
        if not api_key:
            raise LLMError(
                f"Missing API key. Set {api_key_env} or OPENAI_API_KEY, or run with --mock."
            )
        if not resolved_model:
            raise LLMError("Missing model. Set HARNESS_LLM_MODEL or pass --model.")
        return cls(
            api_key=api_key,
            model=resolved_model,
            base_url=resolved_base_url,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )

    def complete(self, messages: list[ChatMessage]) -> str:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [message.to_dict() for message in messages],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        request = urllib.request.Request(
            self._endpoint(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM provider returned HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"Cannot reach LLM provider: {exc}") from exc

        data = json.loads(raw)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected LLM response shape: {raw[:500]}") from exc
        if not isinstance(content, str):
            raise LLMError("LLM response content was not a string.")
        return content

    def _endpoint(self) -> str:
        cleaned = self.base_url.rstrip("/")
        if cleaned.endswith("/chat/completions"):
            return cleaned
        return f"{cleaned}/chat/completions"


class MockLLMClient:
    """Deterministic client for smoke-testing the closed loop without network access."""

    def complete(self, messages: list[ChatMessage]) -> str:
        proposal = {
            "analysis": "Create a minimal but testable harness scaffold for the requested task.",
            "architecture": (
                "Single-module harness with a small public run() entrypoint, stdlib tests, "
                "and documentation. Real model calls are expected to be added behind env-based config."
            ),
            "files": [
                {
                    "path": "README.md",
                    "content": (
                        "# Generated Harness\n\n"
                        "This harness scaffold was produced by the mock LLM client. "
                        "Replace `harness.py` internals with task-specific logic when running with a real model.\n"
                    ),
                },
                {
                    "path": "harness.py",
                    "content": (
                        "from __future__ import annotations\n\n"
                        "from dataclasses import dataclass\n"
                        "from typing import Any\n\n\n"
                        "@dataclass\n"
                        "class HarnessResult:\n"
                        "    ok: bool\n"
                        "    output: dict[str, Any]\n\n\n"
                        "def run(task_input: dict[str, Any] | None = None) -> HarnessResult:\n"
                        "    data = task_input or {}\n"
                        "    return HarnessResult(ok=True, output={\"received\": data, \"status\": \"ready\"})\n"
                    ),
                },
                {
                    "path": "tests/test_harness_contract.py",
                    "content": (
                        "import unittest\n\n"
                        "import harness\n\n\n"
                        "class HarnessContractTests(unittest.TestCase):\n"
                        "    def test_run_returns_successful_result(self):\n"
                        "        result = harness.run({\"case\": \"demo\"})\n"
                        "        self.assertTrue(result.ok)\n"
                        "        self.assertEqual(result.output[\"status\"], \"ready\")\n"
                        "        self.assertEqual(result.output[\"received\"], {\"case\": \"demo\"})\n\n\n"
                        "if __name__ == \"__main__\":\n"
                        "    unittest.main()\n"
                    ),
                },
            ],
            "commands": ["python -m unittest discover -s tests"],
            "notes": "Mock run is intended to validate agent plumbing.",
        }
        return json.dumps(proposal, ensure_ascii=False)
