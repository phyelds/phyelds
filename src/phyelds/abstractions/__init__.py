"""
Engine interface: how to implement an aggregate computing engine.
"""
from abc import ABC


class Engine(ABC):
    """
    Abstract base class for the engine. This class should be implemented by the user.
    """

    def __init__(self):
        self.node_id = None

    def setup(
        self, node_id: int, messages: dict[int, dict[str, any]], state=None
    ) -> None:
        """
        Setup the engine with the current context.
        :param node_id:
        :param messages: The messages to send.
        :param state: The state of the engine.
        """

    def enter(self, name: str) -> None:
        """
        Enter a new context.
        :param name: The name of the context.
        """

    def exit(self) -> None:
        """
        Exit the current context.
        """

    def current_path(self) -> list[str]:
        """
        Get the current path of the engine.
        :return: The current path.
        """

    def write_state(self, value: any, stack: list[str]) -> None:
        """
        Write the state of the engine.
        :param value: The value to write.
        :param stack: The stack of the engine.
        """

    def read_state(self, stack: list[str]) -> any:
        """
        Read the state of the engine.
        :param stack: The stack of the engine.
        :return: The value of the state.
        """

    def state_trace(self) -> dict[str, any]:
        """
        Get the state trace of the engine.
        :return: The state trace.
        """

    def forget(self, _self_path):
        """
        Forget the value store in the engine.
        :param _self_path:
        :return:
        """

    def send(self, data: any) -> None:
        """
        Send data to the engine.
        :param data: The data to send.
        """

    def aligned(self) -> list[int]:
        """
        Get the aligned ids.
        :return: The aligned ids.
        """

    def aligned_values(self, path: list[str]) -> dict[int, any]:
        """
        Get the aligned values.
        :param path: The path of the values.
        :return: The aligned values.
        """

    def cooldown(self) -> None:
        """
        Cooldown the engine.
        :return:
        """
