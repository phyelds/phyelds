# CLAUDE.md

phyelds is a lightweight Python library for aggregate computing. The core package
lives in `src/phyelds/` (`calculus`, `data`, `libraries`, `vm`, `experimental`), its
tests in `src/tests/`. `experimental` holds studies in progress, whose API is not
settled and may change in any release; a study that settles moves to `libraries`. The simulator (`phyelds.simulator`) is a separate package in
`packages/phyelds-simulator/`, and so are the VMAS extension in
`packages/phyelds-vmas/`, the Mesa extension in `packages/phyelds-mesa/`, the
Webots extension in `packages/phyelds-webots/` and the ARGoS extension in
`packages/phyelds-argos/`; all of them share the `phyelds` namespace. The core
depends only on `wrapt`: the simulator is a development dependency, used by the
tests, the examples and the playground. The documentation site (MkDocs Material) is in `docs/`,
with runnable, tested examples in `docs/examples/`.

## Commands

```bash
poetry install                     # set up the environment (Python 3.12–3.13)
poetry run pytest                  # core and simulator tests (see testpaths)
poetry run pytest src/tests/libraries/test_gossip.py::test_name   # a single test
poetry run pylint src packages/phyelds-simulator/src packages/phyelds-simulator/tests  # lint, as in CI
poetry run flake8                  # style, max line length 120, as in CI
PYTHONPATH="packages/phyelds-vmas/src" poetry run pytest packages/phyelds-vmas/tests
poetry run pip install "mesa[network]==3.5.1"   # once, for the Mesa extension
PYTHONPATH="packages/phyelds-mesa/src" poetry run pytest packages/phyelds-mesa/tests
PYTHONPATH="packages/phyelds-webots/src" poetry run pytest packages/phyelds-webots/tests  # runs Webots if on the PATH
PYTHONPATH="packages/phyelds-argos/src" poetry run pytest packages/phyelds-argos/tests    # needs ARGoS3 and CMake
poetry install --with docs         # documentation dependencies
poetry run mkdocs build --strict   # build the docs, as in CI (mkdocs serve to preview)
poetry run python docs/examples/gradient.py   # regenerate the gifs in docs/assets
poetry run python docs/examples/animations.py # and those of the library pages
npm install && node docs/examples/hero.mjs     # record the gifs of the home page (Chrome, ffmpeg, gifsicle)
```

A change is done only when `pytest`, `pylint` and `flake8` all pass: CI and the
pre-commit hooks run exactly these. When a change touches the public API, also
update the docs and check `mkdocs build --strict`; documentation examples are code,
and are tested in `src/tests/examples/`. A page with `draft: true` in its front matter is
a draft (`docs/hooks/drafts.py`): `mkdocs serve` shows it, the published site leaves it
out, with the lines of other pages that link to it, so write such links on lines of
their own.

## Workflow: test-driven development

Every feature and every bug fix follows red → green → refactor. Do not write
production code that no failing test asks for.

1. **Understand.** First check the open issues (`gh issue list`) for one the
   request addresses, and say which; its text may add requirements. Restate the
   requested behaviour as a short list of observable cases (normal case, edge
   cases, error cases). If a requirement is ambiguous, ask before writing code.
2. **Red.** Write *one* test for the next case and run it. It must fail, and fail
   for the expected reason (an assertion or a missing name, not a typo or an
   import error elsewhere). Do not write the implementation in the same step.
3. **Green.** Write the minimum code that makes that test pass. Run the whole
   suite, not only the new test.
4. **Refactor.** With the suite green, remove duplication and improve names and
   structure, in both production and test code. Run the suite after each change.
5. **Commit** (see below), then repeat from step 2 for the next case.

Rules:

- Never change or delete an existing test just to make it pass. If a test is
  wrong, say so, explain why, and fix it in its own commit.
- Never skip, `xfail` or weaken an assertion to get to green.
- For a bug, first write a test that reproduces it; the fix comes after.
- Test behaviour through the public API, not implementation details, so the
  refactor step stays free.
- Tests mirror the source tree: `src/phyelds/libraries/gossip.py` →
  `src/tests/libraries/test_gossip.py`. Reuse the helpers already there
  (e.g. `tests/libraries/simulator_utils.py`) instead of building new fixtures.
- Name tests after the behaviour: `test_<unit>_<does_what>_<when>`, and lay them
  out as Arrange / Act / Assert.
- Keep tests fast and deterministic: fix random seeds, keep simulations small.

## Commits

Commit small and often: one logical change per commit, each one leaving the
suite green. A typical feature is a series of commits, e.g. a failing test plus
its implementation, then a refactor.

- Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
  `<type>(<optional scope>): <description>`. Releases are produced by
  semantic-release from these messages, so the type matters:
  - `feat:` → minor release, `fix:` → patch release,
    `feat!:` or a `BREAKING CHANGE:` footer → major release;
  - `test:`, `refactor:`, `docs:`, `style:`, `perf:`, `build:`, `ci:`, `chore:`
    do not release.
- Subject: imperative mood, lowercase, no trailing period, ≤ 72 characters.
- Body (when useful): wrap at 72 columns, explain *why* and what the previous
  behaviour was, not a line-by-line list of the diff. Follow the style of the
  existing history (`git log`).
- When the work resolves an open issue, close it: add a `Closes #<n>` footer
  to the commit that completes it (GitHub closes the issue when the commit
  reaches `master`), and `Refs #<n>` to the earlier ones. Work that ends
  without a commit (e.g. a spike answered in conversation) closes it with
  `gh issue close <n> --comment "<outcome>"`.
- Stage files explicitly (`git add <path>`), never `git add -A` / `git add .`.
- Never use `--no-verify`; if a pre-commit hook fails, fix the cause.
- Never amend or rewrite commits that are already pushed, and do not push
  unless asked.
- **No AI attribution.** Do not add `Co-Authored-By: Claude …`, "Generated
  with Claude Code", emoji or any other reference to AI tools in commit
  messages, PR titles or PR descriptions. Commits are authored by the git user
  only.

## Python style

Follow [PEP 8](https://peps.python.org/pep-0008/),
[PEP 257](https://peps.python.org/pep-0257/) and the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html);
pylint and flake8 enforce the mechanical part. Match the surrounding code first.

### Design and modularity

- One module, one responsibility. Put new code in the package it belongs to
  (`calculus` for the language primitives, `libraries` for building blocks
  written on top of them, `simulator` for simulation concerns) and keep the
  dependency direction: `libraries` and `simulator` may depend on `calculus`,
  never the other way round.
- Small, focused functions; a function longer than ~40 lines or with deep
  nesting is a signal to split it. Prefer early returns over nested `if`s.
- Prefer composition and plain functions over class hierarchies; use
  `dataclass` (or the existing pydantic models) for data carriers.
- Keep side effects at the edges and pure logic in the middle, so it is easy
  to test.
- No mutable module-level state; if it is unavoidable, make it private
  (`_name`) and expose it through functions.
- Do not duplicate: look for an existing helper before writing a new one.
- Do not add a dependency without asking.

### Code

- Type-annotate every public function, method and attribute. Use modern
  syntax: `list[int]`, `X | None`, `collections.abc` abstract types for
  parameters (`Sequence`, `Mapping`, `Callable`).
- Naming: `lower_with_under` for modules, functions and variables, `CapWords`
  for classes, `CAPS_WITH_UNDER` for constants, a leading `_` for internals.
  Descriptive names, no type in the name, no single letters outside short
  loops or maths. Do not shadow builtins (`max`, `min`, `id`, `list`, …).
- Imports: absolute (`from phyelds.calculus import aggregate`), grouped as
  standard library / third party / local, no wildcard imports.
- Never use mutable default arguments; default to `None` and build the value
  inside.
- Exceptions: raise specific built-in ones (`ValueError`, `TypeError`) or a
  custom one ending in `Error`; no bare `except:`, no broad `except Exception`
  unless re-raising; keep `try` blocks small. Do not use `assert` for runtime
  checks in library code (it is fine in tests).
- Comprehensions only when they stay simple; otherwise use a loop.
- Use f-strings, `pathlib`, context managers (`with`) for resources, and
  `logging` instead of `print` in library code.
- Executable scripts put their logic in `main()` behind
  `if __name__ == "__main__":`.

### Docstrings and comments

- Every public module, class and function has a docstring in Google style: a
  one-line summary ending with a period, then `Args:`, `Returns:` (or
  `Yields:`) and `Raises:` when relevant. Describe behaviour and contract, not
  implementation.
- Comments explain *why*, not *what*. Do not leave commented-out code, TODOs
  without context, or comments describing the change you just made.
- Update the README or docstrings when a public API changes.
