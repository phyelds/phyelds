"""
MkDocs hook: publish what the playground loads in the browser.

After every build, ``site/playground/`` gets ``phyelds.zip`` (the package of
this commit and its simulator, which Pyodide unpacks into site-packages), the examples and a
``manifest.json`` that lists them for the menu. The full-screen pages, the
walkthrough and the playground, replace their Markdown placeholders, and stay
out of the previous and next links.
"""
import ast
import json
import shutil
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
# The core and the simulator, both under the phyelds namespace.
PACKAGES = (ROOT / "src" / "phyelds", ROOT / "packages" / "phyelds-simulator" / "src" / "phyelds")
EXAMPLES = DOCS / "examples" / "playground"
# Pages that open full screen: docs/<name>/app.html, published in place of docs/<name>/index.md.
FULL_SCREEN = ("walkthrough", "playground")
# The menu follows this tour; examples not listed come after, by name.
TOUR = ["neighbours", "gradient", "channel", "leaders", "bubbles"]


def on_nav(nav: Any, **_: Any) -> Any:
    """Link every page to its neighbors in the nav, skipping the full-screen pages.

    They open without the footer of the other pages: a reader who reached one
    with "next" would find no "previous" to come back.
    """
    placeholders = {f"{name}/index.md" for name in FULL_SCREEN}
    pages = [page for page in nav.pages if page.file.src_uri not in placeholders]
    bookended = [None, *pages, None]
    for before, page, after in zip(bookended, bookended[1:], bookended[2:]):
        page.previous_page, page.next_page = before, after
    return nav


def on_post_build(config: Mapping[str, Any], **_: Any) -> None:
    """Write phyelds.zip, the examples and manifest.json, and the full-screen pages."""
    site_dir = Path(config["site_dir"])
    playground = site_dir / "playground"
    playground.mkdir(parents=True, exist_ok=True)
    _bundle_packages(PACKAGES, playground / "phyelds.zip")
    examples = playground / "examples"
    shutil.rmtree(examples, ignore_errors=True)
    examples.mkdir()
    manifest = []
    for source in _tour_order(EXAMPLES.glob("*.py")):
        shutil.copy(source, examples / source.name)
        manifest.append(_describe(source))
    (playground / "manifest.json").write_text(json.dumps({"examples": manifest}, indent=2))
    for name in FULL_SCREEN:
        _publish_full_screen(DOCS / name / "app.html", site_dir / name)


def _publish_full_screen(page: Path, target: Path) -> None:
    """Serve ``page`` in place of the Markdown placeholder published in ``target``.

    Its stylesheets and modules sit next to it, so MkDocs publishes them itself,
    as it does every file of the docs that is not a page.
    """
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(page, target / "index.html")


def _bundle_packages(packages: Iterable[Path], archive: Path) -> None:
    """Zip ``packages`` with their sources only, each rooted at the package name."""
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for package in packages:
            for path in sorted(package.rglob("*.py")):
                if "__pycache__" not in path.parts:
                    bundle.write(path, path.relative_to(package.parent).as_posix())


def _tour_order(sources: Iterable[Path]) -> list[Path]:
    """The examples in the order of TOUR, then the others by name."""
    def position(source: Path) -> tuple[int, str]:
        rank = TOUR.index(source.stem) if source.stem in TOUR else len(TOUR)
        return rank, source.stem

    return sorted(sources, key=position)


def _describe(source: Path) -> dict[str, str]:
    """Name, title and summary of an example, from the first line of its docstring."""
    docstring = ast.get_docstring(ast.parse(source.read_text())) or source.stem
    title, _, summary = docstring.splitlines()[0].partition(":")
    return {"name": source.stem, "title": title.strip(), "summary": summary.strip()}
