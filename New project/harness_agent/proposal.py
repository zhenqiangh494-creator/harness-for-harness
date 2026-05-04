from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any


class ProposalParseError(ValueError):
    """Raised when the model did not return a valid proposal object."""


@dataclass(frozen=True)
class FileEdit:
    path: str
    content: str | None = None
    delete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IterationProposal:
    analysis: str
    architecture: str
    files: list[FileEdit]
    commands: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis,
            "architecture": self.architecture,
            "files": [item.to_dict() for item in self.files],
            "commands": self.commands,
            "notes": self.notes,
        }


def extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return _load_object(fenced.group(1).strip())

    start = text.find("{")
    if start == -1:
        raise ProposalParseError("No JSON object found in model response.")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return _load_object(text[start : index + 1])

    raise ProposalParseError("JSON object was not balanced.")


def parse_proposal(text: str) -> IterationProposal:
    data = extract_json_object(text)

    raw_files = data.get("files")
    if not isinstance(raw_files, list):
        raise ProposalParseError("Proposal must include a 'files' list.")

    files: list[FileEdit] = []
    for item in raw_files:
        if not isinstance(item, dict):
            raise ProposalParseError("Each file edit must be an object.")
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ProposalParseError("Each file edit requires a non-empty 'path'.")
        delete = bool(item.get("delete", item.get("action") == "delete"))
        content = item.get("content")
        if delete:
            files.append(FileEdit(path=path, delete=True))
            continue
        if not isinstance(content, str):
            raise ProposalParseError(f"File edit for {path!r} requires string 'content'.")
        files.append(FileEdit(path=path, content=content, delete=False))

    delete_files = data.get("delete_files", [])
    if delete_files:
        if not isinstance(delete_files, list):
            raise ProposalParseError("'delete_files' must be a list when present.")
        for path in delete_files:
            if not isinstance(path, str) or not path.strip():
                raise ProposalParseError("'delete_files' entries must be non-empty strings.")
            files.append(FileEdit(path=path, delete=True))

    raw_commands = data.get("commands", [])
    if raw_commands is None:
        raw_commands = []
    if not isinstance(raw_commands, list) or not all(isinstance(item, str) for item in raw_commands):
        raise ProposalParseError("'commands' must be a list of strings.")

    return IterationProposal(
        analysis=str(data.get("analysis", "")),
        architecture=str(data.get("architecture", "")),
        files=files,
        commands=list(raw_commands),
        notes=str(data.get("notes", "")),
    )


def _load_object(candidate: str) -> dict[str, Any]:
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ProposalParseError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProposalParseError("Top-level JSON value must be an object.")
    return data
