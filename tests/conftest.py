from __future__ import annotations

import json

from mythings.engine import EngineRequest, EngineResult


class ScriptedEngine:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        return EngineResult(text=self.reply)


class SpyEngine:
    def __init__(self) -> None:
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        return EngineResult(text="")


class FakeGh:
    # Mocks only the `gh` subprocess boundary.
    def __init__(
        self,
        *,
        number: int = 5,
        title: str = "Talk on Kernel Methods",
        body: str = "Audience: ML engineers. Explain kernel methods for SVMs.",
        labels: list[str] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.number = number
        self.title = title
        self.body = body
        self.labels = labels or []

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        if argv[:2] == ["issue", "view"]:
            return json.dumps(
                {
                    "number": self.number,
                    "title": self.title,
                    "body": self.body,
                    "labels": [{"name": lbl} for lbl in self.labels],
                }
            )
        if argv[:2] == ["issue", "comment"]:
            return "https://github.com/owner/target/issues/5#issuecomment-1\n"
        raise AssertionError(f"unexpected gh call: {argv}")


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
