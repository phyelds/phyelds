from functools import reduce

from fieldpy.calculus import aggregate, remember


def min_with_default(iterable, default=None):
    return (
        reduce(lambda x, y: x if x < y else y, iterable, default)
        if iterable
        else default
    )


@aggregate
def counter():
    return remember(0).update_fn(lambda x: x + 1)
