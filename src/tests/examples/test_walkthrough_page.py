"""Keeps the standalone walkthrough page and its modules pointing at files that exist."""
import re
from pathlib import Path

WALKTHROUGH = Path(__file__).resolve().parents[3] / "docs" / "walkthrough"
# src and href of the page that stay on the site: not absolute URLs, not anchors.
LOCAL_REFERENCE = re.compile(r'(?:src|href)="(?![a-z]+:|#)([^"#?]+)')
MODULE_IMPORT = re.compile(r'from "(\.{1,2}/[^"]+)"')


def _missing(references: list[str]) -> list[str]:
    return [reference for reference in references if not (WALKTHROUGH / reference).exists()]


def test_walkthrough_page_references_only_files_of_the_docs():
    page = (WALKTHROUGH / "app.html").read_text()

    missing = _missing(LOCAL_REFERENCE.findall(page))

    assert not missing


def test_walkthrough_modules_import_only_modules_of_the_walkthrough():
    imports = [target for module in WALKTHROUGH.glob("*.js") for target in MODULE_IMPORT.findall(module.read_text())]

    missing = _missing(imports)

    assert imports
    assert not missing
