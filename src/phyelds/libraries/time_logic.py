"""
Group of function used to create distributed monitors about temporal events.
"""
from phyelds.calculus import remember, neighbors


def yesterday(expression: bool) -> bool:
    """
    Yesterday function in temporal logic: it returns the expression value happen the tick before.
    :param expression: the expression to remember.
    """
    expression = remember((False, False))
    return expression.update_fn(lambda x: (expression, x[0]))[1]

def all_in_yesterday(expression: bool) -> bool:
    """
    All yesterday function in temporal logic: it returns the expression value happen the tick before in all the neighbors.
    :param expression: the expression to remember.
    """
    expression = remember((True, True))
    all_neighbors = neighbors(expression[0]).all()
    return expression.update_fn(lambda x: (expression, all_neighbors))[1]

def any_in_yesterday(expression: bool) -> bool:
    """
    Any yesterday function in temporal logic: it returns the expression value happen the tick before in any of the neighbors.
    :param expression: the expression to remember.
    """
    expression = remember((False, False))
    any_neighbors = neighbors(expression[0]).any()
    return expression.update_fn(lambda x: (expression, any_neighbors))[1]