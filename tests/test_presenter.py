from __future__ import annotations

import json
from pathlib import Path

from mythings.ledger import Ledger

from conftest import FakeGh, FakeTypster, ScriptedEngine, SpyEngine
from mypresentation.presenter import Presenter

_OUTLINE_REPLY = json.dumps(
    {
        "slides": [
            {"title": "Intro", "bullets": ["what is a kernel"], "speaker_notes": "warm up"},
            {"title": "The trick", "bullets": ["mapping to feature space"], "speaker_notes": ""},
            {"title": "Wrap-up", "bullets": ["recap"], "speaker_notes": ""},
        ],
        "est_duration_min": 15,
    }
)


def _presenter(tmp_path: Path, gh: FakeGh, typster: FakeTypster, **kw) -> tuple[Presenter, Ledger]:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    p = Presenter(repo="owner/target", ledger=ledger, runner=gh, mytypster_runner=typster, **kw)
    return p, ledger


def test_draft_happy_path_comments_outline_and_opens_pr(tmp_path: Path) -> None:
    gh = FakeGh()
    typster = FakeTypster(outcome="success", pr=9)
    p, ledger = _presenter(tmp_path, gh, typster, engine=ScriptedEngine(_OUTLINE_REPLY))

    result = p.draft(issue=5)

    assert result.outcome == "success"
    assert result.pr == 9
    assert result.slide_count == 3

    comment_call = next(c for c in gh.calls if c[:2] == ["issue", "comment"])
    body = comment_call[-1]
    assert "### Intro" in body
    assert "what is a kernel" in body
    assert "_Speaker notes: warm up_" in body
    assert "### Wrap-up" in body

    typster_call = typster.calls[0]
    assert "--kind" in typster_call and "presentation" in typster_call
    assert "--from-json" in typster_call

    entry = list(ledger)[0]
    assert entry.kind == "presentation"
    assert entry.outcome == "success"
    assert entry.data["pr_url"] == 9


def test_draft_truncates_to_target_slides_deterministically(tmp_path: Path) -> None:
    gh = FakeGh()
    typster = FakeTypster()
    p, ledger = _presenter(tmp_path, gh, typster, engine=ScriptedEngine(_OUTLINE_REPLY))

    result = p.draft(issue=5, target_slides=2)

    assert result.slide_count == 2
    comment_call = next(c for c in gh.calls if c[:2] == ["issue", "comment"])
    assert "### Wrap-up" not in comment_call[-1]  # dropped, over the cap
    assert "### Intro" in comment_call[-1]
    assert "### The trick" in comment_call[-1]

    slides_path = Path(typster.calls[0][typster.calls[0].index("--from-json") + 1])
    payload = json.loads(slides_path.read_text())
    assert len(payload["slides"]) == 2


def test_draft_target_slides_parsed_from_issue_body(tmp_path: Path) -> None:
    gh = FakeGh(body="Please keep this to 1 slides total.")
    typster = FakeTypster()
    p, ledger = _presenter(tmp_path, gh, typster, engine=ScriptedEngine(_OUTLINE_REPLY))

    result = p.draft(issue=5)

    assert result.slide_count == 1


def test_draft_compile_failure_still_comments_outline_but_no_pr(tmp_path: Path) -> None:
    gh = FakeGh()
    typster = FakeTypster(outcome="compile_failed", pr=None)
    p, ledger = _presenter(tmp_path, gh, typster, engine=ScriptedEngine(_OUTLINE_REPLY))

    result = p.draft(issue=5)

    assert result.outcome == "compile_failed"
    assert result.pr is None
    assert any(c[:2] == ["issue", "comment"] for c in gh.calls)  # narrative review still posts
    assert list(ledger)[0].outcome == "compile_failed"
    assert "pdf_path" not in list(ledger)[0].data


def test_draft_no_pr_passed_through_to_typster(tmp_path: Path) -> None:
    gh = FakeGh()
    typster = FakeTypster()
    p, _ = _presenter(tmp_path, gh, typster, engine=ScriptedEngine(_OUTLINE_REPLY))

    p.draft(issue=5, no_pr=True)

    assert "--no-pr" in typster.calls[0]


def test_draft_against_noop_engine_degrades_to_one_stub_slide(tmp_path: Path) -> None:
    gh = FakeGh(title="Quick talk on RayTracer", body="Line one.\nLine two.")
    typster = FakeTypster()
    p, ledger = _presenter(tmp_path, gh, typster)  # default NoopEngine

    result = p.draft(issue=5)

    assert result.slide_count == 1
    comment_call = next(c for c in gh.calls if c[:2] == ["issue", "comment"])
    assert "### Quick talk on RayTracer" in comment_call[-1]
    assert "Line one." in comment_call[-1]


def test_draft_engine_never_called_when_issue_fetch_fails(tmp_path: Path) -> None:
    class BrokenGh:
        def __call__(self, argv: list[str]) -> str:
            raise RuntimeError("gh issue view failed (404): not found")

    typster = FakeTypster()
    spy = SpyEngine()
    ledger = Ledger(tmp_path / "ledger.jsonl")
    p = Presenter(
        repo="owner/target",
        ledger=ledger,
        runner=BrokenGh(),
        mytypster_runner=typster,
        engine=spy,
    )

    result = p.draft(issue=5)

    assert result.outcome == "failure"
    assert spy.calls == []
    assert typster.calls == []
    assert list(ledger)[0].outcome == "failure"
