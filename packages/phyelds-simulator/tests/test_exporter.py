"""Tests for CSV metric exporting in the simulator."""

import csv
from pathlib import Path

import pytest

from phyelds.simulator import Simulator
from phyelds.simulator.exporter import ExporterConfig, csv_exporter


def _simulator_with_outputs(values: list[float]) -> Simulator:
    simulator = Simulator()
    for index, value in enumerate(values):
        simulator.create_node((float(index), 0.0), data={"outputs": {"distance": value}}, node_id=index)
    return simulator


def test_csv_exporter_writes_header_and_appends_aggregated_rows_across_steps(tmp_path: Path):
    simulator = _simulator_with_outputs([1, 2, 6])
    config = ExporterConfig(
        output_directory=f"{tmp_path}/metrics/",
        experiment_name="gradient",
        metrics=["distance"],
        aggregators=["mean", "min", "max", "std"],
        precision=3,
    )
    simulator.schedule_event(1.0, csv_exporter, simulator, 1.0, config)
    simulator.schedule_event(
        1.5, lambda: simulator.environment.nodes[2].data["outputs"].update(distance=3)
    )

    simulator.run(2.0)

    csv_path = tmp_path / "metrics" / "gradient.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows == [
        ["distance_mean", "distance_min", "distance_max", "distance_std"],
        ["3.0", "1.0", "6.0", "4.667"],
        ["2.0", "1.0", "3.0", "0.667"],
    ]


def test_csv_exporter_overwrites_stale_file_when_initial_is_true(tmp_path: Path):
    csv_path = tmp_path / "gradient.csv"
    csv_path.write_text("stale_header\n999\n", encoding="utf-8")
    simulator = _simulator_with_outputs([2.0, 4.0])
    config = ExporterConfig(
        output_directory=f"{tmp_path}/",
        experiment_name="gradient",
        metrics=["distance"],
        aggregators=["mean"],
        precision=2,
    )
    simulator.schedule_event(1.0, csv_exporter, simulator, 1.0, config)

    simulator.run(1.0)

    assert csv_path.read_text(encoding="utf-8").splitlines() == ["distance_mean", "3.0"]


def test_csv_exporter_rejects_unknown_aggregator(tmp_path: Path):
    simulator = _simulator_with_outputs([1.0, 2.0])
    config = ExporterConfig(
        output_directory=f"{tmp_path}/",
        experiment_name="gradient",
        metrics=["distance"],
        aggregators=["median"],
        precision=2,
    )
    simulator.schedule_event(1.0, csv_exporter, simulator, 1.0, config)

    with pytest.raises(ValueError, match="Invalid aggregator"):
        simulator.run(1.0)
