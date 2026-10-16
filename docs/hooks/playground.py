"""
MkDocs hook: publish what the playground loads in the browser.

After every build, ``site/playground/`` gets ``phyelds.zip`` (the package of
this commit, which Pyodide unpacks into site-packages), the examples and a
``manifest.json`` that lists them for the menu.
"""
import ast
import json
import shutil
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "phyelds"
EXAMPLES = ROOT / "docs" / "examples" / "playground"
WALKTHROUGH = ROOT / "docs" / "walkthrough"
# The menu follows this tour; examples not listed come after, by name.
TOUR = ["neighbours", "gradient", "self_healing", "channel", "leaders", "bubbles"]


def on_post_build(config: Mapping[str, Any], **_: Any) -> None:
    """Write phyelds.zip, the examples, manifest.json, and standalone walkthrough."""
    site_dir = Path(config["site_dir"])
    playground = site_dir / "playground"
    playground.mkdir(parents=True, exist_ok=True)
    _bundle_package(PACKAGE, playground / "phyelds.zip")
    examples = playground / "examples"
    shutil.rmtree(examples, ignore_errors=True)
    examples.mkdir()
    manifest = []
    for source in _tour_order(EXAMPLES.glob("*.py")):
        shutil.copy(source, examples / source.name)
        manifest.append(_describe(source))
    (playground / "manifest.json").write_text(json.dumps({"examples": manifest}, indent=2))
    _publish_walkthrough(site_dir / "walkthrough")


def _publish_walkthrough(target: Path) -> None:
    """Serve the standalone walkthrough page in place of its Markdown placeholder.

    Its stylesheet and modules sit next to it in docs/walkthrough, so MkDocs
    publishes them itself, as it does every file of the docs that is not a page.
    """
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(WALKTHROUGH / "app.html", target / "index.html")


def _bundle_package(package: Path, archive: Path) -> None:
    """Zip ``package`` with its sources only, rooted at the package name."""
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
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
