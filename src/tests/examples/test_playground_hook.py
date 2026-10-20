"""Keeps the MkDocs hook that publishes phyelds and the examples for the playground."""
import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

DOCS = Path(__file__).resolve().parents[3] / "docs"


def _load_hook():
    spec = importlib.util.spec_from_file_location("playground_hook", DOCS / "hooks" / "playground.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def _linked_navigation(*sources: str) -> SimpleNamespace:
    """A navigation of pages linked to the previous and the next one, as MkDocs links them."""
    pages = [SimpleNamespace(file=SimpleNamespace(src_uri=source), previous_page=None, next_page=None)
             for source in sources]
    for before, after in zip(pages, pages[1:]):
        before.next_page, after.previous_page = after, before
    return SimpleNamespace(pages=pages)


def test_on_nav_leaves_the_full_screen_pages_out_of_previous_and_next():
    nav = _linked_navigation("tutorial.md", "playground/index.md", "walkthrough/index.md", "concepts/state.md")
    tutorial, _, _, state = nav.pages

    hook.on_nav(nav, config={}, files=None)

    assert tutorial.next_page is state
    assert state.previous_page is tutorial


def test_on_post_build_publishes_phyelds_as_an_importable_archive(tmp_path):
    hook.on_post_build({"site_dir": str(tmp_path)})

    with zipfile.ZipFile(tmp_path / "playground" / "phyelds.zip") as archive:
        names = archive.namelist()
    assert "phyelds/__init__.py" in names
    assert "phyelds/calculus/__init__.py" in names
    assert "phyelds/simulator/__init__.py" in names
    assert not [name for name in names if "__pycache__" in name]


def test_on_post_build_publishes_the_examples_group_by_group(tmp_path):
    hook.on_post_build({"site_dir": str(tmp_path)})

    playground = tmp_path / "playground"
    examples = json.loads((playground / "manifest.json").read_text())["examples"]
    assert [(example["group"], example["name"]) for example in examples] == [
        (group, name) for group, names in hook.GROUPS.items() for name in names
    ]
    for example in examples:
        assert (playground / "examples" / f"{example['name']}.py").exists()


def test_on_post_build_describes_an_example_by_its_docstring_and_the_names_it_imports(tmp_path):
    hook.on_post_build({"site_dir": str(tmp_path)})

    examples = json.loads((tmp_path / "playground" / "manifest.json").read_text())["examples"]
    gradient = next(example for example in examples if example["name"] == "gradient")
    assert gradient["title"] == "Gradient"
    assert gradient["summary"].startswith("every device estimates its distance")
    assert gradient["uses"] == ["aggregate", "sense", "neighbors_distances", "distance_to"]


def test_groups_hold_every_example_once():
    grouped = [name for names in hook.GROUPS.values() for name in names]

    assert sorted(grouped) == sorted(path.stem for path in hook.EXAMPLES.glob("*.py"))


@pytest.mark.parametrize("page, title", [
    ("walkthrough", "Phyelds 3D Field Explorer"),
    ("playground", "Phyelds Playground"),
])
def test_on_post_build_publishes_a_full_screen_page_in_place_of_its_placeholder(tmp_path, page, title):
    hook.on_post_build({"site_dir": str(tmp_path)})

    index = tmp_path / page / "index.html"
    assert f"<title>{title}</title>" in index.read_text()
