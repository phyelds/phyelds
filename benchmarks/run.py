"""
Measure hosts, adapters and phyelds with many agents in one world.

Each measurement runs in a process of its own, so that the peak memory it reports is its
own, and prints a JSON line: its configuration, its metrics and where it ran (versions,
hardware, commit and seed). From the root of the repository:

    poetry run python benchmarks/run.py --hosts simulator mesa --nodes 100 1000 > results.jsonl

The agents stand on a jittered grid and talk within a radius of 1. At constant density the
area grows with the agents, so that each one has ``--degree`` neighbors on average; at
constant area, the area is that of ``--area-nodes`` agents at that density, so the density
grows with the agents.

The stages split the cost: ``none`` runs the host alone, ``empty`` adds the adapter with a
program that does nothing, and ``gradient``, ``gossip`` and ``count`` run the programs of
``programs.py``. The hosts that run in processes of their own (ARGoS, Webots) report the
time of ``--rounds`` rounds less that of one, to leave their start-up out.
"""
import argparse
import itertools
import json
import math
import os
import platform
import random
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Mapping, Sequence
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = Path(__file__).resolve().parent
# The extensions are not installed with the core: their sources go on the PYTHONPATH.
EXTENSIONS = [
    ROOT / "packages" / name / "src" for name in ("phyelds-mesa", "phyelds-vmas", "phyelds-argos")
]
RADIUS = 1.0
STAGES = ("none", "empty", "gradient", "gossip", "count")
# Webots runs a round at every step of the world.
WEBOTS_STEP_MS = 32
# Foot-bots are 17 cm wide: two metres per unit keep 10,000 of them apart at constant area.
ARGOS_METRES = 2.0

Point = tuple[float, float]
Metrics = dict[str, Any]


def positions(nodes: int, layout: str, degree: float, area_nodes: int, seed: int) -> list[Point]:
    """
    Where the agents stand: a square grid, each point moved at random by up to a fifth of
    the spacing.

    Args:
        nodes: How many agents.
        layout: ``"density"`` for a constant density, ``"area"`` for a constant area.
        degree: The mean number of neighbors at the constant density.
        area_nodes: The agents that fill the constant area at that density.
        seed: The seed of the jitter.

    Returns:
        The position of each agent, the source first.
    """
    density = degree / (math.pi * RADIUS ** 2)
    side = math.sqrt((nodes if layout == "density" else area_nodes) / density)
    columns = math.ceil(math.sqrt(nodes))
    spacing = side / columns
    rng = random.Random(seed)
    points = []
    for index in range(nodes):
        row, column = divmod(index, columns)
        points.append((
            (column + 0.5 + rng.uniform(-0.2, 0.2)) * spacing,
            (row + 0.5 + rng.uniform(-0.2, 0.2)) * spacing,
        ))
    return points


def _timed(action: Callable[[], Any]) -> float:
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


def _rounds(config: Mapping[str, Any], wall: float, **metrics: Any) -> Metrics:
    """The metrics of ``config["rounds"]`` rounds, one per second of simulated time."""
    return {"wall_s": wall, "rounds_timed": config["rounds"], "sim_time": config["rounds"],
            **metrics}


def _program(config: Mapping[str, Any]) -> Callable[[], Any] | None:
    """The program of the stage, or ``None`` for the host alone."""
    import programs  # pylint: disable=import-outside-toplevel  # next to this script

    return None if config["stage"] == "none" else getattr(programs, config["stage"])


def _idle(simulator: Any) -> None:
    """A round of the host alone: nothing, then the next one."""
    simulator.schedule_event(1.0, _idle, simulator)


def _run_simulator(simulator: Any, program: Callable[[], Any] | None, rounds: int) -> float:
    """Run ``rounds`` rounds of ``program`` on every node, and return the wall time they take."""
    # pylint: disable-next=import-outside-toplevel
    from phyelds.simulator.runner import schedule_program_for_all

    if program is None:
        for _ in simulator.environment.nodes:
            simulator.schedule_event(0.0, _idle, simulator)
    else:
        schedule_program_for_all(simulator, 0.0, 1.0, program)
    # Rounds at 0, 1, ...; VMAS steps at 0.5, 1.5, ...: as many steps as rounds.
    return _timed(lambda: simulator.run(rounds - 0.5))


def _traffic(simulator: Any, program: Callable[[], Any] | None) -> Metrics:
    """The neighbor search, timed on its own, and the messages and bytes of the last round."""
    from phyelds.data.codec import encode  # pylint: disable=import-outside-toplevel

    environment = simulator.environment
    nodes = environment.node_list()
    found: list[int] = []
    search = _timed(lambda: found.extend(len(environment.get_neighbors(node)) for node in nodes))
    sent = None if program is None else sum(len(encode(node.data["messages"])) for node in nodes)
    return {"neighbor_search_s": search, "messages_per_round": sum(found), "bytes_per_round": sent}


def simulator_host(config: Mapping[str, Any], points: Sequence[Point]) -> Metrics:
    """The phyelds simulator, with ``radius_neighborhood``."""
    # pylint: disable=import-outside-toplevel  # each host is an optional dependency
    from phyelds.simulator import Simulator
    from phyelds.simulator.neighborhood import radius_neighborhood

    simulator = Simulator()
    for index, point in enumerate(points):
        simulator.create_node(point, data={"source": index == 0}, node_id=index)
    simulator.environment.set_neighborhood_function(radius_neighborhood(RADIUS))
    program = _program(config)
    wall = _run_simulator(simulator, program, config["rounds"])
    return _rounds(config, wall, **_traffic(simulator, program))


def _mesa_agents(config: Mapping[str, Any], points: Sequence[Point]) -> tuple[Any, list[Any]]:
    """A Mesa model with an agent at each of ``points``, in a continuous space."""
    # pylint: disable=import-outside-toplevel  # each host is an optional dependency
    import mesa
    from mesa.experimental.continuous_space import ContinuousSpace, ContinuousSpaceAgent

    side = max(max(point) for point in points) + RADIUS
    model = mesa.Model(rng=config["seed"])
    space = ContinuousSpace(
        [[0, side], [0, side]], torus=False, random=model.random, n_agents=len(points)
    )
    agents = [ContinuousSpaceAgent(space, model) for _ in points]
    for agent, point in zip(agents, points):
        agent.position = list(point)
    return model, agents


def mesa_host(config: Mapping[str, Any], points: Sequence[Point]) -> Metrics:
    """A Mesa model with ``phyelds-mesa`` and ``within``."""
    from phyelds.mesa import AggregateRuntime, within  # pylint: disable=import-outside-toplevel

    model, agents = _mesa_agents(config, points)
    source = agents[0].unique_id
    neighbors = within(RADIUS)
    found: list[int] = []
    search = _timed(lambda: found.extend(len(neighbors(agent)) for agent in agents))
    program = _program(config)
    runtime = None if program is None else AggregateRuntime(
        program, neighbors=neighbors, sensors=lambda agent: {"source": agent.unique_id == source}
    )

    def run() -> None:
        for _ in range(config["rounds"]):
            model.step()
            if runtime is not None:
                runtime.run_round(agents)

    # phyelds-mesa keeps the messages to itself: no bytes to count.
    return _rounds(config, _timed(run), neighbor_search_s=search,
                   messages_per_round=sum(found), bytes_per_round=None)


def _vmas_environment(config: Mapping[str, Any], points: Sequence[Point]) -> Any:
    """VMAS flocking without obstacles, its agents moved to ``points``, wrapped for phyelds."""
    # pylint: disable=import-outside-toplevel  # each host is an optional dependency
    import torch
    from vmas import make_env
    from phyelds.simulator.neighborhood import radius_neighborhood
    from phyelds.vmas import VmasEnvironment

    vmas_environment = make_env(
        scenario="flocking", num_envs=1, seed=config["seed"], n_agents=len(points), n_obstacles=0
    )
    environment = VmasEnvironment(vmas_environment, radius_neighborhood(RADIUS))
    for (index, node), point in zip(environment.nodes.items(), points):
        vmas_environment.agents[index].set_pos(torch.tensor([point]), batch_index=None)
        node.position = point
        node.data["source"] = index == 0
    return environment


def vmas_host(config: Mapping[str, Any], points: Sequence[Point]) -> Metrics:
    """VMAS, stepped by ``vmas_runner`` with the actions of the programs."""
    # pylint: disable=import-outside-toplevel  # each host is an optional dependency
    import torch
    from phyelds.calculus import aggregate
    from phyelds.simulator import Simulator
    from phyelds.vmas import vmas_runner
    from phyelds.vmas.devices import action

    environment = _vmas_environment(config, points)
    simulator = Simulator(environment)
    program = _program(config)
    if program is None:
        still = [torch.zeros((1, 2)) for _ in points]
        steps = range(config["rounds"])
        wall = _timed(lambda: [environment.vmas_environment.step(still) for _ in steps])
        return _rounds(config, wall, **_traffic(simulator, None))

    @aggregate
    def standing_still() -> Any:
        """The program, and an action that keeps the agent where it is: VMAS needs one."""
        result = program()
        action.send([0.0, 0.0])
        return result

    simulator.schedule_event(0.5, vmas_runner, simulator, 1.0)
    wall = _run_simulator(simulator, standing_still, config["rounds"])
    return _rounds(config, wall, **_traffic(simulator, standing_still))


ARGOS_EXPERIMENT = """<?xml version="1.0" ?>
<argos-configuration>
  <framework>
    <system threads="0" />
    <experiment length="{rounds}" ticks_per_second="1" random_seed="{seed}" />
  </framework>
  <controllers>
    <phyelds_controller id="phyelds" library="{plugin}">
      <actuators>
        <differential_steering implementation="default" />
        <range_and_bearing implementation="default" />
      </actuators>
      <sensors>
        <range_and_bearing implementation="medium" medium="rab" />
        <positioning implementation="default" />
      </sensors>
      <params program="programs:{program}" source="0" />
    </phyelds_controller>
  </controllers>
  <arena size="{size},{size},1" center="{center},{center},0.5">
{robots}
  </arena>
  <physics_engines><dynamics2d id="dyn2d" /></physics_engines>
  <media><range_and_bearing id="rab" check_occlusions="false" /></media>
</argos-configuration>
"""
ARGOS_ROBOT = (
    '    <foot-bot id="fb{index}" rab_range="{range}" rab_data_size="4096">'
    '<body position="{x},{y},0" orientation="0,0,0" /><controller config="phyelds" />'
    "</foot-bot>"
)


def argos_host(config: Mapping[str, Any], points: Sequence[Point]) -> Metrics:
    """ARGoS foot-bots with ``phyelds-argos``, over their range-and-bearing radio."""
    from phyelds.argos.build import build_plugin  # pylint: disable=import-outside-toplevel

    if config["stage"] == "none":
        raise ValueError("ARGoS robots need a controller: there is no host alone to measure")
    plugin = build_plugin(Path(config["build_dir"]) / "argos", gui=False)
    side = (max(max(point) for point in points) + RADIUS) * ARGOS_METRES
    robots = "\n".join(
        ARGOS_ROBOT.format(index=index, range=RADIUS * ARGOS_METRES,
                           x=x * ARGOS_METRES, y=y * ARGOS_METRES)
        for index, (x, y) in enumerate(points)
    )

    def run(rounds: int) -> float:
        with tempfile.TemporaryDirectory() as directory:
            experiment = Path(directory) / "benchmark.argos"
            experiment.write_text(ARGOS_EXPERIMENT.format(
                rounds=rounds, seed=config["seed"], plugin=plugin.with_suffix(""),
                program=config["stage"], size=side, center=side / 2, robots=robots,
            ), encoding="utf-8")
            command = ["argos3", "-z", "-n", "-c", str(experiment)]
            return _timed(lambda: _run_quietly(command, _controllers()))

    return _difference(run, config["rounds"])


WEBOTS_ROBOT = """Robot {{
  translation {x} {y} 0
  name "r{index}"
  controller "{controller}"
  controllerArgs [ {arguments} ]
  children [ Emitter {{ range {range} }} Receiver {{ }} ]
}}"""
WEBOTS_STOPPER = """from controller import Supervisor

supervisor = Supervisor()
for _ in range({rounds}):
    supervisor.step(int(supervisor.getBasicTimeStep()))
supervisor.simulationQuit(0)
"""


def webots_host(config: Mapping[str, Any], points: Sequence[Point]) -> Metrics:
    """Webots robots, a process each, with ``phyelds-webots`` over their Emitter and Receiver."""
    if config["stage"] == "none":
        controller, arguments = "<none>", ""
    else:
        controller = "phyelds_controller"
        arguments = f'"programs:{config["stage"]}" "--source" "r0"'
    robots = "\n".join(
        WEBOTS_ROBOT.format(index=index, x=x, y=y, controller=controller, arguments=arguments,
                            range=RADIUS)
        for index, (x, y) in enumerate(points)
    )
    controllers = ROOT / "docs" / "examples" / "webots" / "controllers" / "phyelds_controller"
    environment = _controllers(ROOT / "packages" / "phyelds-webots" / "src")

    def run(rounds: int) -> float:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(controllers, project / "controllers" / "phyelds_controller")
            stopper = project / "controllers" / "stopper" / "stopper.py"
            stopper.parent.mkdir()
            stopper.write_text(WEBOTS_STOPPER.format(rounds=rounds), encoding="utf-8")
            world = project / "worlds" / "benchmark.wbt"
            world.parent.mkdir()
            world.write_text("\n".join([
                "#VRML_SIM R2025a utf8", f"WorldInfo {{ basicTimeStep {WEBOTS_STEP_MS} }}",
                'Robot { name "stopper" supervisor TRUE controller "stopper" }', robots,
            ]) + "\n", encoding="utf-8")
            command = ["webots", "--batch", "--mode=fast", "--no-rendering", "--minimize",
                       "--stdout", "--stderr", str(world)]
            return _timed(lambda: _run_quietly(command, environment))

    return _difference(run, config["rounds"], seconds_per_round=WEBOTS_STEP_MS / 1000)


def _controllers(*extensions: Path) -> dict[str, str]:
    """
    The environment of controllers that run in processes of their own: the python3 of this
    environment, which finds phyelds from the sources and the programs of the benchmarks.
    """
    paths = [ROOT / "src", *extensions, BENCHMARKS]
    return {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": os.pathsep.join([*map(str, paths), os.environ.get("PYTHONPATH", "")]),
    }


def _run_quietly(command: Sequence[str], environment: Mapping[str, str]) -> None:
    """Run ``command``, and raise with the end of its output if it, or a controller, fails."""
    completed = subprocess.run(command, capture_output=True, text=True, env=environment,
                               check=False)
    output = completed.stdout + completed.stderr
    # Webots carries on, and exits with 0, when a controller fails.
    if completed.returncode != 0 or "Traceback" in output:
        raise RuntimeError(f"{command[0]} failed: {output[-2000:]}")


def _difference(
    run: Callable[[int], float], rounds: int, seconds_per_round: float = 1.0
) -> Metrics:
    """The time of ``rounds`` rounds less that of one, which leaves the start-up out."""
    startup = run(1)
    total = run(rounds)
    return {"wall_s": total - startup, "rounds_timed": rounds - 1,
            "sim_time": (rounds - 1) * seconds_per_round, "startup_s": startup,
            "neighbor_search_s": None, "messages_per_round": None, "bytes_per_round": None}


HOSTS: dict[str, Callable[[Mapping[str, Any], Sequence[Point]], Metrics]] = {
    "simulator": simulator_host, "mesa": mesa_host, "vmas": vmas_host,
    "argos": argos_host, "webots": webots_host,
}


def measure(config: Mapping[str, Any]) -> Metrics:
    """Run one measurement, in this process, and return its configuration and metrics."""
    points = positions(config["nodes"], config["layout"], config["degree"],
                       config["area_nodes"], config["seed"])
    metrics = HOSTS[config["host"]](config, points)
    wall = metrics["wall_s"]
    peak = max(resource.getrusage(who).ru_maxrss
               for who in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN))
    return {
        **config,
        "agents": len(points),
        "phyelds_agents": 0 if config["stage"] == "none" else len(points),
        "worlds": 1,
        **metrics,
        "agent_rounds_per_s": len(points) * metrics["rounds_timed"] / wall,
        "sim_over_wall": metrics["sim_time"] / wall,
        "rss_peak_mb": peak / 1024,  # ru_maxrss is in KiB on Linux
    }


def provenance() -> dict[str, Any]:
    """The versions, hardware and commit the measurements ran with."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    versions = {"phyelds": project["tool"]["poetry"]["version"]}
    for package in ("mesa", "vmas", "torch"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            pass
    for tool in ("argos3", "webots"):
        if shutil.which(tool):
            completed = subprocess.run([tool, "--version"], capture_output=True, text=True,
                                       timeout=60, check=False)
            plain = re.sub(r"\x1b\[[0-9;]*m", "", completed.stdout)  # ARGoS colours its output
            versions[tool] = plain.strip().splitlines()[0]
    commit = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=ROOT,
                            capture_output=True, text=True, check=False).stdout.strip()
    return {
        "python": platform.python_version(),
        "versions": versions,
        "commit": commit,
        "cpu": _cpu(),
        "cpus": os.cpu_count(),
        "memory_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 1),
        "os": platform.platform(),
    }


def _cpu() -> str:
    """The model of the processor."""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    return platform.processor()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--hosts", nargs="+", choices=HOSTS, default=["simulator", "mesa"])
    parser.add_argument("--nodes", nargs="+", type=int, default=[100, 1000])
    parser.add_argument("--layouts", nargs="+", choices=("density", "area"),
                        default=["density", "area"])
    parser.add_argument("--stages", nargs="+", choices=STAGES, default=list(STAGES))
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--degree", type=float, default=8.0,
                        help="mean neighbors at the constant density")
    parser.add_argument("--area-nodes", type=int, default=1000,
                        help="agents that fill the constant area")
    parser.add_argument("--seed", type=int, default=1)
    builds = Path(tempfile.gettempdir()) / "phyelds-benchmarks"
    parser.add_argument("--build-dir", default=str(builds),
                        help="where to build the ARGoS plugin")
    parser.add_argument("--measure", help=argparse.SUPPRESS)  # one measurement, in this process
    return parser


def main() -> None:
    """Run every combination of the arguments, each in a process of its own."""
    args = _parser().parse_args()
    if args.measure:
        print(json.dumps(measure(json.loads(args.measure))))
        return
    context = provenance()
    paths = [*map(str, EXTENSIONS), os.environ.get("PYTHONPATH", "")]
    measuring = {**os.environ, "PYTHONPATH": os.pathsep.join(path for path in paths if path)}
    combinations = itertools.product(args.hosts, args.nodes, args.layouts, args.stages)
    for host, nodes, layout, stage in combinations:
        config = {"host": host, "nodes": nodes, "layout": layout, "stage": stage,
                  "rounds": args.rounds, "degree": args.degree, "area_nodes": args.area_nodes,
                  "seed": args.seed, "build_dir": args.build_dir}
        completed = subprocess.run([sys.executable, __file__, "--measure", json.dumps(config)],
                                   capture_output=True, text=True, env=measuring, check=False)
        if completed.returncode == 0:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        else:
            result = {**config, "error": completed.stderr.strip()[-1000:]}
        print(json.dumps({**result, "environment": context}), flush=True)


if __name__ == "__main__":
    main()
