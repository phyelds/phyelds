"""Exporter module for saving simulation metrics to CSV during simulation."""

import os
import itertools
from pathlib import Path
from dataclasses import dataclass, replace
import pandas as pd
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
    simulator: Simulator, time_delta: float, config: ExporterConfig, **kwargs
):
    """Exporter module for saving simulation metrics to CSV."""
    file_path = f'{config.output_directory}{config.experiment_name}.csv'
    if not os.path.exists(file_path) or config.initial:
        Path(config.output_directory).mkdir(parents=True, exist_ok=True)
        df = init_dataframe(config, file_path)
    else:
        df = pd.read_csv(file_path)
    new_data = {}
    nodes = simulator.environment.nodes.values()
    for metric in config.metrics:
        nodes_data = [node.data['outputs'][metric] for node in nodes]
        for aggregator in config.aggregators:
            column = f'{metric}_{aggregator}'
            new_data[column] = aggregate_values(nodes_data, config.precision, aggregator)
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_csv(file_path, mode='w', index=False)
    config = replace(config, initial=False)
    simulator.schedule_event(
        time_delta, csv_exporter, simulator, time_delta, config, **kwargs
    )


def aggregate_values(values: list[float], precision, aggregator: str):
    """Aggregates a list of values using the given method and rounds to the specified precision."""
    if aggregator == "mean":
        value = sum(values) / len(values)
    elif aggregator == "std":
        mean = sum(values) / len(values)
        value = sum((v - mean) ** 2 for v in values) / len(values)
    elif aggregator == "min":
        value = min(values)
    elif aggregator == "max":
        value = max(values)
    else:
        raise ValueError(f"Invalid aggregator: {aggregator}")
    return round(value, precision)


def init_dataframe(config, file_path):
    """Initializes an empty DataFrame with appropriate columns based on config."""
    columns = list(f'{s}_{a}' for s, a in itertools.product(config.metrics, config.aggregators))
    try:
        os.remove(file_path)
    except OSError:
        pass
    return pd.DataFrame(columns=columns).astype('float64')
