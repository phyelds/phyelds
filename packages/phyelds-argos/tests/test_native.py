"""Exercise the actual ARGoS plugin, rather than a mock radio or controller."""
import os
import json
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.fixture(scope="session")
def plugin(tmp_path_factory):
    from phyelds.argos.build import build_plugin  # pylint: disable=import-outside-toplevel

    library = build_plugin(tmp_path_factory.mktemp("argos-plugin"), gui=False)
    assert library.is_file()
    assert shutil.which("argos3"), "ARGoS must be installed for the integration tests"
    return library


def run_experiment(tmp_path, plugin, *, replacements=(), runner=None):
    """Run a variant of the line experiment, retaining all failure diagnostics."""
    experiment = Path(__file__).parent / "line.argos"
    xml = experiment.read_text().replace("@PLUGIN@", str(plugin.with_suffix("")))
    for old, new in replacements:
        xml = xml.replace(old, new)
    configuration = tmp_path / "line.argos"
    configuration.write_text(xml)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([
        str(Path(__file__).parent), environment.get("PYTHONPATH", "")
    ])
    command = [str(runner), str(configuration)] if runner else ["argos3", "-z", "-n", "-c", str(configuration)]
    return subprocess.run(
        command,
        env=environment, capture_output=True, text=True, timeout=30, check=False,
    )


def test_native_build_and_rounds(tmp_path, plugin):
    result = run_experiment(tmp_path, plugin)
    assert result.returncode == 0, result.stdout + result.stderr
    for node_id in range(5):
        assert f"fb{node_id} final: {node_id}" in result.stdout


def test_native_rounds_are_isolated_and_radio_geometry_uses_the_compass(tmp_path, plugin):
    result = run_experiment(tmp_path, plugin, replacements=[
        ('program="programs:gradient"', 'program="programs:probe" trace="true"'),
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    rounds = [json.loads(line.split(" round: ")[1]) for line in result.stdout.splitlines() if " round: " in line]
    for node_id in range(5):
        node_rounds = [row for row in rounds if row["id"] == node_id]
        assert [row["round"] for row in node_rounds] == list(range(1, 31))
        assert all(row["position"] is None for row in node_rounds)
        assert node_rounds[0]["ranges"] == {str(node_id): 0}
        assert node_rounds[1]["time"] == pytest.approx(0.2)
    one = [row for row in rounds if row["id"] == 1][-1]
    assert one["vectors"]["0"] == pytest.approx([-0.5, 0, 0])
    assert one["vectors"]["2"] == pytest.approx([0.5, 0, 0])


def test_native_rounds_work_on_argos_worker_threads(tmp_path, plugin):
    result = run_experiment(tmp_path, plugin, replacements=[('threads="0"', 'threads="2"')])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fb4 final: 4" in result.stdout


@pytest.mark.parametrize("replacement,message", [
    (("rab_data_size=\"4096\"", "rab_data_size=\"8\""), "exceeds rab_data_size"),
    (("programs:gradient", "programs:not_a_program"), "AttributeError"),
    (("programs:gradient", "programs:broken"), "deliberate program error"),
    (("programs:gradient", "programs:bad_velocity"), "actuator components must be finite"),
    (("programs:gradient", "programs:bad_led"), "led channels must be in [0,255]"),
    (("programs:gradient", "programs:bad_label"), "UnicodeEncodeError"),
    (("source=\"0\"", "source=\"0\" max_speed=\"-1\""), "max_speed must be finite"),
])
def test_native_reports_configuration_program_and_payload_errors(tmp_path, plugin, replacement, message):
    result = run_experiment(tmp_path, plugin, replacements=[replacement])
    assert result.returncode != 0
    assert message in result.stdout + result.stderr
    assert "fb0" in result.stdout + result.stderr


@pytest.fixture(scope="session")
def native_tools(tmp_path_factory):
    source = Path(__file__).parent / "native"
    build = tmp_path_factory.mktemp("argos-test-tools")
    subprocess.run(["cmake", "-S", str(source), "-B", str(build)], check=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel"], check=True)
    return build


def test_native_reset_restarts_each_device_and_clears_the_radio(tmp_path, plugin, native_tools):
    result = run_experiment(tmp_path, plugin, runner=native_tools / "reset", replacements=[
        ('program="programs:gradient"', 'program="programs:probe" trace="true"'),
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    rounds = [json.loads(line.split(" round: ")[1]) for line in result.stdout.splitlines() if " round: " in line]
    node = [row for row in rounds if row["id"] == 1]
    assert [row["round"] for row in node] == list(range(1, 31)) * 2
    assert node[0] == node[30]


@pytest.mark.parametrize("size", [2, 4096])
def test_native_ignores_malformed_radio_frame_lengths(tmp_path, plugin, native_tools, size):
    sender = native_tools / "libbad_sender"
    result = run_experiment(tmp_path, plugin, replacements=[
        ("</controllers>", f'<bad_sender id="bad" library="{sender}"><actuators>'
         '<range_and_bearing implementation="default" /></actuators><sensors /><params /></bad_sender></controllers>'),
        ("</arena>", f'<foot-bot id="bad99" rab_range="0.65" rab_data_size="{size}">'
         '<body position="0,0.5,0" orientation="0,0,0" /><controller config="bad" /></foot-bot></arena>'),
    ])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fb4 final: 4" in result.stdout
