import matplotlib

matplotlib.use("Agg")

# pylint: disable=wrong-import-position
import pytest
from matplotlib import colormaps
from matplotlib import pyplot as plt
from matplotlib.animation import FFMpegWriter, PillowWriter
from matplotlib.colors import to_rgba
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


def _face_colors(effect: DrawNodes, simulator: Simulator) -> list[tuple[float, ...]]:
    figure, ax = plt.subplots()
    effect.apply(ax, simulator.environment)
    colors = [tuple(color) for color in ax.collections[0].get_facecolors()]
    plt.close(figure)
    return colors


def _simulator_with_results(results: dict[int, object]) -> Simulator:
    simulator = Simulator()
    for node_id, result in results.items():
        node = simulator.create_node((float(node_id), 0.0), node_id=node_id)
        if result is not None:
            node.data["result"] = result
    return simulator


def test_draw_nodes_maps_finite_values_onto_the_colormap():
    simulator = _simulator_with_results({0: 0.0, 1: 5.0, 2: 10.0})
    effect = DrawNodes(color_from="result", cmap="viridis")

    colors = _face_colors(effect, simulator)

    viridis = colormaps["viridis"]
    assert colors[0] == pytest.approx(viridis(0.0))
    assert colors[1] == pytest.approx(viridis(0.5))
    assert colors[2] == pytest.approx(viridis(1.0))


def test_draw_nodes_uses_missing_color_for_infinite_or_absent_values():
    simulator = _simulator_with_results({0: 0.0, 1: float("inf"), 2: None, 3: 4.0})
    effect = DrawNodes(color_from="result", cmap="viridis", missing_color="red")

    colors = _face_colors(effect, simulator)

    assert colors[1] == pytest.approx(to_rgba("red"))
    assert colors[2] == pytest.approx(to_rgba("red"))
    assert colors[3] == pytest.approx(colormaps["viridis"](1.0))


def test_draw_nodes_respects_explicit_colormap_bounds():
    simulator = _simulator_with_results({0: 2.0, 1: 20.0})
    effect = DrawNodes(color_from="result", cmap="viridis", vmin=0.0, vmax=4.0)

    colors = _face_colors(effect, simulator)

    assert colors[0] == pytest.approx(colormaps["viridis"](0.5))
    assert colors[1] == pytest.approx(colormaps["viridis"](1.0))


def test_draw_nodes_without_colormap_keeps_raw_colors():
    simulator = _simulator_with_results({0: "green", 1: None})
    effect = DrawNodes(color_from="result")

    colors = _face_colors(effect, simulator)

    assert colors == [pytest.approx(to_rgba("green")), pytest.approx(to_rgba("blue"))]
