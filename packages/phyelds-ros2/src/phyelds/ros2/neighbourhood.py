"""
Who, among the nodes heard on the shared topic, is a neighbour: strategies a node is given.

A strategy adds to each message what the others need to judge its sender (``header``), and
judges each message heard (``admit``), from the position of the node that hears it.
"""
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Neighbour:
    """
    A sender a strategy admits, with what it measured of it.

    Attributes:
        distance: How far the sender is, in metres; ``None`` if the strategy cannot tell.
        vector: From this node to the sender, in the frame of the positions; ``None`` if the
            strategy cannot tell.
    """

    distance: float | None = None
    vector: tuple[float, ...] | None = None


class Neighbourhood(Protocol):
    """A strategy that decides the neighbours of a node."""

    def header(self, position: Sequence[float] | None) -> dict[str, Any]:
        """What to add to the message of a node at ``position``, ``None`` if unknown."""

    def admit(
        self, header: Mapping[str, Any], position: Sequence[float] | None
    ) -> Neighbour | None:
        """The sender of ``header``, as a neighbour of a node at ``position``, or ``None``."""


class Reachable:
    """
    The nodes this node hears are its neighbours: the network decides the neighbourhood.

    On one host, a LAN or in a simulator, every node hears every other; on robots that talk
    over an ad-hoc or mesh radio, the nodes heard are those in range. A node that stops
    sending is forgotten after the ``lifetime`` of its messages.

    Args:
        measure: Whether each message carries the position of its sender, so that a
            neighbour comes with its distance and vector when both positions are known.
            Positions must then be in a frame all the nodes share.
    """

    def __init__(self, *, measure: bool = False):
        self.measure = measure

    def header(self, position: Sequence[float] | None) -> dict[str, Any]:
        """The position of the sender if measuring, ``None`` while it is unknown; else nothing."""
        return _position_header(position) if self.measure else {}

    def admit(
        self, header: Mapping[str, Any], position: Sequence[float] | None
    ) -> Neighbour | None:
        """The sender, measured if possible: every sender heard is a neighbour."""
        return _measured(header, position) or Neighbour()


class WithinRange:
    """
    The nodes within a radius are neighbours: each message carries the position of its sender.

    Positions must be in a frame all the nodes share, such as ``map`` or the world of a simulator.

    Args:
        radius: How far a node reaches, in metres.
    """

    def __init__(self, radius: float):
        self.radius = radius

    def header(self, position: Sequence[float] | None) -> dict[str, Any]:
        """The position of the sender, ``None`` while it is unknown."""
        return _position_header(position)

    def admit(
        self, header: Mapping[str, Any], position: Sequence[float] | None
    ) -> Neighbour | None:
        """
        The sender, with its distance and the vector to it, if it is within the radius.

        A sender is not admitted while its position or that of this node is unknown.
        """
        neighbour = _measured(header, position)
        if neighbour is None or neighbour.distance > self.radius:
            return None
        return neighbour


def _position_header(position: Sequence[float] | None) -> dict[str, Any]:
    """A header with ``position``, ``None`` while it is unknown."""
    return {"position": None if position is None else list(position)}


def _measured(header: Mapping[str, Any], position: Sequence[float] | None) -> Neighbour | None:
    """The sender of ``header`` measured from ``position``; ``None`` if a position is unknown."""
    if header.get("position") is None or position is None:
        return None
    vector = tuple(there - here for there, here in zip(header["position"], position))
    return Neighbour(distance=math.hypot(*vector), vector=vector)
