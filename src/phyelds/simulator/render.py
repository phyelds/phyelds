"""
Render the nodes in the simulator's environment.
"""
import sys
from pathlib import Path

from IPython.display import display, clear_output
from matplotlib import pyplot as plt
from matplotlib.animation import AbstractMovieWriter, FFMpegWriter, PillowWriter

from phyelds.simulator import Simulator, Monitor
from phyelds.simulator.effects import RenderConfig, RenderMode


def make_writer(config: RenderConfig) -> AbstractMovieWriter:
    """
    Create the movie writer matching the extension of ``config.save_as``.

    Args:
        config: the render configuration.

    Returns:
        A ``PillowWriter`` for ``.gif`` files, an ``FFMpegWriter`` otherwise.
    """
    fps = 1 / config.dt if config.dt > 0 else 15
    if Path(config.save_as).suffix.lower() == ".gif":
        return PillowWriter(fps=fps)
    metadata = {"title": "Simulation", "artist": "Phyelds"}
    return FFMpegWriter(fps=fps, metadata=metadata)


def _padded_limits(values: tuple[float, ...], pad: float = 0.05) -> tuple[float, float]:
    """
    Axis limits enclosing ``values`` with a margin of ``pad`` times their range.
    When all values coincide (e.g. nodes on a line) the margin is 1, so the limits
    never collapse into a single point.
    """
    low, high = min(values), max(values)
    margin = pad * (high - low) if high > low else 1.0
    return low - margin, high + margin


class RenderMonitor(Monitor):
    """
    Render the nodes in the simulator's environment.
    """

    def __init__(self, simulator: Simulator, config: RenderConfig):
        super().__init__(simulator)
        self.config = config
        self.config.effects.sort(key=lambda e: e.z_order)
        self.last_render_time = 0
        self.fig, self.ax = plt.subplots()
        self.writer = None

    def on_start(self):
        if self.config.mode in [RenderMode.SAVE, RenderMode.SAVE_ALL]:
            self.writer = make_writer(self.config)
            self.writer.setup(self.fig, self.config.save_as, dpi=100)
        elif self.config.mode == RenderMode.SHOW:
            plt.ion()
            plt.show()

    def update(self):
        if self.simulator.current_time < self.config.skip or self._instant_in_progress():
            return
        if self.simulator.current_time - self.last_render_time >= self.config.dt:
            self._render()
            self.last_render_time = self.simulator.current_time

    def _instant_in_progress(self) -> bool:
        """True while other events are still queued for the current time."""
        queue = self.simulator.event_queue
        return bool(queue) and queue[0].time <= self.simulator.current_time

    def on_finish(self):
        if self.config.mode in [RenderMode.SAVE, RenderMode.SAVE_ALL]:
            self.writer.finish()
            if self.config.mode == RenderMode.SAVE:
                self.fig.savefig(Path(self.config.save_as).with_suffix(".png"))
        elif self.config.mode == RenderMode.SHOW:
            if 'ipykernel' in sys.modules:
                clear_output(wait=True)
                display(self.fig)
            else:
                plt.ioff()
                plt.show()
        plt.close(self.fig)

    def _render(self):
        self.ax.clear()

        for effect in self.config.effects:
            effect.apply(self.ax, self.simulator.environment)

        self._setup_axis()
        self._setup_limits()

        if self.config.mode == RenderMode.SAVE_ALL:
            self.fig.savefig(
                f"{self.config.snapshot_prefix}_{self.simulator.current_time:.2f}.png"
            )

        if self.config.mode in [RenderMode.SAVE, RenderMode.SAVE_ALL]:
            self.writer.grab_frame()
        elif self.config.mode == RenderMode.SHOW:
            if 'ipykernel' in sys.modules:
                clear_output(wait=True)
                display(self.fig)
            else:
                plt.draw()
                plt.pause(self.config.pause_duration)

    def _setup_axis(self):
        if self.config.show_axis:
            if self.config.title:
                self.ax.set_title(self.config.title)
            self.ax.set_xlabel("X Position")
            self.ax.set_ylabel("Y Position")
            self.ax.axis("on")
        else:
            self.ax.axis("off")
            if self.config.title:
                self.ax.set_title(self.config.title)
                self.fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.9)
            else:
                self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    def _setup_limits(self):
        if self.config.xlim:
            self.ax.set_xlim(self.config.xlim)
        if self.config.ylim:
            self.ax.set_ylim(self.config.ylim)
        elif not self.config.xlim and not self.config.ylim:
            positions = [
                node.position for node in self.simulator.environment.nodes.values()
            ]
            if positions:
                x, y = zip(*positions)
                self.ax.set_xlim(*_padded_limits(x))
                self.ax.set_ylim(*_padded_limits(y))
                self.ax.set_aspect("equal")
        else:
            self.ax.axis("equal")
