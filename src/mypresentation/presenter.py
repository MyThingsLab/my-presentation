from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from myguard import Guard
from mythings.engine import Engine, EngineRequest, NoopEngine
from mythings.github import Runner, _gh
from mythings.isolation import in_github_actions
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, Policy

LABEL = "my-presentation"

_SYSTEM = (
    "You draft a slide-by-slide talk outline with speaker notes for the given "
    "topic, audience, and target length. Reply with a single JSON object "
    '{"slides": [{"title": str, "bullets": [str], "speaker_notes": str}], '
    '"est_duration_min": int} and nothing else.'
)

_SLIDE_COUNT_RE = re.compile(r"(\d+)\s*slides?\b", re.IGNORECASE)


@dataclass(frozen=True)
class Slide:
    title: str
    bullets: list[str] = field(default_factory=list)
    speaker_notes: str = ""


@dataclass(frozen=True)
class Result:
    outcome: str  # success | compile_failed | failure
    slide_count: int | None
    pr: int | None
    detail: str


@dataclass(frozen=True)
class _Issue:
    number: int
    title: str
    body: str
    labels: list[str]


class Presenter:
    def __init__(
        self,
        *,
        repo: str | None = None,
        repo_root: str | Path = ".",
        templates_repo: str | Path = "../typst-templates",
        ledger: Ledger,
        base: str = "main",
        engine: Engine | None = None,
        policy: Policy | None = None,
        runner: Runner = _gh,
        mytypster_runner: Runner | None = None,
    ) -> None:
        self.repo = repo
        self.repo_root = Path(repo_root)
        self.templates_repo = Path(templates_repo)
        self.ledger = ledger
        self.base = base
        self.engine: Engine = engine or NoopEngine()
        self.policy: Policy = policy or Guard()
        self.runner = runner
        self._mytypster_run = mytypster_runner or _default_mytypster_runner

    # ---- draft ------------------------------------------------------------

    def draft(self, issue: int, *, target_slides: int | None = None, no_pr: bool = False) -> Result:
        try:
            topic = self._fetch_issue(issue)
        except Exception as err:  # gh.GitHubError, but keep this boundary generic
            return self._fail(None, f"could not read issue #{issue}: {err}")

        resolved_target = target_slides if target_slides is not None else _parse_target(topic.body)

        reply = self.engine.run(
            EngineRequest(
                system=_SYSTEM,
                prompt=self._prompt(topic, resolved_target),
                context={"issue": issue, "target_slides": resolved_target},
            )
        )
        slides = self._parse_reply(reply.text, topic)

        if resolved_target is not None and len(slides) > resolved_target:
            slides = slides[:resolved_target]

        self._comment(issue, _render_outline(slides))

        typster_result = self._call_typster(issue, slides, no_pr=no_pr)

        detail = f"deck for {topic.title} ({len(slides)} slides)"
        outcome = typster_result.get("outcome", "failure")
        pr = typster_result.get("pr")
        self._record(outcome, len(slides), pr, detail, typster_result)
        return Result(outcome, len(slides), pr, detail)

    # ---- deterministic pre-work ---------------------------------------------

    def _fetch_issue(self, number: int) -> _Issue:
        argv = ["issue", "view", str(number), "--json", "number,title,body,labels"]
        if self.repo:
            argv += ["--repo", self.repo]
        obj = json.loads(self.runner(argv))
        labels = [lbl["name"] if isinstance(lbl, dict) else lbl for lbl in obj.get("labels", [])]
        return _Issue(
            number=obj["number"], title=obj["title"], body=obj.get("body") or "", labels=labels
        )

    def _prompt(self, topic: _Issue, target_slides: int | None) -> str:
        lines = [f"Issue #{topic.number}: {topic.title}", f"\nRequest body:\n{topic.body.strip()}"]
        if target_slides is not None:
            lines.append(f"\nTarget slide count: {target_slides}")
        return "\n".join(lines)

    # ---- engine reply parsing -----------------------------------------------

    def _parse_reply(self, text: str, topic: _Issue) -> list[Slide]:
        obj = _parse_json_object(text)
        if obj is None:
            return [_stub_slide(topic)]

        raw_slides = obj.get("slides")
        if not isinstance(raw_slides, list) or not raw_slides:
            return [_stub_slide(topic)]

        slides = []
        for item in raw_slides:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))
            bullets = [str(b) for b in item.get("bullets") or []]
            notes = str(item.get("speaker_notes", ""))
            slides.append(Slide(title=title, bullets=bullets, speaker_notes=notes))
        return slides or [_stub_slide(topic)]

    # ---- MyTypster hand-off --------------------------------------------------

    def _call_typster(self, issue: int, slides: list[Slide], *, no_pr: bool) -> dict:
        payload = {
            "slides": [
                {"title": s.title, "bullets": s.bullets, "speaker_notes": s.speaker_notes}
                for s in slides
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(payload, fh)
            slides_path = fh.name

        argv = [
            "draft",
            "--issue",
            str(issue),
            "--kind",
            "presentation",
            "--repo-root",
            str(self.repo_root),
            "--templates-repo",
            str(self.templates_repo),
            "--base",
            self.base,
            "--from-json",
            slides_path,
            "--json",
        ]
        if self.repo:
            argv += ["--repo", self.repo]
        if no_pr:
            argv.append("--no-pr")

        action = Action(kind="bash", payload={"command": "mytypster draft"})
        if self.policy.evaluate(action).under(unattended=in_github_actions()) is not Decision.ALLOW:
            return {"outcome": "failure", "detail": "policy blocked mytypster hand-off"}

        raw = self._mytypster_run(argv)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {"outcome": "failure", "detail": "mytypster returned an unparsable result"}

    # ---- github helpers --------------------------------------------------

    def _comment(self, issue: int, body: str) -> str | None:
        if self.repo is None:
            return None
        argv = ["issue", "comment", str(issue), "--repo", self.repo, "--body", body]
        action = Action(kind="bash", payload={"command": f"gh issue comment {issue}"})
        if self.policy.evaluate(action).under(unattended=in_github_actions()) is not Decision.ALLOW:
            return None
        return self.runner(argv).strip() or None

    # ---- ledger / results ---------------------------------------------------

    def _record(
        self, outcome: str, slide_count: int, pr: int | None, detail: str, typster_result: dict
    ) -> None:
        data = {
            "slide_count": slide_count,
            "typ_path": typster_result.get("typ_path"),
        }
        if outcome == "success":
            data["pdf_path"] = typster_result.get("pdf_path")
            data["pr_url"] = pr
        self.ledger.record(
            tool="mypresentation", kind="presentation", outcome=outcome, detail=detail, **data
        )

    def _fail(self, slide_count: int | None, detail: str) -> Result:
        self.ledger.record(
            tool="mypresentation", kind="presentation", outcome="failure", detail=detail
        )
        return Result("failure", slide_count, None, detail)


def _parse_target(body: str) -> int | None:
    match = _SLIDE_COUNT_RE.search(body)
    return int(match.group(1)) if match else None


def _stub_slide(topic: _Issue) -> Slide:
    bullets = [line.strip() for line in topic.body.splitlines() if line.strip()]
    return Slide(title=topic.title, bullets=bullets, speaker_notes="")


def _render_outline(slides: list[Slide]) -> str:
    blocks = []
    for slide in slides:
        lines = [f"### {slide.title}"]
        lines += [f"- {b}" for b in slide.bullets]
        if slide.speaker_notes:
            lines.append(f"\n_Speaker notes: {slide.speaker_notes}_")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _default_mytypster_runner(argv: list[str]) -> str:
    proc = subprocess.run(["mytypster", *argv], capture_output=True, text=True)
    return proc.stdout


def _parse_json_object(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(lines).strip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None
