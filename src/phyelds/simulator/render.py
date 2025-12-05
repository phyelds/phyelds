"""
Render the nodes in the simulator's environment.
"""
import sys
from IPython.display import display, clear_output
from matplotlib import pyplot as plt
from matplotlib.animation import FFMpegWriter

from phyelds.simulator import Simulator, Monitor
from phyelds.simulator.effects import RenderConfig, RenderMode


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
            metadata = {"title": "Simulation", "artist": "Phyelds"}
            self.writer = FFMpegWriter(
                fps=1 / self.config.dt if self.config.dt > 0 else 15, metadata=metadata
            )
            self.writer.setup(self.fig, self.config.save_as, dpi=100)
        elif self.config.mode == RenderMode.SHOW:
            plt.ion()
            plt.show()

    def update(self):
        if self.simulator.current_time < self.config.skip:
            return
        if self.simulator.current_time - self.last_render_time >= self.config.dt:
            self._render()
            self.last_render_time = self.simulator.current_time

    def on_finish(self):
        if self.config.mode in [RenderMode.SAVE, RenderMode.SAVE_ALL]:
            self.writer.finish()
            if self.config.mode == RenderMode.SAVE:
                self.fig.savefig(self.config.save_as.replace(".mp4", ".png"))
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
                pad = 0.05
                x_range = max(x) - min(x)
                y_range = max(y) - min(y)
                self.ax.set_xlim(min(x) - pad * x_range, max(x) + pad * x_range)
                self.ax.set_ylim(min(y) - pad * y_range, max(y) + pad * y_range)
                self.ax.set_aspect("equal")
        else:
            self.ax.axis("equal")