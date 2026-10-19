"""
phyelds: A Python library for aggregate computing system with a pythonic interface.

This library provides a set of tools for building and running aggregate computing systems.

A global engine is used to manage the state and message passing between different contexts.
In order to use it, you should:
1. Call `engine.setup(messages, id, state)` to initialize the engine with the current context.
2. Call an aggregate script
3. Call `engine.cooldown()` to reset the engine state and get the messages to send.
4. Store the state for the next iteration.

"""
from contextvars import ContextVar

from phyelds.vm import Engine

# phyelds is a namespace shared with phyelds-simulator and phyelds-vmas. The idiom is the
# one documentation tools recognise; MicroPython has no pkgutil, nor other portions.
try:
    __path__ = __import__("pkgutil").extend_path(__path__, __name__)
except ImportError:
    pass

engine: ContextVar[Engine] = ContextVar("engine")
