"""Keeps the MkDocs hook that leaves the pages marked as drafts out of the published site."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

# The hook runs inside MkDocs, installed with the docs group: the docs workflow tests it.
mkdocs_files = pytest.importorskip("mkdocs.structure.files")
File, Files, InclusionLevel = mkdocs_files.File, mkdocs_files.Files, mkdocs_files.InclusionLevel

DOCS = Path(__file__).resolve().parents[3] / "docs"


def _load_hook():
    spec = importlib.util.spec_from_file_location("drafts_hook", DOCS / "hooks" / "drafts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def _page(tmp_path: Path, name: str, text: str) -> File:
    (tmp_path / name).write_text(text, encoding="utf-8")
    return File(name, str(tmp_path), str(tmp_path / "site"), use_directory_urls=True)


def test_on_files_marks_the_pages_with_draft_in_their_front_matter_as_drafts(tmp_path):
    draft = _page(tmp_path, "draft.md", "---\ndraft: true\n---\n# Not yet\n")
    page = _page(tmp_path, "page.md", "# Published\n")
    other = _page(tmp_path, "other.md", "---\ndraft: false\n---\n# Published too\n")

    hook.on_files(Files([draft, page, other]), config={})

    assert draft.inclusion == InclusionLevel.DRAFT
    assert page.inclusion != InclusionLevel.DRAFT
    assert other.inclusion != InclusionLevel.DRAFT


def test_on_files_leaves_the_files_that_are_not_pages_alone(tmp_path):
    image = _page(tmp_path, "draft.css", "---\ndraft: true\n---\n")

    hook.on_files(Files([image]), config={})

    assert image.inclusion != InclusionLevel.DRAFT


def _published(tmp_path: Path, markdown: str, serving: bool = False) -> str:
    draft = _page(tmp_path, "draft.md", "---\ndraft: true\n---\n# Not yet\n")
    other = _page(tmp_path, "other.md", "# Published\n")
    (tmp_path / "guide").mkdir()
    page = _page(tmp_path, "guide/page.md", markdown)
    files = Files([draft, other, page])
    hook.on_startup(command="serve" if serving else "build", dirty=False)
    hook.on_files(files, config={})
    return hook.on_page_markdown(markdown, page=SimpleNamespace(file=page), config={}, files=files)


def test_on_page_markdown_leaves_out_the_lines_linking_to_a_draft_when_publishing(tmp_path):
    markdown = "Intro.\n\nSee [the draft](../draft.md#part).\nSee [the other](../other.md).\n"

    assert _published(tmp_path, markdown) == "Intro.\n\nSee [the other](../other.md).\n"


def test_on_page_markdown_keeps_the_lines_linking_to_a_draft_when_serving(tmp_path):
    markdown = "See [the draft](../draft.md).\n"

    assert _published(tmp_path, markdown, serving=True) == markdown


def _nav_page(file: File) -> SimpleNamespace:
    return SimpleNamespace(file=file, children=None, previous_page=None, next_page=None)


def _nav(tmp_path: Path) -> SimpleNamespace:
    draft = _page(tmp_path, "draft.md", "---\ndraft: true\n---\n# Not yet\n")
    first, last = _page(tmp_path, "first.md", "# First\n"), _page(tmp_path, "last.md", "# Last\n")
    hook.on_files(Files([draft, first, last]), config={})
    pages = [_nav_page(first), _nav_page(draft), _nav_page(last)]
    only_drafts = SimpleNamespace(file=None, children=[_nav_page(draft)])
    return SimpleNamespace(items=[SimpleNamespace(file=None, children=list(pages)), only_drafts], pages=pages)


def test_on_nav_leaves_the_drafts_out_of_the_navigation_when_publishing(tmp_path):
    nav = _nav(tmp_path)
    hook.on_startup(command="build", dirty=False)

    hook.on_nav(nav, config={}, files=None)

    first, last = nav.pages
    assert [page.file.src_uri for page in nav.items[0].children] == ["first.md", "last.md"]
    assert len(nav.items) == 1
    assert (first.next_page, last.previous_page) == (last, first)


def test_on_nav_keeps_the_drafts_when_serving(tmp_path):
    nav = _nav(tmp_path)
    hook.on_startup(command="serve", dirty=False)

    hook.on_nav(nav, config={}, files=None)

    assert len(nav.pages) == 3 and len(nav.items) == 2
