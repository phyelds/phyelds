"""
Core syntax for phyelds.
It exposes a set of functions that are used to create and manipulate fields,
as well as to manage the state of the system.
@aggregate is a decorator that marks a function as an aggregate function,
Example:
@aggregate
def my_function():
    # do something
    return result

Then, there is the core syntax of phyelds:
- remember: used to remember a value across iterations.
- neighbors: used to get the neighbors of a node.
- neighbors_distances: used to get the distances to the neighbors.
"""
import ast
import inspect
import textwrap

from phyelds import engine
from phyelds.calculus.align import AlignContext
from phyelds.calculus.internal import AggregateTransformer
from phyelds.data import State, Field


def aggregate(func):
    """
    A decorator for aggregate functions,
    namely each function that is called in the context of a field.
    You can use it in the following way:
    @aggregate
    def my_function():
        # do something
        return result
    """

    def wrapper(*args, **kwargs):
        engine.get().enter(func.__name__)
        result = transform_code(func)(*args, **kwargs)
        engine.get().exit()
        return result

    return wrapper


@aggregate
def remember(init):
    """
    One of the main operator of phyelds.

    :param init:
    :return:
    """
    state = State(init, engine.get().current_path(), engine.get())
    return state.update_fn, state

def remember_and_evolve(init, evolve_fn):
    """
    Remember a value across iterations and evolve it using the provided function.

    :param init: Initial value to remember.
    :param evolve_fn: Function to evolve the remembered value.
    :return: A tuple containing the update function and the state.
    """
    state = State(init, engine.get().current_path(), engine.get())
    state.update_fn(evolve_fn(state))
    return state

@aggregate
def neighbors(value):
    """
    Get the `value` of the neighbors from the current node.
    Example:
    neighbors(context.data["temperature"]) // returns the temperature of the neighbors
    :param value: used to query the neighbors.
    :return: the field representing this value
    """
    if isinstance(value, Field):
        raise TypeError("Field is not supported as a value")
    engine.get().send(value)
    values = engine.get().aligned_values(engine.get().current_path())
    values[engine.get().node_context.node_id] = value
    return Field(values, engine.get().node_context.node_id)


def align(name: str):
    """
    Used to align a part of the code with the current context,
    creating different non communicating zones
    :param name: what you would like to align on
    :return: the context
    """
    return AlignContext(name)


def align_right():
    """
    Typically used in if statements to align the code
    Example:
    if condition:
        with align_left():
            # do something
    else:
        with align_right():
            # do something else
    :return:
    """
    return align("left")


def align_left():
    """
    Typically used in if statements to align the code
    See align_right
    """
    return align("right")


_TRANSFORMATION_CACHE = {}


# pylint: disable=exec-used,broad-exception-caught
def transform_code(func):
    """
    Transforms the code of the given function to include alignment contexts.
    :param func: The function to transform.
    :return: The transformed function.
    """
    if func.__code__ in _TRANSFORMATION_CACHE:
        code_obj = _TRANSFORMATION_CACHE[func.__code__]
    else:
        try:
            source = inspect.getsource(func)
            source = textwrap.dedent(source)
            tree = ast.parse(source)
            func_def = tree.body[0]
            if hasattr(func_def, 'decorator_list'):
                func_def.decorator_list = [
                    d for d in func_def.decorator_list
                    if not (isinstance(d, ast.Name) and d.id == 'aggregate')
                ]

            transformer = AggregateTransformer()
            tree = transformer.visit(tree)
            ast.fix_missing_locations(tree)
            code_obj = compile(tree, filename="<aggregated_code>", mode="exec")
            _TRANSFORMATION_CACHE[func.__code__] = code_obj
        except Exception as e:
            print(f"WARNING: AST transformation failed ({e}). Using original function.")
            return func
    scope = func.__globals__.copy()
    scope['align_left'] = align_left
    scope['align_right'] = align_right
    if func.__closure__ and func.__code__.co_freevars:
        for name, cell in zip(func.__code__.co_freevars, func.__closure__):
            try:
                scope[name] = cell.cell_contents
            except ValueError:
                pass
    local_scope = {}
    exec(code_obj, scope, local_scope)
    return local_scope[func.__name__]
