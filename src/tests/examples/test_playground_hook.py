"""Keeps the MkDocs hook that publishes phyelds and the examples for the playground."""
import importlib.util
import json
import zipfile
from pathlib import Path

DOCS = Path(__file__).resolve().parents[3] / "docs"


def _load_hook():
    spec = importlib.util.spec_from_file_location("playground_hook", DOCS / "hooks" / "playground.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def test_on_post_build_publishes_phyelds_as_an_importable_archive(tmp_path):
    hook.on_post_build({"site_dir": str(tmp_path)})

    with zipfile.ZipFile(tmp_path / "playground" / "phyelds.zip") as archive:
        names = archive.namelist()
    assert "phyelds/__init__.py" in names
    assert "phyelds/calculus/__init__.py" in names
    assert not [name for name in names if "__pycache__" in name]


def test_on_post_build_publishes_the_examples_in_the_order_of_the_tour(tmp_path):
    hook.on_post_build({"site_dir": str(tmp_path)})

    playground = tmp_path / "playground"
    manifest = json.loads((playground / "manifest.json").read_text())
    names = [example["name"] for example in manifest["examples"]]
    assert names == ["neighbours", "gradient", "self_healing", "channel", "leaders", "bubbles"]
    assert manifest["examples"][1]["title"] == "Gradient"
    assert manifest["examples"][1]["summary"].startswith("every device estimates its distance")
    for name in names:
        assert (playground / "examples" / f"{name}.py").exists()
