"""
A minimal array with elementwise arithmetic, comparisons and logic, as tensors have: what the
clocks and the channel of a wavefront simulation compute on, besides floats.
"""
import operator


class Array:
    """A list of numbers with elementwise operators."""

    def __init__(self, values):
        self.values = list(values)

    def apply(self, other, function):
        """``function`` of each value and of ``other``, or of its value at the same index."""
        others = other.values if isinstance(other, Array) else [other] * len(self.values)
        return Array(function(mine, theirs) for mine, theirs in zip(self.values, others))


_ARITHMETIC = {
    "add": operator.add,
    "sub": operator.sub,
    "mul": operator.mul,
    "truediv": operator.truediv,
    "pow": operator.pow,
    "and": operator.and_,
    "or": operator.or_,
}
_COMPARISONS = {"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}

for _name, _function in _ARITHMETIC.items():
    setattr(Array, f"__{_name}__", lambda self, other, f=_function: self.apply(other, f))
    setattr(
        Array,
        f"__r{_name}__",
        lambda self, other, f=_function: self.apply(other, lambda mine, theirs: f(theirs, mine)),
    )
for _name, _function in _COMPARISONS.items():
    setattr(Array, f"__{_name}__", lambda self, other, f=_function: self.apply(other, f))
