from fieldpy.internal import Engine, MutableEngine

"""
FieldPy: A Python library for aggregate computing system with a pythonic interface.
"""


"""
Global engine instance (singleton pattern)
In order to use it, you should:
1. Call `engine.setup(messages, id, state)` to initialize the engine with the current context.
2. Call an aggregate script 
3. Call `engine.cooldown()` to reset the engine state and get the messages to send.
4. Store the state for the next iteration.
"""
engine = MutableEngine()
