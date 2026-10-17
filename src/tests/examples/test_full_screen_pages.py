"""Keeps the full-screen pages of the docs and their modules pointing at files and names that exist."""
import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[3] / "docs"
PAGES = ["walkthrough", "playground"]
# src and href of the page that stay on the site: not absolute URLs, not anchors.
LOCAL_REFERENCE = re.compile(r'(?:src|href)="(?![a-z]+:|#)([^"#?]+)')
NAMED_IMPORT = re.compile(r'import \{([^}]*)\} from "(\.{1,2}/[^"]+)"')
EXPORT = re.compile(r"export (?:const|let|function|class) (\w+)")


@pytest.mark.parametrize("page", PAGES)
def test_full_screen_page_references_only_files_of_the_docs(page):
    folder = DOCS / page

    references = LOCAL_REFERENCE.findall((folder / "app.html").read_text())

    assert references
    assert [reference for reference in references if not (folder / reference).exists()] == []


@pytest.mark.parametrize("page", PAGES)
def test_full_screen_page_modules_import_names_their_modules_export(page):
    imports = [
        (module.parent / target, name.strip())
        for module in (DOCS / page).glob("*.js")
        for names, target in NAMED_IMPORT.findall(module.read_text())
        for name in names.split(",")
        if name.strip()
    ]

    missing = [
        f"{name} from {target.relative_to(DOCS)}"
        for target, name in imports
        if not target.exists() or name not in EXPORT.findall(target.read_text())
    ]

    assert imports
    assert missing == []
