import ast
import subprocess
import sys
import textwrap

from phyelds.micropython.build import build, transpile


def _transpiled(source: str, **options) -> str:
    return transpile(textwrap.dedent(source), **options)


def test_transpile_aligns_the_branches_of_aggregate_functions():
    output = _transpiled("""
        @aggregate
        def program(flag):
            if flag:
                return 1
            return 2 if flag else neighbors(3)
    """)

    assert "with align_left():" in output
    assert "_aligned_branch(flag, lambda: 2, lambda: neighbors(3))" in output
    assert "from phyelds.calculus import _aligned_branch, align_left, align_right" in output


def test_transpile_aligns_nested_aggregate_functions_once():
    output = _transpiled("""
        @aggregate
        def outer(flag):
            @aggregate
            def inner():
                if flag:
                    return 1
            return inner()
    """)

    assert output.count("align_left()") == 1


def test_transpile_leaves_the_branches_of_other_functions_alone():
    output = _transpiled("""
        def helper(flag):
            if flag:
                return 1
    """)

    assert "align" not in output


def test_transpile_does_not_import_helpers_in_the_module_defining_them():
    output = _transpiled("""
        def align_left():
            pass

        @aggregate
        def program(flag):
            if flag:
                return 1
    """)

    assert "import" not in output


def test_transpile_removes_annotations():
    output = _transpiled("""
        def scale(value: float, *rest: int, factor: float = 2.0, **options: str) -> float:
            result: float = value * factor
            unused: int
            return result
    """)

    assert ":" not in output.replace("def scale(value, *rest, factor=2.0, **options):", "")


def test_transpile_redirects_modules_missing_on_micropython():
    output = _transpiled("""
        import wrapt
        import math
        from typing import Any
        from collections.abc import Callable
        from contextvars import ContextVar
    """)

    assert output.splitlines() == [
        "import phyelds._mpy.wrapt as wrapt",
        "import math",
        "from phyelds._mpy.typing import Any",
        "from phyelds._mpy.typing import Callable",
        "from phyelds._mpy.contextvars import ContextVar",
    ]


def test_transpile_spells_out_unpacking_in_tuples_and_lists():
    output = _transpiled("""
        extended = (*hops, last)
        both = [first, *middle, *rest]
        first, *others = items
    """)

    assert output.splitlines() == [
        "extended = tuple(hops) + (last,)",
        "both = [first] + list(middle) + list(rest)",
        "first, *others = items",
    ]


def test_transpile_reduces_type_expressions_to_their_typing_name():
    output = _transpiled("""
        from typing import Callable, cast
        Strategy = Callable[[float, Field[float]], int | None]
        value = cast(Field[bool], compute())
        size = sizes[0]
    """)

    assert output.splitlines()[1:] == [
        "Strategy = Callable",
        "value = compute()",
        "size = sizes[0]",
    ]


def test_transpile_drops_generic_base_classes():
    output = _transpiled("""
        class Field(Generic[T], Iterator[T], Base):
            pass
    """)

    assert "class Field(Base):" in output


def test_transpile_lists_the_fields_of_dataclasses():
    output = _transpiled('''
        @dataclass(frozen=True)
        class Reading:
            """A reading."""
            sensor: str
            value: float = 0.0
    ''')

    reading = ast.parse(output).body[0]
    assert ast.unparse(reading.body[1]) == "__dataclass_fields__ = ('sensor', 'value')"
    assert ast.unparse(reading.body[2]) == "value = 0.0"


def test_transpile_turns_enum_attributes_into_members():
    output = _transpiled("""
        class Status(Enum):
            ON = "on"
    """)

    assert output.startswith("from phyelds._mpy.enum import members as _phyelds_enum_members")
    assert "@_phyelds_enum_members\nclass Status(Enum):" in output


def test_transpile_records_the_signatures_of_program_functions():
    output = _transpiled("""
        def step(edge, data=None, *rest, key, **options):
            return data

        def outer():
            def inner(a):
                pass
    """, signatures=True)

    assert output.startswith("from phyelds._mpy.inspect import register as _phyelds_signature")
    assert (
        "_phyelds_signature(step, (('edge', 1, False), ('data', 1, True), ('rest', 2, False), "
        "('key', 3, False), ('options', 4, False)))"
    ) in output
    assert "inner, " not in output


def test_build_writes_the_library_without_the_parts_needing_cpython(tmp_path):
    build([], tmp_path)

    assert (tmp_path / "phyelds" / "__init__.py").exists()
    assert (tmp_path / "phyelds" / "_mpy" / "wrapt.py").exists()
    assert not (tmp_path / "phyelds" / "simulator").exists()
    assert not (tmp_path / "phyelds" / "micropython").exists()
    assert not (tmp_path / "phyelds" / "calculus" / "internal" / "transform.py").exists()


def test_build_output_runs_a_program_like_the_library(tmp_path):
    program = tmp_path / "program.py"
    program.write_text(textwrap.dedent("""
        from phyelds import engine
        from phyelds.calculus import aggregate, neighbors, remember
        from phyelds.vm import NodeContext
        from phyelds.vm.internal import MutableEngine


        @aggregate
        def program():
            set_count, count = remember(0)
            if count < 2:
                return set_count(count + neighbors(1).sum())
            return count


        def run():
            state, outbox = {}, {}
            for _ in range(3):
                engine.set(MutableEngine().setup(NodeContext(0, {}), {1: outbox}, state))
                result = program()
                outbox = engine.get().cooldown()
                state = engine.get().state_trace()
            return result, sorted(outbox)
    """))
    reference = subprocess.run(
        [sys.executable, "-c", "import program; print(program.run())"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    ).stdout
    build([program], tmp_path / "dist")

    bundled = subprocess.run(
        [sys.executable, "-c", "import program; print(program.run())"],
        cwd=tmp_path / "dist", capture_output=True, text=True, check=True,
    ).stdout

    assert bundled == reference
