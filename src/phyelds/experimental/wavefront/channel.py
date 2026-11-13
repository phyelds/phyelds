"""
The channel between devices: how late messages arrive, how many are lost, and for how long a
silent neighbor is still heard.

Like a clock, a channel turns randomness drawn by the runtime into deliveries, with arithmetic
operators and comparisons only: the same channel works on the floats of one message and on
arrays, such as tensors, holding one value per message.
"""
from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class Channel:
    """
    Communication channel governing delivery latency, packet loss and message expiry.

    Args:
        delay: Minimum transmission and propagation delay ``>= 0``.
        jitter: Additional uniform delivery delay in ``[0, jitter]``.
        loss: Independent packet drop probability in ``[0.0, 1.0]``.
        retention: Maximum age of a delivered message before a silent neighbor expires;
            ``None`` keeps the latest delivered message while the sender stays a neighbor.
    """

    delay: float = 0.0
    jitter: float = 0.0
    loss: float = 0.0
    retention: float | None = None

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError(f"delay must be non-negative, not {self.delay}")
        if self.jitter < 0:
            raise ValueError(f"jitter must be non-negative, not {self.jitter}")
        if not 0.0 <= self.loss <= 1.0:
            raise ValueError(f"loss must be in [0.0, 1.0], not {self.loss}")
        if self.retention is not None and self.retention <= 0:
            raise ValueError(f"retention must be positive, not {self.retention}")

    def lost(self, uniform: Any) -> Any:
        """
        Whether a message is lost.

        Args:
            uniform: A uniform draw in ``[0, 1)``, new for each message.

        Returns:
            Whether ``uniform`` falls below ``loss``.
        """
        return uniform < self.loss

    def arrival(self, sent: Any, uniform: Any) -> Any:
        """
        When a message arrives.

        Args:
            sent: The time the message was sent.
            uniform: A uniform draw in ``[0, 1)``, new for each message.

        Returns:
            ``sent`` plus ``delay`` plus the share ``uniform`` of ``jitter``.
        """
        return sent + self.delay + self.jitter * uniform

    def heard(self, age: Any) -> Any:
        """
        Whether a message is heard, given how long ago it arrived.

        Args:
            age: The time since the message arrived; negative if it has not arrived yet.

        Returns:
            Whether the message has arrived and, with a ``retention``, is not older than it.
        """
        if self.retention is None:
            return age >= 0.0
        return (age >= 0.0) & (age <= self.retention)


@dataclass
class _LinkSlot:
    """Committed and in-flight packets on a directed link ``sender -> receiver``."""

    committed: dict[str, Any] | None = None
    committed_at: float = -math.inf
    pending: dict[str, Any] | None = None
    pending_at: float = math.inf

    def transmit(self, payload: dict[str, Any], arrival: float) -> None:
        """Queue ``payload`` arriving at ``arrival``, promoting any earlier arrived packet."""
        if self.pending is not None and self.pending_at <= arrival:
            self.committed = self.pending
            self.committed_at = self.pending_at
        self.pending = payload
        self.pending_at = arrival

    def read_at(self, now: float, channel: Channel) -> dict[str, Any] | None:
        """Return the latest packet delivered by ``now`` that ``channel`` still hears."""
        if self.pending is not None and self.pending_at <= now:
            self.committed = self.pending
            self.committed_at = self.pending_at
            self.pending = None
            self.pending_at = math.inf
        if self.committed is None or not channel.heard(now - self.committed_at):
            return None
        return self.committed
