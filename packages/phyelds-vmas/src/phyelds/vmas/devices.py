"""Sensors and actions shared by VMAS programs and their host."""

from collections.abc import Sequence

from torch import Tensor
from vmas.simulator.core import Agent

from phyelds.libraries.device import Actuator, Sensor

observations: Sensor[Tensor] = Sensor("observations")
"""The agent's observation tensor in environment zero."""

rewards: Sensor[Tensor] = Sensor("rewards")
"""The agent's scalar reward tensor in environment zero; initially zero."""

dones: Sensor[bool] = Sensor("dones")
"""Whether environment zero has finished; initially false."""

infos: Sensor[dict[str, Tensor]] = Sensor("infos")
"""The agent's info tensors in environment zero; initially an empty dictionary."""

agent: Sensor[Agent] = Sensor("agent")
"""The VMAS agent, whose state still contains all environments."""

action: Actuator[Sequence[float] | Tensor | int] = Actuator("action")
"""The scenario's continuous or discrete action, repeated across environments."""
