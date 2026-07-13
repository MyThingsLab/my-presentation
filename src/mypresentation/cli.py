from __future__ import annotations

import argparse
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.ledger import Ledger

from mypresentation.presenter import Presenter, Result


def build_engine(name: str, *, model: str | None = None) -> Engine:
    if name == "claude-cli":
        return ClaudeCLIEngine(model=model)
    return NoopEngine()


def _render(result: Result) -> str:
    line = f"{result.outcome}: {result.detail}"
    if result.pr is not None:
        line += f" — PR #{result.pr}"
    return line


def _make(args: argparse.Namespace) -> Presenter:
    return Presenter(
        repo=args.repo,
        repo_root=args.repo_root,
        templates_repo=args.templates_repo,
        ledger=Ledger(args.ledger),
        base=args.base,
        engine=build_engine(args.engine, model=args.engine_model),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mypresentation",
        description="Draft a slide outline from a talk issue and hand it to MyTypster for a deck.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    draft = sub.add_parser("draft", help="draft an outline and deck for one issue")
    draft.add_argument("--issue", type=int, required=True, help="the talk-request issue")
    draft.add_argument("--repo", help="GitHub slug owner/name where the issue and PR live")
    draft.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="local checkout passed to mytypster"
    )
    draft.add_argument(
        "--templates-repo",
        type=Path,
        default=Path("../typst-templates"),
        help="local typst-templates checkout, passed to mytypster",
    )
    draft.add_argument("--base", default="main", help="base branch for the PR")
    draft.add_argument("--ledger", type=Path, default=Path(".mythings/ledger.jsonl"))
    draft.add_argument(
        "--slides", type=int, help="target slide count (default: inferred from body)"
    )
    draft.add_argument(
        "--images",
        help="comma-separated repo-relative image paths the outline may reference "
        "(default: inferred from an 'images:' line in the body)",
    )
    draft.add_argument("--no-pr", action="store_true", help="skip opening the compiled-deck PR")
    draft.add_argument(
        "--engine",
        choices=("noop", "claude-cli"),
        default="noop",
        help="Engine backend for the outline (default: noop — one stub slide)",
    )
    draft.add_argument("--engine-model", help="model for --engine claude-cli")

    args = parser.parse_args(argv)
    presenter = _make(args)

    images = [p.strip() for p in args.images.split(",") if p.strip()] if args.images else None
    result = presenter.draft(
        args.issue, target_slides=args.slides, images=images, no_pr=args.no_pr
    )

    print(_render(result))
    return 1 if result.outcome in {"failure", "compile_failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
