"""Keeps the conceptual figures of the docs drawable in both themes."""
import importlib.util
from pathlib import Path

from PIL import Image

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "diagrams.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("diagrams_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diagrams = _load_example()


def test_diagrams_example_draws_the_dark_figure_on_the_background_of_the_dark_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "ASSETS", tmp_path)

    diagrams.draw_local_vs_global(diagrams.DARK)

    figure = Image.open(tmp_path / "local-vs-global-dark.png").convert("RGB")
    assert figure.getpixel((0, 0)) == (0x1F, 0x1A, 0x24)


def test_diagrams_example_draws_every_figure_at_the_width_of_the_docs_column(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "ASSETS", tmp_path)

    diagrams.main()

    widths = {path.name: Image.open(path).width for path in tmp_path.glob("*.png")}
    assert len(widths) == 22
    assert set(widths.values()) == {round(diagrams.COLUMN_WIDTH * diagrams.DPI)}
