"""Webots worlds that put each wheeled robot Webots ships under the phyelds controller."""
import shutil
from dataclasses import dataclass
from pathlib import Path

from session import ROOT

PROTOS = "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots"
CONTROLLER = ROOT / "docs" / "examples" / "webots" / "controllers" / "phyelds_controller"
FAR = 4.0  # metres between the groups of a world, beyond the range of their radios


@dataclass(frozen=True)
class Robot:
    """
    A robot of Webots, with what the controller needs to know of it.

    ``proto`` is its path among the robots of Webots, ``slot`` the field that takes extra
    devices, and ``spacing`` how far apart, in metres, its robots stand in a line. ``wall`` is
    how far from the robot a wall is seen by its distance sensors; ``None`` if it sees none.
    """

    proto: str
    slot: str
    wheel_radius: float
    spacing: float
    wall: float | None
    wheels: tuple[str, str] = ("left wheel motor", "right wheel motor")

    @property
    def node(self) -> str:
        """The name of the PROTO node."""
        return Path(self.proto).stem

    def arguments(self, program: str) -> list[str]:
        """The arguments of the controller that run ``program`` on this robot."""
        return [
            f"programs:{program}", "--trace", "--emitter", "radio_tx", "--receiver", "radio_rx",
            "--wheel-radius", str(self.wheel_radius), "--wheels", *self.wheels,
        ]

    def write_world(self, project: Path) -> Path:
        """
        Write a project with a world of three groups, far apart, and return the world.

        Three robots stand in a line and measure how far they are from the first, ``g0``; the
        robot ``mover`` heads north; the robot ``watcher`` faces a wall, if the robot sees walls.
        """
        shutil.copytree(CONTROLLER, project / "controllers" / CONTROLLER.name)
        robots = [
            self._robot(f"g{index}", (index * self.spacing, 0.0), [*self.arguments("metres"), "--source", "g0"])
            for index in range(3)
        ]
        robots.append(self._robot("mover", (0.0, FAR), [*self.arguments("heads_north"), "--gps"]))
        robots.append(self._robot("watcher", (0.0, -FAR), self.arguments("says_obstacle")))
        world = project / "worlds" / f"{self.node}.wbt"
        world.parent.mkdir()
        world.write_text("\n".join([
            "#VRML_SIM R2025a utf8",
            f'EXTERNPROTO "{PROTOS}/{self.proto}"',
            "WorldInfo { basicTimeStep 32 }",
            "Viewpoint { orientation 0 1 0 1.57 position 0 0 12 }",
            _solid("floor", "Plane { size 20 20 }", (0.0, 0.0, 0.0)),
            *robots,
            *([] if self.wall is None else [_solid("wall", "Box { size 0.02 1 0.3 }", (self.wall + 0.01, -FAR, 0.15))]),
        ]) + "\n")
        return world

    def _robot(self, name: str, where: tuple[float, float], arguments: list[str]) -> str:
        """A robot of this kind, with a radio of limited range, an inertial unit and a GPS."""
        quoted = " ".join(f'"{argument}"' for argument in arguments)
        devices = (
            f'Emitter {{ name "radio_tx" range {1.5 * self.spacing} channel 7 }} '
            'Receiver { name "radio_rx" channel 7 } InertialUnit { } GPS { }'
        )
        return (
            f'{self.node} {{ translation {where[0]} {where[1]} 0 name "{name}" '
            f'controller "phyelds_controller" controllerArgs [ {quoted} ] {self.slot} [ {devices} ] }}'
        )


def _solid(name: str, geometry: str, where: tuple[float, float, float]) -> str:
    """A light solid, which infra-red sensors see."""
    appearance = "PBRAppearance { baseColor 1 1 1 roughness 1 metalness 0 }"
    return (
        f'Solid {{ translation {where[0]} {where[1]} {where[2]} name "{name}" '
        f"children [ Shape {{ appearance {appearance} geometry {geometry} }} ] boundingObject {geometry} }}"
    )


ROBOTS = {
    "e-puck": Robot("gctronic/e-puck/protos/E-puck.proto", "turretSlot", 0.02, 0.1, wall=0.06),
    "elisa-3": Robot("gctronic/elisa/protos/Elisa3.proto", "extensionSlot", 0.0045, 0.1, wall=0.045),
    "khepera-iii": Robot("k-team/khepera3/protos/Khepera3.proto", "turretSlot", 0.0212, 0.3, wall=0.1),
    "khepera-iv": Robot("k-team/khepera4/protos/Khepera4.proto", "turretSlot", 0.021, 0.3, wall=0.1),
    "thymio-ii": Robot(
        "mobsya/thymio/protos/Thymio2.proto", "bodySlot", 0.021, 0.3, wall=0.1, wheels=("motor.left", "motor.right")
    ),
    "create": Robot("irobot/create/protos/Create.proto", "bodySlot", 0.031, 0.6, wall=None),
    "pioneer-3dx": Robot(
        "adept/pioneer3/protos/Pioneer3dx.proto", "extensionSlot", 0.0975, 0.8, wall=0.4,
        wheels=("left wheel", "right wheel"),
    ),
}
