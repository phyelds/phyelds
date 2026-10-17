import ast
import functools
import textwrap
import traceback

import pytest
from phyelds import engine
from phyelds.calculus import aggregate, neighbors, str_transformed_code
from phyelds.calculus.internal import AggregateTransformer
from phyelds.libraries.device import local_id
from phyelds.vm.internal import MutableEngine
from tests.calculus.mock import MockNodeContext, MockSimulator


# ---------- AST helpers ----------

def _transform_source(source: str):
    tree = ast.parse(textwrap.dedent(source))
    transformer = AggregateTransformer()
    return transformer.visit(tree)


def _get_function_body(tree):
    func_def = tree.body[0]
    return func_def.body


def _assert_with_align(node, expected_name: str):
    assert isinstance(node, ast.With)
    assert len(node.items) == 1
    context_expr = node.items[0].context_expr
    assert isinstance(context_expr, ast.Call)
    assert isinstance(context_expr.func, ast.Name)
    assert context_expr.func.id == expected_name


# ---------- AST structure tests ----------

def test_simple_if_else_transformed():
    source = """
    def f():
        if x:
            a = 1
        else:
            a = 2
    """
    tree = _transform_source(source)
    body = _get_function_body(tree)
    assert len(body) == 1
    if_node = body[0]
    assert isinstance(if_node, ast.If)
    assert len(if_node.body) == 1
    _assert_with_align(if_node.body[0], "align_left")
    assert len(if_node.orelse) == 1
    _assert_with_align(if_node.orelse[0], "align_right")


def test_if_without_else_transformed():
    source = """
    def f():
        if x:
            a = 1
    """
    tree = _transform_source(source)
    body = _get_function_body(tree)
    if_node = body[0]
    assert isinstance(if_node, ast.If)
    assert len(if_node.body) == 1
    _assert_with_align(if_node.body[0], "align_left")
    assert len(if_node.orelse) == 1
    _assert_with_align(if_node.orelse[0], "align_right")
    assert isinstance(if_node.orelse[0].body[0], ast.Pass)


def test_nested_if_same_branch_transformed():
    source = """
    def f():
        if x:
            if y:
                a = 1
            else:
                a = 2
    """
    tree = _transform_source(source)
    body = _get_function_body(tree)
    outer_if = body[0]
    assert isinstance(outer_if, ast.If)
    assert len(outer_if.body) == 1
    _assert_with_align(outer_if.body[0], "align_left")
    inner_if = outer_if.body[0].body[0]
    assert isinstance(inner_if, ast.If)
    assert len(inner_if.body) == 1
    _assert_with_align(inner_if.body[0], "align_left")
    assert len(inner_if.orelse) == 1
    _assert_with_align(inner_if.orelse[0], "align_right")


def test_nested_if_cross_branches_transformed():
    source = """
    def f():
        if x:
            a = 1
        else:
            if y:
                a = 2
            else:
                a = 3
    """
    tree = _transform_source(source)
    body = _get_function_body(tree)
    outer_if = body[0]
    assert isinstance(outer_if, ast.If)
    assert len(outer_if.body) == 1
    _assert_with_align(outer_if.body[0], "align_left")
    assert len(outer_if.orelse) == 1
    _assert_with_align(outer_if.orelse[0], "align_right")
    inner_if = outer_if.orelse[0].body[0]
    assert isinstance(inner_if, ast.If)
    assert len(inner_if.body) == 1
    _assert_with_align(inner_if.body[0], "align_left")
    assert len(inner_if.orelse) == 1
    _assert_with_align(inner_if.orelse[0], "align_right")


def test_multiple_sequential_ifs_transformed():
    source = """
    def f():
        if x:
            a = 1
        else:
            a = 2
        if y:
            b = 1
        else:
            b = 2
    """
    tree = _transform_source(source)
    body = _get_function_body(tree)
    assert len(body) == 2
    for if_node in body:
        assert isinstance(if_node, ast.If)
        assert len(if_node.body) == 1
        _assert_with_align(if_node.body[0], "align_left")
        assert len(if_node.orelse) == 1
        _assert_with_align(if_node.orelse[0], "align_right")


def test_deeply_nested_ifs_transformed():
    source = """
    def f():
        if a:
            if b:
                if c:
                    d = 1
                else:
                    d = 2
            else:
                e = 1
        else:
            f = 1
    """
    tree = _transform_source(source)
    body = _get_function_body(tree)
    level1 = body[0]
    assert isinstance(level1, ast.If)
    _assert_with_align(level1.body[0], "align_left")
    level2 = level1.body[0].body[0]
    assert isinstance(level2, ast.If)
    _assert_with_align(level2.body[0], "align_left")
    level3 = level2.body[0].body[0]
    assert isinstance(level3, ast.If)
    _assert_with_align(level3.body[0], "align_left")
    _assert_with_align(level3.orelse[0], "align_right")


# ---------- Utility tests ----------

def test_print_transformed_code_outputs_aligns(capsys):
    def sample():
        if True:
            pass
        else:
            pass
    output = str_transformed_code(sample)
    assert "align_left" in output
    assert "align_right" in output


# ---------- Behavioral coherence tests ----------

@pytest.fixture(scope="function", autouse=True)
def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))


def test_simple_if_else_all_true_behavior():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if True:
            return neighbors(1)
        else:
            return neighbors(2)

    simulator.cycle_for(program, 9)
    # every node takes the if branch (align_left) and communicates
    for node in simulator.nodes:
        assert node.root.data == {0: 1, 1: 1, 2: 1}


def test_cross_branch_isolation_behavior():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if True:
            return neighbors(10)
        else:
            return neighbors(20)

    simulator.cycle_for(program, 9)
    # all nodes are in align_left -> same zone
    for node in simulator.nodes:
        assert set(node.root.data.values()) == {10}


def test_condition_based_isolation_behavior():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if local_id() < 2:
            return neighbors(local_id())
        else:
            return neighbors(local_id())

    simulator.cycle_for(program, 9)
    # nodes 0 and 1 share align_left; node 2 is align_right
    assert simulator.nodes[0].root.data == {0: 0, 1: 1}
    assert simulator.nodes[1].root.data == {0: 0, 1: 1}
    assert simulator.nodes[2].root.data == {2: 2}


def test_nested_if_same_outer_branch_behavior():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if True:
            if True:
                return neighbors(100)
            else:
                return neighbors(200)
        else:
            return neighbors(300)

    simulator.cycle_for(program, 9)
    # all nodes in outer left + inner left
    for node in simulator.nodes:
        assert set(node.root.data.values()) == {100}


def test_nested_if_same_outer_different_inner_isolation():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if local_id() < 2:
            if local_id() == 0:
                return neighbors(local_id())
            else:
                return neighbors(local_id())
        else:
            return neighbors(local_id())

    simulator.cycle_for(program, 9)
    # node 0: outer left + inner left
    assert simulator.nodes[0].root.data == {0: 0}
    # node 1: outer left + inner right -> different path from node 0
    assert simulator.nodes[1].root.data == {1: 1}
    # node 2: outer right -> isolated from outer left
    assert simulator.nodes[2].root.data == {2: 2}


def test_sequential_ifs_independent_behavior():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if True:
            a = neighbors(1)
        else:
            a = neighbors(2)
        if True:
            b = neighbors(10)
        else:
            b = neighbors(20)
        return a, b

    simulator.cycle_for(program, 9)
    for node in simulator.nodes:
        a, b = node.root
        assert set(a.data.values()) == {1}
        assert set(b.data.values()) == {10}


def test_if_without_else_post_alignment_behavior():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if local_id() < 2:
            return neighbors(local_id())
        return neighbors(999)

    simulator.cycle_for(program, 9)
    # nodes 0 and 1: took align_left, see each other
    # node 2: took implicit align_right, isolated
    # The fix ensures counters are balanced after the if
    assert simulator.nodes[0].root.data == {0: 0, 1: 1}
    assert simulator.nodes[1].root.data == {0: 0, 1: 1}
    assert simulator.nodes[2].root.data == {2: 999}


def test_if_without_else_counter_alignment_after_branch():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if local_id() < 2:
            x = 1
        # After the if, all nodes should have balanced counters
        # so subsequent aggregate calls work correctly
        return neighbors(local_id())

    simulator.cycle_for(program, 9)
    # All nodes call neighbors(local_id()) after the if
    # With balanced counters, they all share the same path
    # and can communicate
    for node in simulator.nodes:
        assert node.root.data == {0: 0, 1: 1, 2: 2}



# ---------- Conditional expressions ----------

def test_conditional_expression_isolates_its_branches():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        return neighbors(local_id()) if local_id() < 2 else neighbors(local_id())

    simulator.cycle_for(program, 9)
    # nodes 0 and 1 take the first branch, node 2 the second: they do not meet
    assert simulator.nodes[0].root.data == {0: 0, 1: 1}
    assert simulator.nodes[1].root.data == {0: 0, 1: 1}
    assert simulator.nodes[2].root.data == {2: 2}


def test_conditional_expression_keeps_later_calls_aligned_when_a_branch_does_not_communicate():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        nearest = float("inf") if local_id() == 0 else min(neighbors(1))
        return nearest, neighbors(local_id())

    simulator.cycle_for(program, 9)
    # node 0 skips neighbors(1), yet all nodes meet in the call that follows
    for node in simulator.nodes:
        assert node.root[1].data == {0: 0, 1: 1, 2: 2}


def test_conditional_expression_without_calls_is_left_as_is():
    source = """
    def f():
        return 1 if x else y
    """
    tree = _transform_source(source)
    returned = _get_function_body(tree)[0].value
    assert isinstance(returned, ast.IfExp)


def test_conditional_expression_keeps_an_assignment_expression_in_the_function():
    simulator = MockSimulator(1)

    @aggregate
    def program():
        size = None
        _ = (size := sum(neighbors(1))) if True else 0
        return size

    simulator.cycle_for(program, 3)
    assert simulator.nodes[0].root == 1


# ---------- Decorators stacked with @aggregate ----------

_CALLS = []


def counted(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _CALLS.append(fn)
        return fn(*args, **kwargs)
    return wrapper


def _run_once(program):
    _CALLS.clear()
    node_engine = MutableEngine()
    engine.set(node_engine)
    node_engine.setup(MockNodeContext(0), {}, {})
    return program()


def test_aggregate_reports_an_error_at_its_line_in_the_source_file():
    @aggregate
    def program():
        return 1 / 0

    with pytest.raises(ZeroDivisionError) as raised:
        _run_once(program)

    failing = traceback.extract_tb(raised.value.__traceback__)[-1]
    assert failing.filename == __file__
    assert failing.lineno == program.__wrapped__.__code__.co_firstlineno + 2
    assert failing.line == "return 1 / 0"


def test_decorator_above_aggregate_runs_once():
    @counted
    @aggregate
    def program():
        return 1

    assert _run_once(program) == 1
    assert len(_CALLS) == 1


def test_decorator_above_qualified_aggregate_runs_once():
    import phyelds.calculus

    @counted
    @phyelds.calculus.aggregate
    def program():
        return 1

    assert _run_once(program) == 1
    assert len(_CALLS) == 1


def test_decorator_above_aggregate_may_reference_locals():
    calls = []

    def recording(fn):
        def wrapper():
            calls.append(fn)
            return fn()
        return wrapper

    @recording
    @aggregate
    def program():
        return 1

    assert _run_once(program) == 1
    assert len(calls) == 1


def test_decorator_below_aggregate_is_kept():
    @aggregate
    @counted
    def program():
        return 1

    assert _run_once(program) == 1
    assert len(_CALLS) == 1

