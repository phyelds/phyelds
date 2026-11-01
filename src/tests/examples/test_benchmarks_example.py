"""Keeps the charts of the benchmarks page drawable from the baseline, in both themes."""
import importlib.util
from pathlib import Path

from PIL import Image

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "benchmarks.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("benchmarks_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


benchmarks = _load_example()


def test_benchmarks_example_draws_each_chart_in_both_themes_at_the_width_of_the_docs_column(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmarks, "ASSETS", tmp_path)

    benchmarks.main()

    widths = {path.name: Image.open(path).width for path in tmp_path.glob("*.png")}
    assert set(widths) == {
        "benchmarks-scaling.png", "benchmarks-scaling-dark.png", "benchmarks-layers.png", "benchmarks-layers-dark.png"
    }
    assert set(widths.values()) == {round(benchmarks.COLUMN_WIDTH * benchmarks.DPI)}


def test_benchmarks_example_draws_the_dark_charts_on_the_background_of_the_dark_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmarks, "ASSETS", tmp_path)

    benchmarks.main()

    for name in ("benchmarks-scaling-dark.png", "benchmarks-layers-dark.png"):
        assert Image.open(tmp_path / name).convert("RGB").getpixel((0, 0)) == (0x1F, 0x1A, 0x24)
