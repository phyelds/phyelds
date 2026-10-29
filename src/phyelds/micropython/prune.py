"""
Leave out of a build the definitions of phyelds that nothing in the build names.

The analysis goes by name, and stays on the safe side: a definition is kept as soon as its
name appears anywhere else in the build.
"""
import ast
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from phyelds.micropython._syntax import decorator_name

# Words in strings count as names: getattr(field, "min") calls a method by its name.
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Methods that Python calls without naming them, besides __dunder__ ones: dict(table).
_IMPLICIT = {"keys"}
# Decorators that only wrap or describe what they decorate: any other one may register it
# somewhere (as the codec's register does), so what it decorates stays.
_PURE_DECORATORS = {
    "aggregate", "classmethod", "contextmanager", "dataclass", "property", "staticmethod",
}


def prune(library: Mapping[Path, str], programs: Mapping[str, str]) -> dict[Path, str]:
    """
    The modules of ``library`` without the definitions that nothing in the build names.

    Args:
        library: The modules of phyelds in the build, by path.
        programs: The modules of the program, by name; they are kept whole.

    Returns:
        The modules of ``library``, pruned.
    """
    trees = {path: ast.parse(source) for path, source in library.items()}
    mentions = Counter()
    for tree in [*trees.values(), *map(ast.parse, programs.values())]:
        mentions.update(_mentions(tree))
    pruned = True
    while pruned:
        pruned = False
        for tree in trees.values():
            pruned |= _prune_body(tree, mentions)
    return {path: ast.unparse(tree) + "\n" for path, tree in trees.items()}


def _prune_body(holder: ast.Module | ast.ClassDef, mentions: Counter) -> bool:
    """
    Remove from the body of ``holder``, and of the classes it keeps, the definitions named
    only in themselves, and their names from ``mentions``; true if it removed any.
    """
    pruned = False
    kept = []
    for statement in holder.body:
        if _removable(statement):
            own = _mentions(statement)
            if mentions[statement.name] == own[statement.name]:
                mentions.subtract(own)
                pruned = True
                continue
        if isinstance(statement, ast.ClassDef):
            pruned |= _prune_body(statement, mentions)
        kept.append(statement)
    holder.body = kept or [ast.Pass()]
    return pruned


def _removable(statement: ast.stmt) -> bool:
    """True for a definition that Python does not call by itself, nor a decorator registers."""
    if not isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
        return False
    name = statement.name
    if (name.startswith("__") and name.endswith("__")) or name in _IMPLICIT:
        return False
    decorators = map(decorator_name, statement.decorator_list)
    return all(decorator in _PURE_DECORATORS for decorator in decorators)


def _mentions(tree: ast.AST) -> Counter:
    """How many times each name appears in ``tree``."""
    words = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words[node.id] += 1
        elif isinstance(node, ast.Attribute):
            words[node.attr] += 1
        elif isinstance(node, ast.alias):
            words.update({node.name.rsplit(".", 1)[-1], node.asname} - {None})
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            words.update(_WORD.findall(node.value))
    return words
