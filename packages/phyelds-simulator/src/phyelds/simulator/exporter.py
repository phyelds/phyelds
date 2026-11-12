"""Exporter module for saving simulation metrics to CSV during simulation."""

from collections.abc import Sequence
import csv
from dataclasses import dataclass, replace
import itertools
from pathlib import Path
from typing import Any

from phyelds.simulator import Simulator


__all__ = ["csv_exporter", "ExporterConfig"]


@dataclass
class ExporterConfig:
    """Configuration for CSV exporting of simulation metrics."""

    output_directory: str
    experiment_name: str
    metrics: list[str]
    aggregators: list[str]
    precision: int
    initial: bool = True


def csv_exporter(
    simulator: Simulator, time_delta: float, config: ExporterConfig, **kwargs: Any
) -> None:
    """Append aggregated node outputs to a CSV file and reschedule the next export.

    Args:
        simulator: The running simulator whose nodes hold ``outputs`` data.
        time_delta: Delay before the next export event.
        config: Export destination, metric names, aggregators and rounding precision.
        **kwargs: Extra keyword arguments forwarded when rescheduling.
    """
    file_path = Path(f"{config.output_directory}{config.experiment_name}.csv")
    write_header = config.initial or not file_path.exists()
    if write_header:
        Path(config.output_directory).mkdir(parents=True, exist_ok=True)

    nodes = simulator.environment.nodes.values()
    row: list[float] = []
    for metric in config.metrics:
        nodes_data = [node.data["outputs"][metric] for node in nodes]
        for aggregator in config.aggregators:
            row.append(float(aggregate_values(nodes_data, config.precision, aggregator)))

    mode = "w" if write_header else "a"
    with file_path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(_columns(config))
        writer.writerow(row)

    next_config = replace(config, initial=False)
    simulator.schedule_event(
        time_delta, csv_exporter, simulator, time_delta, next_config, **kwargs
    )


def aggregate_values(values: Sequence[float], precision: int, aggregator: str) -> float:
    """Aggregate ``values`` with ``aggregator`` and round to ``precision`` decimals.

    Args:
        values: Numeric metric values collected across nodes.
        precision: Number of decimal digits passed to ``round``.
        aggregator: One of ``"mean"``, ``"std"``, ``"min"``, or ``"max"``.

    Returns:
        The rounded aggregate value.

    Raises:
        ValueError: If ``aggregator`` is not one of the supported names.
    """
    if aggregator == "mean":
        value = sum(values) / len(values)
    elif aggregator == "std":
        mean = sum(values) / len(values)
        value = sum((item - mean) ** 2 for item in values) / len(values)
    elif aggregator == "min":
        value = min(values)
    elif aggregator == "max":
        value = max(values)
    else:
        raise ValueError(f"Invalid aggregator: {aggregator}")
    return round(value, precision)


def _columns(config: ExporterConfig) -> list[str]:
    """Column headers for every ``(metric, aggregator)`` pair in ``config``."""
    return [
        f"{metric}_{aggregator}"
        for metric, aggregator in itertools.product(config.metrics, config.aggregators)
    ]
