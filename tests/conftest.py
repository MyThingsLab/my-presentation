from __future__ import annotations

import json

# Shared fakes come from mythings.testing; only the issue payload wiring and
# the mytypster CLI double stay local.
from mythings.testing import FakeGh, ScriptedEngine

__all__ = ["ScriptedEngine"]


def fake_gh(
    *,
    number: int = 5,
    title: str = "Talk on Kernel Methods",
    body: str = "Audience: ML engineers. Explain kernel methods for SVMs.",
    labels: list[str] | None = None,
) -> FakeGh:
    issue = {
        "number": number,
        "title": title,
        "body": body,
        "labels": [{"name": lbl} for lbl in (labels or [])],
    }
    return FakeGh(
        {
            ("issue", "view"): json.dumps(issue),
            ("issue", "comment"): "https://github.com/owner/target/issues/5#issuecomment-1\n",
        }
    )


class FakeTypster:
    # Mocks the `mytypster` subprocess boundary MyPresentation shells out to.
    def __init__(self, *, outcome: str = "success", pr: int | None = 9, detail: str = "ok") -> None:
        self.calls: list[list[str]] = []
        self.outcome = outcome
        self.pr = pr
        self.detail = detail

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        result = {
            "outcome": self.outcome,
            "kind": "presentation",
            "pr": self.pr if self.outcome == "success" else None,
            "detail": self.detail,
            "typ_path": "deck.typ" if self.outcome != "failure" else None,
            "pdf_path": "deck.pdf" if self.outcome == "success" else None,
        }
        return json.dumps(result)
