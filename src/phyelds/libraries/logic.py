"""
Spatial and temporal logic operators for aggregate computing (from FCPP ``slcs`` and ``past_ctl``).

Provides:
- **Spatial Logic for Closure Spaces (SLCS)**: ``interior``, ``closure``, ``boundary``,
  ``interior_boundary``, ``closure_boundary``, ``somewhere``, ``everywhere``,
  ``reaches``, ``touches``, ``surrounds``;
- **Past Computation Tree Logic (Past-CTL)**: ``yesterday``, ``since``,
  ``previously``, ``historically`` with ``scope`` in ``("local", "all", "any")``.
"""

from typing import Literal

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.libraries.spreading import SpreadingStrategy, distance_to
from phyelds.libraries.time import delay

PastScope = Literal["local", "all", "any"]
_VALID_SCOPES: tuple[str, ...] = ("local", "all", "any")


def _validate_scope(scope: str) -> None:
    """Validate that ``scope`` is one of ``'local'``, ``'all'``, or ``'any'``."""
    if scope not in _VALID_SCOPES:
        raise ValueError(f"scope must be one of {_VALID_SCOPES}, got {scope!r}")


@aggregate
def interior(region: bool) -> bool:
    """
    Return True on devices in the topological interior of ``region`` (SLCS ``I``).

    Holds when ``region`` is True on the current device and on all its neighbors.
    """
    return neighbors(bool(region)).all()


@aggregate
def closure(region: bool) -> bool:
    """
    Return True on devices in the topological closure of ``region`` (SLCS ``C``).

    Holds when ``region`` is True on the current device or on at least one neighbor.
    """
    return neighbors(bool(region)).any()


@aggregate
def boundary(region: bool) -> bool:
    """
    Return True on the full topological boundary of ``region`` (SLCS ``B``).

    Holds on devices in ``closure(region)`` that are not in ``interior(region)``.
    """
    in_closure = closure(region)
    in_interior = interior(region)
    return in_closure and not in_interior


@aggregate
def interior_boundary(region: bool) -> bool:
    """
    Return True on the inner frontier of ``region`` (SLCS ``IB``).

    Holds on devices inside ``region`` that have at least one neighbor outside ``region``.
    """
    in_interior = interior(region)
    return bool(region) and not in_interior


@aggregate
def closure_boundary(region: bool) -> bool:
    """
    Return True on the outer fringe of ``region`` (SLCS ``CB``).

    Holds on devices outside ``region`` that have at least one neighbor inside ``region``.
    """
    in_closure = closure(region)
    return in_closure and not bool(region)


@aggregate
def somewhere(
    condition: bool,
    *,
    max_diameter: float = 20.0,
    strategy: SpreadingStrategy | None = None,
) -> bool:
    """
    Return True if ``condition`` holds on any reachable device within ``max_diameter`` (SLCS ``F``).

    Args:
        condition: Local boolean formula.
        max_diameter: Upper bound on the hop distance considered reachable.
        strategy: Optional spreading strategy (e.g. ``path_coherent()``).
    """
    return float(distance_to(bool(condition), strategy=strategy)) < max_diameter


@aggregate
def everywhere(
    condition: bool,
    *,
    max_diameter: float = 20.0,
    strategy: SpreadingStrategy | None = None,
) -> bool:
    """
    Return True if ``condition`` holds on all reachable devices within ``max_diameter``.

    Args:
        condition: Local boolean formula.
        max_diameter: Upper bound on the hop distance considered reachable.
        strategy: Optional spreading strategy (e.g. ``path_coherent()``).
    """
    return not somewhere(not bool(condition), max_diameter=max_diameter, strategy=strategy)


@aggregate
def reaches(
    region: bool,
    target: bool,
    *,
    max_diameter: float = 20.0,
    strategy: SpreadingStrategy | None = None,
) -> bool:
    """
    Return True if a path entirely contained in ``region`` reaches a ``target`` node (SLCS ``R``).

    Because the ``if region`` branch splits alignment, reachability only propagates
    across devices where ``region`` holds.
    """
    return (
        somewhere(target, max_diameter=max_diameter, strategy=strategy)
        if region
        else False
    )


@aggregate
def touches(
    region: bool,
    target: bool,
    *,
    max_diameter: float = 20.0,
    strategy: SpreadingStrategy | None = None,
) -> bool:
    """
    Return True on nodes in ``region`` whose component is adjacent to ``target`` (SLCS ``T``).

    Equivalent to ``reaches(region, closure(target))``.
    """
    near_target = closure(target)
    return reaches(region, near_target, max_diameter=max_diameter, strategy=strategy)


@aggregate
def surrounds(
    region: bool,
    barrier: bool,
    *,
    max_diameter: float = 20.0,
    strategy: SpreadingStrategy | None = None,
) -> bool:
    """
    Return True on nodes in ``region`` enclosed by ``barrier`` (SLCS ``U`` / surrounding).

    Holds on devices in ``region`` whose neighborhood cannot reach ``not region``
    without passing through ``barrier``.
    """
    escaped = reaches(
        not bool(barrier),
        not bool(region),
        max_diameter=max_diameter,
        strategy=strategy,
    )
    enclosed_neighborhood = interior(not escaped)
    return bool(region) and enclosed_neighborhood


@aggregate
def _run_yesterday(condition: bool, scope: PastScope) -> bool:
    """Aggregate implementation of yesterday."""
    flag = bool(condition)
    if scope == "local":
        return delay(flag, initial=False)
    if scope == "all":
        set_field, field = exchange(True)
        result = field.all()
        set_field(flag)
        return result
    set_field, field = exchange(False)
    result = field.any()
    set_field(flag)
    return result


def yesterday(condition: bool, *, scope: PastScope = "local") -> bool:
    """
    Check whether ``condition`` held in the previous round (Past-CTL ``Y``, ``AY``, ``EY``).

    Args:
        condition: Local boolean formula.
        scope: ``"local"`` (same device, ``Y``), ``"all"`` (all neighbors, ``AY``),
            or ``"any"`` (at least one neighbor, ``EY``).
    """
    _validate_scope(scope)
    return _run_yesterday(condition, scope)


@aggregate
def _run_since(sustained: bool, triggered: bool, scope: PastScope) -> bool:
    """Aggregate implementation of since."""
    sust = bool(sustained)
    trig = bool(triggered)
    if scope == "local":
        set_state, prev = remember(False)
        current = trig or (sust and bool(prev.value))
        set_state(current)
        return current
    if scope == "all":
        set_field, field = exchange(False)
        current = trig or (sust and field.all())
        set_field(current)
        return current
    set_field, field = exchange(False)
    current = trig or (sust and field.any())
    set_field(current)
    return current


def since(
    sustained: bool,
    triggered: bool,
    *,
    scope: PastScope = "local",
) -> bool:
    """
    Check whether ``sustained`` has held continuously since ``triggered`` held (Past-CTL).

    Args:
        sustained: Condition that must remain True after ``triggered``.
        triggered: Condition that initiates the interval.
        scope: ``"local"`` (``S``), ``"all"`` (``AS``), or ``"any"`` (``ES``).
    """
    _validate_scope(scope)
    return _run_since(sustained, triggered, scope)


def previously(condition: bool, *, scope: PastScope = "local") -> bool:
    """
    Check whether ``condition`` held at least once in the past (Past-CTL ``P``, ``AP``, ``EP``).

    Args:
        condition: Local boolean formula.
        scope: ``"local"`` (``P``), ``"all"`` (``AP``), or ``"any"`` (``EP``).
    """
    return since(True, condition, scope=scope)


@aggregate
def _run_historically(condition: bool, scope: PastScope) -> bool:
    """Aggregate implementation of historically."""
    flag = bool(condition)
    if scope == "local":
        set_state, prev = remember(True)
        current = flag and bool(prev.value)
        set_state(current)
        return current
    if scope == "all":
        set_field, field = exchange(True)
        current = flag and field.all()
        set_field(current)
        return current
    set_field, field = exchange(True)
    current = flag and field.any()
    set_field(current)
    return current


def historically(condition: bool, *, scope: PastScope = "local") -> bool:
    """
    Check whether ``condition`` has always held in the past (Past-CTL ``H``, ``AH``, ``EH``).

    Args:
        condition: Local boolean formula.
        scope: ``"local"`` (``H``), ``"all"`` (``AH``), or ``"any"`` (``EH``).
    """
    _validate_scope(scope)
    return _run_historically(condition, scope)
