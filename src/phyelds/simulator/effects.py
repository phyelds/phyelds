"""
This module contains the effects that can be applied to the simulation rendering.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Literal, Optional, Any, Annotated, Tuple, List
from pydantic import BaseModel, Field, BeforeValidator, SerializeAsAny
from phyelds.simulator import Environment


class Link:
    """
    A class to represent a link between two nodes.
    The link is represented as a tuple of two nodes.
    Note!
    Link(node1, node2) == Link(node2, node1)
    """

    def __init__(self, node1: Tuple[float, ...], node2: Tuple[float, ...]):
        self.node1 = node1
        self.node2 = node2

    def __hash__(self):
        return hash(frozenset((self.node1, self.node2)))

    def __eq__(self, other):
        if isinstance(other, Link):
            return frozenset((self.node1, self.node2)) == frozenset(
                (other.node1, other.node2)
            )
        return False


class Effect(BaseModel, ABC):
    """
    Abstract base class for effects.
    """
    z_order: int = 0

    @abstractmethod
    def apply(self, ax, environment: Environment):
        """
        Apply the effect to the matplotlib axis.
        """


class DrawEdges(Effect):
    """
    Draw edges between nodes.
    """
    type: Literal["DrawEdges"] = "DrawEdges"
    alpha: float = 0.6
    z_order: int = 0

    def apply(self, ax, environment: Environment):
        """
        Draw edges between nodes.
        """
        all_neighbors_tuple = set()
        for node in environment.nodes.values():
            neighbors = node.get_neighbors()
            for neighbor in neighbors:
                all_neighbors_tuple.add(Link(node.position, neighbor.position))
        for link in all_neighbors_tuple:
            ax.plot(
                [link.node1[0], link.node2[0]],
                [link.node1[1], link.node2[1]],
                alpha=self.alpha,
                color="gray",
                zorder=self.z_order,
            )


class DrawNodes(Effect):
    """
    Draw nodes.
    """
    type: Literal["DrawNodes"] = "DrawNodes"
    color_from: Optional[str] = None
    z_order: int = 10

    def apply(self, ax, environment: Environment):
        """
        Draw nodes.
        """
        positions = [node.position for node in environment.nodes.values()]
        if not positions:
            return
        x, y = zip(*positions)

        if self.color_from:
            colors = [
                node.data.get(self.color_from, "blue")
                for node in environment.nodes.values()
            ]
            ax.scatter(x, y, c=colors, zorder=self.z_order)
        else:
            ax.scatter(x, y, c="blue", zorder=self.z_order)


class DrawIDs(Effect):
    """
    Draw node IDs.
    """
    type: Literal["DrawIDs"] = "DrawIDs"
    z_order: int = 20

    def apply(self, ax, environment: Environment):
        """
        Draw node IDs.
        """
        # Add node IDs as text labels
        for node in environment.nodes.values():
            ax.text(
                node.position[0] + 0.02,
                node.position[1],
                str(node.id),
                fontsize=8,
                ha="center",
                va="center",
                bbox={"facecolor": "white", "alpha": 0.1, "edgecolor": "none"},
                zorder=self.z_order,
            )


def validate_effect(v: Any) -> Any:
    """
    Validate the effect type.
    """
    if isinstance(v, dict):
        effect_type = v.get("type")
        for sub in Effect.__subclasses__():
            # pylint: disable=unsupported-membership-test, unsubscriptable-object
            if (
                "type" in sub.model_fields
                and sub.model_fields["type"].default == effect_type
            ):
                return sub.model_validate(v)
        raise ValueError(f"Unknown effect type: {effect_type}")
    return v


EffectType = Annotated[Effect, BeforeValidator(validate_effect)]


class RenderMode(str, Enum):
    """
    Enum for render modes.
    """
    SHOW = "show"
    SAVE = "save"
    SAVE_ALL = "save_all"


class RenderConfig(BaseModel):
    """
    Configuration for the RenderMonitor.
    """

    effects: List[SerializeAsAny[EffectType]] = Field(default_factory=list)
    dt: float = 1.0
    skip: float = 0.0
    pause_duration: float = 0.001
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    mode: RenderMode = RenderMode.SHOW
    save_as: str = "simulation.mp4"
    snapshot_prefix: str = "snapshot"
    show_axis: bool = True
    title: Optional[str] = None

    def save(self, path: str):
        """
        Save the configuration to a file.
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load(cls, path: str):
        """
        Load the configuration from a file.
        """
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
