from abc import ABC


class Engine(ABC):
    """
    Abstract base class for the engine. This class should be implemented by the user.
    """

    def __init__(self):
        self.id = None

    def setup(self, messages: dict[int, dict[str, any]], id: int, state=None) -> None:
        """
        Setup the engine with the current context.
        :param messages: The messages to send.
        :param id: The id of the current iteration.
        :param state: The state of the engine.
        """
        pass

    def enter(self, name: str) -> None:
        """
        Enter a new context.
        :param name: The name of the context.
        """
        pass

    def write_state(self, value: any, stack: list[str]) -> None:
        """
        Write the state of the engine.
        :param value: The value to write.
        :param stack: The stack of the engine.
        """
        pass

    def read_state(self, stack: list[str]) -> any:
        """
        Read the state of the engine.
        :param stack: The stack of the engine.
        :return: The value of the state.
        """
        pass

    def exit(self) -> None:
        """
        Exit the current context.
        """
        pass

    def send(self, data: any) -> None:
        """
        Send data to the engine.
        :param data: The data to send.
        """
        pass

    def aligned(self) -> list[int]:
        """
        Get the aligned ids.
        :return: The aligned ids.
        """
        pass

    def aligned_values(self, path: list[str]) -> dict[int, any]:
        """
        Get the aligned values.
        :param path: The path of the values.
        :return: The aligned values.
        """
        pass

    def cooldown(self) -> None:
        """
        Cooldown the engine.
        :return:
        """

    def forget(self, _self_path):
        pass
