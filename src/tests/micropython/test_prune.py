import textwrap
from pathlib import Path

from phyelds.micropython.prune import prune

LIBRARY = Path("phyelds") / "library.py"


def _pruned(library: str, program: str) -> str:
    modules = prune({LIBRARY: textwrap.dedent(library)}, {"main.py": textwrap.dedent(program)})
    return modules[LIBRARY]


def test_prune_drops_the_functions_nothing_names():
    output = _pruned("""
        def used():
            pass

        def unused():
            pass
    """, "from phyelds.library import used\n")

    assert "def used" in output
    assert "def unused" not in output


def test_prune_drops_the_classes_and_methods_nothing_names():
    output = _pruned("""
        class Used:
            def called(self):
                pass

            def uncalled(self):
                pass

        class Unused:
            pass
    """, "from phyelds.library import Used\nUsed().called()\n")

    assert "class Used" in output and "def called" in output
    assert "uncalled" not in output and "Unused" not in output


def test_prune_drops_what_only_dropped_definitions_name():
    output = _pruned("""
        def helper():
            pass

        def unused():
            return helper()
    """, "")

    assert "helper" not in output


def test_prune_keeps_what_a_dropped_class_and_a_kept_function_both_name():
    output = _pruned("""
        def helper():
            pass

        class Unused:
            def run(self):
                return helper()

        def used():
            return helper()
    """, "from phyelds.library import used\n")

    assert "def helper" in output


def test_prune_keeps_the_definitions_named_in_strings():
    output = _pruned("""
        class Field:
            def smallest(self):
                pass

            def largest(self):
                pass
    """, "from phyelds.library import Field\ngetattr(Field(), 'smallest')()\nREDUCERS = 'largest, sum'\n")

    assert "def smallest" in output and "def largest" in output


def test_prune_keeps_the_methods_python_calls_by_itself():
    output = _pruned("""
        class Table:
            def __init__(self):
                pass

            def __add__(self, other):
                pass

            def keys(self):
                pass
    """, "from phyelds.library import Table\ndict(Table() + Table())\n")

    assert "__init__" in output and "__add__" in output and "def keys" in output


def test_prune_keeps_the_definitions_whose_decorators_may_register_them():
    output = _pruned("""
        @register
        class Message:
            pass

        @aggregate
        def unused():
            pass

        @dataclass(frozen=True)
        class Reading:
            @property
            def unused_value(self):
                pass
    """, "from phyelds.library import Reading\n")

    assert "class Message" in output and "class Reading" in output
    assert "unused()" not in output and "unused_value" not in output
