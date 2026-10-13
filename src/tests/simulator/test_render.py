import matplotlib

matplotlib.use("Agg")

# pylint: disable=wrong-import-position
from matplotlib.animation import FFMpegWriter, PillowWriter
from PIL import Image

from phyelds.simulator import Simulator
from phyelds.simulator.effects import DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.render import RenderMonitor, make_writer


def _line_simulator(size: int) -> Simulator:
    """A line of nodes whose last node moves up at every step, so each frame differs."""
    simulator = Simulator()
    for index in range(size):
        simulator.create_node((float(index), 0.0), node_id=index)
    moving = simulator.environment.nodes[size - 1]
    for step in range(1, 4):
        simulator.schedule_event(float(step), moving.update, (float(size - 1), float(step)))
    return simulator


def test_make_writer_uses_pillow_for_gif():
    config = RenderConfig(save_as="animation.gif")

    assert isinstance(make_writer(config), PillowWriter)


def test_make_writer_uses_ffmpeg_for_mp4():
    config = RenderConfig(save_as="animation.mp4")

    assert isinstance(make_writer(config), FFMpegWriter)


def test_render_monitor_saves_an_animated_gif(tmp_path):
    simulator = _line_simulator(3)
    gif_path = tmp_path / "animation.gif"
    config = RenderConfig(effects=[DrawNodes()], mode=RenderMode.SAVE, save_as=str(gif_path))
    RenderMonitor(simulator, config)

    simulator.run()

    with Image.open(gif_path) as gif:
        assert gif.n_frames > 1
    assert (tmp_path / "animation.png").exists()
