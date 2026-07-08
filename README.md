# my-presentation

[![CI](https://github.com/MyThingsLab/my-presentation/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-presentation/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MyThingsLab/my-presentation/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-presentation)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![MIT](https://img.shields.io/badge/license-MIT-green)

A [MyThingsLab](../mythings-core) `My[X]` tool: given a talk-request issue
(topic, audience, target length), drafts a slide-by-slide outline with speaker
notes, then hands that structure to **MyTypster** to render an actual slide deck
(a Typst slide package via a `templates/presentation.typ` anchor) and compile it
to PDF.

MyPresentation owns the *narrative* — what to say and how to structure a talk;
MyTypster owns the *rendering*. The two are coupled only through the outline
MyPresentation produces, so the deck's look can change without touching the
slide logic.

## Usage

```bash
# Draft an outline + deck for one talk issue and open the compiled-deck PR.
mypresentation draft --issue 7 --repo MyThingsLab/talks --engine claude-cli

# Cap the deck length and dry-run against the noop engine (zero tokens):
mypresentation draft --issue 7 --target-slides 12 --engine noop --no-pr
```

Each invocation makes **exactly one** Engine call — the outline. Against the
default `--engine noop` (zero tokens), the outline degrades to the issue's own
title as a single slide rather than fabricating content. Rendering and the PDF
compile gate are deterministic and delegated to MyTypster.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../mythings-core -e ".[dev]"
pytest
```

See [`CLAUDE.md`](CLAUDE.md) for the tool's seams and [`HARNESS.md`](HARNESS.md)
for the inherited build rules.

## License

MIT — see [`LICENSE`](LICENSE).
