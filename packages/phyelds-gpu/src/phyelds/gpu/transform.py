"""AST staging transforming standard Python ``@aggregate`` functions for SPMD tensor execution."""

import ast
import builtins
from collections.abc import Callable
import functools
import inspect
import math
import textwrap
import types
from typing import Any

import torch

from phyelds import engine
from phyelds.calculus import _aligned_branch, align_left, align_right
from phyelds.calculus.internal import _bound_to_its_scope, _calls_anything
from phyelds.calculus.internal.transform import (
    _PrivateNames,
    _drop_applied_decorators,
    _owner_class,
)
from phyelds.gpu.fields import BatchedNeighborhoodField, _as_node_tensor, _promote_pair

_COMPILED_CACHE: dict[types.CodeType, Callable[..., Any]] = {}


def _gpu_float(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.to(dtype=torch.float64)
    return builtins.float(value)


def _gpu_int(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.to(dtype=torch.int64)
    return builtins.int(value)


def _gpu_bool(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.to(dtype=torch.bool)
    return builtins.bool(value)


def _gpu_len_attr(obj: Any) -> Any:
    if isinstance(obj, BatchedNeighborhoodField):
        return obj.count_entries(include_self=True)
    return builtins.len(obj)


def _gpu_not(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return ~value.to(dtype=torch.bool)
    return not value


def _gpu_and(*values: Any) -> Any:
    if not any(isinstance(v, torch.Tensor) for v in values):
        result = values[0]
        for item in values[1:]:
            if not result:
                return result
            result = item
        return result
    batch_eng = engine.get()
    out = _as_node_tensor(values[0], batch_eng.batch_size, batch_eng.device, dtype=torch.bool)
    for item in values[1:]:
        out = out & _as_node_tensor(item, batch_eng.batch_size, batch_eng.device, dtype=torch.bool)
    return out


def _gpu_or(*values: Any) -> Any:
    if not any(isinstance(v, torch.Tensor) for v in values):
        result = values[0]
        for item in values[1:]:
            if result:
                return result
            result = item
        return result
    batch_eng = engine.get()
    out = _as_node_tensor(values[0], batch_eng.batch_size, batch_eng.device, dtype=torch.bool)
    for item in values[1:]:
        out = out | _as_node_tensor(item, batch_eng.batch_size, batch_eng.device, dtype=torch.bool)
    return out


def _gpu_max(*args: Any, **kwargs: Any) -> Any:
    if kwargs or len(args) == 1 or not any(isinstance(a, torch.Tensor) for a in args):
        return builtins.max(*args, **kwargs)
    batch_eng = engine.get()
    acc = _as_node_tensor(args[0], batch_eng.batch_size, batch_eng.device)
    for item in args[1:]:
        rhs = _as_node_tensor(item, batch_eng.batch_size, batch_eng.device)
        acc, rhs = _promote_pair(acc, rhs)
        acc = torch.maximum(acc, rhs)
    return acc


def _gpu_min(*args: Any, **kwargs: Any) -> Any:
    if kwargs or len(args) == 1 or not any(isinstance(a, torch.Tensor) for a in args):
        return builtins.min(*args, **kwargs)
    batch_eng = engine.get()
    acc = _as_node_tensor(args[0], batch_eng.batch_size, batch_eng.device)
    for item in args[1:]:
        rhs = _as_node_tensor(item, batch_eng.batch_size, batch_eng.device)
        acc, rhs = _promote_pair(acc, rhs)
        acc = torch.minimum(acc, rhs)
    return acc


_gpu_max._gpu_kind = "max"  # type: ignore[attr-defined]  # pylint: disable=protected-access
_gpu_min._gpu_kind = "min"  # type: ignore[attr-defined]  # pylint: disable=protected-access


def _gpu_compute_timer_step(
    remaining: Any, elapsed: Any, duration: float, periodic: bool
) -> tuple[Any, Any]:
    time_left = remaining - elapsed
    clamped = _gpu_max(0.0, time_left)
    if periodic:
        dur_t = torch.full_like(clamped, builtins.float(duration))
        return torch.where(time_left <= 0.0, dur_t, clamped), time_left
    return clamped, time_left


def merge_branch_values(  # pylint: disable=too-many-return-statements
    cond: torch.Tensor, left: Any, right: Any, batch_size: int, device: torch.device
) -> Any:
    """Combine values produced by ``left`` (where ``cond``) and ``right`` (where ``~cond``)."""
    if left is right or bool(cond.all().item()):
        return left
    if not bool(cond.any().item()):
        return right
    if isinstance(left, tuple) and isinstance(right, tuple) and len(left) == len(right):
        return tuple(
            merge_branch_values(cond, lv, rv, batch_size, device) for lv, rv in zip(left, right)
        )
    if isinstance(left, BatchedNeighborhoodField) and isinstance(right, BatchedNeighborhoodField):
        loc = merge_branch_values(cond, left.local_val, right.local_val, batch_size, device)
        edge_cond = cond[left.edges.local_receiver]
        edg_a, edg_b = _promote_pair(left.edge_val, right.edge_val)
        edg = torch.where(edge_cond.unsqueeze(-1) if edg_a.ndim > 1 else edge_cond, edg_a, edg_b)
        val = torch.where(edge_cond, left.edge_valid, right.edge_valid)
        return BatchedNeighborhoodField(
            left.edges, loc, edg, val, has_self=left.has_self and right.has_self
        )
    if left is None:
        r_t = _as_node_tensor(right, batch_size, device)
        sentinel = math.nan if r_t.dtype.is_floating_point else -1
        mask = cond.unsqueeze(-1) if r_t.ndim > 1 else cond
        return torch.where(mask, torch.full_like(r_t, sentinel), r_t)
    if right is None:
        l_t = _as_node_tensor(left, batch_size, device)
        sentinel = math.nan if l_t.dtype.is_floating_point else -1
        mask = cond.unsqueeze(-1) if l_t.ndim > 1 else cond
        return torch.where(mask, l_t, torch.full_like(l_t, sentinel))
    l_t, r_t = _promote_pair(
        _as_node_tensor(left, batch_size, device),
        _as_node_tensor(right, batch_size, device),
    )
    mask = cond.unsqueeze(-1) if l_t.ndim > 1 else cond
    return torch.where(mask, l_t, r_t)


def _gpu_choose(condition: Any, if_true: Callable[[], Any], if_false: Callable[[], Any]) -> Any:
    if isinstance(condition, bool):
        return if_true() if condition else if_false()
    batch_eng = engine.get()
    cond = _as_node_tensor(condition, batch_eng.batch_size, batch_eng.device, dtype=torch.bool)
    if bool(cond.all().item()):
        return if_true()
    if not bool(cond.any().item()):
        return if_false()
    return merge_branch_values(cond, if_true(), if_false(), batch_eng.batch_size, batch_eng.device)


def _gpu_remember(init: Any) -> tuple[Any, Callable[[Any], Any]]:
    return engine.get().remember_state(init)


def _gpu_remember_and_evolve(init: Any, evolve_fn: Callable[[Any], Any]) -> Any:
    return engine.get().remember_and_evolve_state(init, evolve_fn)


def _gpu_if_stmt(  # pylint: disable=too-many-arguments
    condition: Any,
    state_vars: tuple[Any, ...],
    left_fn: Callable[..., tuple[bool, Any, tuple[Any, ...]]],
    right_fn: Callable[..., tuple[bool, Any, tuple[Any, ...]]],
    after_fn: Callable[..., tuple[bool, Any, tuple[Any, ...]]] | None,
) -> tuple[bool, Any, tuple[Any, ...]]:
    return engine.get().execute_if_statement(
        condition, state_vars, left_fn, right_fn, after_fn
    )


def _empty_args() -> ast.arguments:
    return ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])


def _thunk(expr: ast.expr) -> ast.Lambda:
    return ast.copy_location(ast.Lambda(args=_empty_args(), body=expr), expr)


def _assigned_locals(statements: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        for child in ast.walk(stmt):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                names.add(child.id)
    return names


class _StripAnnotations(ast.NodeTransformer):
    """Strip variable, argument, and return annotations before compiling for GPU."""

    # pylint: disable=invalid-name,missing-function-docstring
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.returns = None
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.annotation = None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.stmt | None:
        if node.value is None:
            return None
        assign = ast.Assign(targets=[node.target], value=node.value)
        return self.visit(ast.copy_location(assign, node))


def _is_len_data_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Name) or node.func.id != "len":
        return False
    if len(node.args) != 1 or node.keywords:
        return False
    arg = node.args[0]
    return isinstance(arg, ast.Attribute) and arg.attr == "data"


class _GpuExprTransformer(ast.NodeTransformer):
    # pylint: disable=invalid-name,missing-function-docstring

    def visit_IfExp(self, node: ast.IfExp) -> ast.expr:
        self.generic_visit(node)
        branches = (node.body, node.orelse)
        if any(map(_bound_to_its_scope, branches)):
            return node
        helper = "_aligned_branch" if any(map(_calls_anything, branches)) else "_gpu_choose"
        call = ast.Call(
            func=ast.Name(id=helper, ctx=ast.Load()),
            args=[node.test, _thunk(node.body), _thunk(node.orelse)],
            keywords=[],
        )
        return ast.copy_location(call, node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            call = ast.Call(
                func=ast.Name(id="_gpu_not", ctx=ast.Load()), args=[node.operand], keywords=[]
            )
            return ast.copy_location(call, node)
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
        self.generic_visit(node)
        helper = "_gpu_and" if isinstance(node.op, ast.And) else "_gpu_or"
        return ast.copy_location(
            ast.Call(func=ast.Name(id=helper, ctx=ast.Load()), args=node.values, keywords=[]),
            node,
        )

    def visit_Call(self, node: ast.Call) -> ast.expr:
        if _is_len_data_call(node):
            attr: ast.Attribute = node.args[0]  # type: ignore[assignment]
            target = self.visit(attr.value)
            call = ast.Call(
                func=ast.Name(id="_gpu_len_attr", ctx=ast.Load()), args=[target], keywords=[]
            )
            return ast.copy_location(call, node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in ("float", "int", "bool")
            and len(node.args) == 1
            and not node.keywords
        ):
            arg = self.visit(node.args[0])
            call = ast.Call(
                func=ast.Name(id=f"_gpu_{node.func.id}", ctx=ast.Load()), args=[arg], keywords=[]
            )
            return ast.copy_location(call, node)
        self.generic_visit(node)
        return node


def _vars_tuple(names: list[str], ctx: ast.expr_context) -> ast.Tuple:
    return ast.Tuple(elts=[ast.Name(id=name, ctx=ctx) for name in names], ctx=ctx)


def _helper_func_def(
    name: str,
    statements: list[ast.stmt],
    scope_locals: set[str],
    shared: list[str],
    counter_box: list[int],
) -> ast.FunctionDef:
    body = _rewrite_block(statements, scope_locals, counter_box, helper_shared=shared)
    fallthrough = ast.Tuple(
        elts=[
            ast.Constant(value=False),
            ast.Constant(value=None),
            _vars_tuple(shared, ast.Load()),
        ],
        ctx=ast.Load(),
    )
    body.append(ast.Return(value=fallthrough))
    args = ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg=var) for var in shared],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[],
    )
    return ast.FunctionDef(
        name=name, args=args, body=body, decorator_list=[], returns=None, type_params=[]
    )


def _rewrite_if_stmt(  # pylint: disable=too-many-locals
    stmt: ast.If,
    rest: list[ast.stmt],
    scope_locals: set[str],
    counter_box: list[int],
    *,
    helper_shared: list[str] | None,
) -> list[ast.stmt]:
    counter_box[0] += 1
    uid = counter_box[0]
    test_expr = _GpuExprTransformer().visit(stmt.test)
    parent_shared = set(helper_shared or ())
    shared = sorted(
        scope_locals
        & (
            parent_shared
            | _assigned_locals(stmt.body)
            | _assigned_locals(stmt.orelse)
            | _assigned_locals(rest)
        )
    )

    left_name, right_name, after_name = (
        f"__gpu_left_{uid}__",
        f"__gpu_right_{uid}__",
        f"__gpu_after_{uid}__",
    )
    right_stmts = stmt.orelse if stmt.orelse else [ast.Pass()]
    out: list[ast.stmt] = [
        _helper_func_def(left_name, stmt.body, scope_locals, shared, counter_box),
        _helper_func_def(right_name, right_stmts, scope_locals, shared, counter_box),
    ]
    if rest:
        out.append(_helper_func_def(after_name, rest, scope_locals, shared, counter_box))
        after_arg: ast.expr = ast.Name(id=after_name, ctx=ast.Load())
    else:
        after_arg = ast.Constant(value=None)

    call = ast.Call(
        func=ast.Name(id="_gpu_if_stmt", ctx=ast.Load()),
        args=[
            test_expr,
            _vars_tuple(shared, ast.Load()),
            ast.Name(id=left_name, ctx=ast.Load()),
            ast.Name(id=right_name, ctx=ast.Load()),
            after_arg,
        ],
        keywords=[],
    )
    done_var, val_var, state_var = (
        f"__gpu_done_{uid}__",
        f"__gpu_val_{uid}__",
        f"__gpu_st_{uid}__",
    )
    out.append(
        ast.Assign(
            targets=[
                ast.Tuple(
                    elts=[
                        ast.Name(id=done_var, ctx=ast.Store()),
                        ast.Name(id=val_var, ctx=ast.Store()),
                        ast.Name(id=state_var, ctx=ast.Store()),
                    ],
                    ctx=ast.Store(),
                )
            ],
            value=call,
        )
    )
    if shared:
        out.append(
            ast.Assign(
                targets=[_vars_tuple(shared, ast.Store())],
                value=ast.Name(id=state_var, ctx=ast.Load()),
            )
        )
    if helper_shared is not None:
        ret_tuple = ast.Tuple(
            elts=[
                ast.Name(id=done_var, ctx=ast.Load()),
                ast.Name(id=val_var, ctx=ast.Load()),
                _vars_tuple(helper_shared, ast.Load()),
            ],
            ctx=ast.Load(),
        )
        out.append(ast.copy_location(ast.Return(value=ret_tuple), stmt))
        return out

    out.append(
        ast.If(
            test=ast.Name(id=done_var, ctx=ast.Load()),
            body=[ast.Return(value=ast.Name(id=val_var, ctx=ast.Load()))],
            orelse=[],
        )
    )
    return out


def _rewrite_block(
    statements: list[ast.stmt],
    scope_locals: set[str],
    counter_box: list[int],
    *,
    helper_shared: list[str] | None,
) -> list[ast.stmt]:
    expr_tx = _GpuExprTransformer()
    out: list[ast.stmt] = []
    for idx, stmt in enumerate(statements):
        if isinstance(stmt, ast.Return):
            val = ast.Constant(value=None) if stmt.value is None else expr_tx.visit(stmt.value)
            ret_val: ast.expr = (
                ast.Tuple(
                    elts=[
                        ast.Constant(value=True),
                        val,
                        _vars_tuple(helper_shared, ast.Load()),
                    ],
                    ctx=ast.Load(),
                )
                if helper_shared is not None
                else val
            )
            out.append(ast.copy_location(ast.Return(value=ret_val), stmt))
            return out
        if isinstance(stmt, ast.If):
            out.extend(
                _rewrite_if_stmt(
                    stmt,
                    statements[idx + 1:],
                    scope_locals,
                    counter_box,
                    helper_shared=helper_shared,
                )
            )
            return out
        out.append(expr_tx.visit(stmt))
    return out


_GPU_HELPERS: dict[str, Any] = {
    "align_left": align_left,
    "align_right": align_right,
    "_aligned_branch": _aligned_branch,
    "_gpu_choose": _gpu_choose,
    "_gpu_if_stmt": _gpu_if_stmt,
    "_gpu_not": _gpu_not,
    "_gpu_and": _gpu_and,
    "_gpu_or": _gpu_or,
    "_gpu_len_attr": _gpu_len_attr,
    "_gpu_float": _gpu_float,
    "_gpu_int": _gpu_int,
    "_gpu_bool": _gpu_bool,
    "max": _gpu_max,
    "min": _gpu_min,
    "remember": _gpu_remember,
    "remember_and_evolve": _gpu_remember_and_evolve,
    "_compute_timer_step": _gpu_compute_timer_step,
}


def _extract_defaults(original: Callable[..., Any], func_def: ast.FunctionDef) -> dict[str, Any]:
    defaults = {f"__gpu_def_{idx}": val for idx, val in enumerate(original.__defaults__ or ())}
    for kw_name, kw_val in (original.__kwdefaults__ or {}).items():
        defaults[f"__gpu_kwdef_{kw_name}"] = kw_val
    func_def.args.defaults = [
        ast.Name(id=f"__gpu_def_{idx}", ctx=ast.Load())
        for idx in range(len(func_def.args.defaults))
    ]
    func_def.args.kw_defaults = [
        None if d is None else ast.Name(id=f"__gpu_kwdef_{arg.arg}", ctx=ast.Load())
        for arg, d in zip(func_def.args.kwonlyargs, func_def.args.kw_defaults)
    ]
    return defaults


def _compile_scoped_function(
    func_def: ast.FunctionDef, original: Callable[..., Any], cells: dict[str, types.CellType]
) -> Callable[..., Any]:
    code = original.__code__
    factory_name, scope_name = "__gpu_factory__", "__gpu_scope__"
    factory_def = ast.FunctionDef(
        name=factory_name,
        args=_empty_args(),
        body=[func_def, ast.Return(value=ast.Name(id=func_def.name, ctx=ast.Load()))],
        decorator_list=[],
        returns=None,
        type_params=[],
    )
    scope_body: list[ast.stmt] = [
        ast.Assign(
            targets=[ast.Name(id=name, ctx=ast.Store()) for name in cells],
            value=ast.Constant(value=None),
        ),
        factory_def,
        ast.Return(value=ast.Name(id=factory_name, ctx=ast.Load())),
    ]
    scope_def = ast.FunctionDef(
        name=scope_name,
        args=_empty_args(),
        body=scope_body,
        decorator_list=[],
        returns=None,
        type_params=[],
    )
    mod = ast.fix_missing_locations(ast.Module(body=[scope_def], type_ignores=[]))
    compiled_mod = compile(mod, filename=code.co_filename, mode="exec")
    scope_code = next(
        c
        for c in compiled_mod.co_consts
        if isinstance(c, types.CodeType) and c.co_name == scope_name
    )
    factory_code = next(
        c
        for c in scope_code.co_consts
        if isinstance(c, types.CodeType) and c.co_name == factory_name
    )
    closure = tuple(cells[name] for name in factory_code.co_freevars)
    factory_fn = types.FunctionType(factory_code, original.__globals__, factory_name, None, closure)
    return functools.wraps(original)(factory_fn())


def compile_for_gpu(func: Callable[..., Any]) -> Callable[..., Any]:
    """Compile an ``@aggregate`` function's original AST once for SPMD tensor execution."""
    original = inspect.unwrap(func)
    code = original.__code__
    cached = _COMPILED_CACHE.get(code)
    if cached is not None:
        return cached

    func_def = ast.parse(textwrap.dedent(inspect.getsource(original))).body[0]
    _drop_applied_decorators(func_def)
    func_def = _StripAnnotations().visit(func_def)
    owner = _owner_class(original)
    if owner is not None and owner.lstrip("_"):
        _PrivateNames(owner).generic_visit(func_def)

    params = {
        arg.arg
        for arg in (*func_def.args.posonlyargs, *func_def.args.args, *func_def.args.kwonlyargs)
    }
    assigned = _assigned_locals(func_def.body)
    rewritten_body = _rewrite_block(func_def.body, params | assigned, [0], helper_shared=None)
    init_undef = sorted(assigned - params)
    if init_undef:
        rewritten_body.insert(
            0,
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store()) for name in init_undef],
                value=ast.Constant(value=None),
            ),
        )
    func_def.body = rewritten_body

    defaults = _extract_defaults(original, func_def)
    cells = {name: types.CellType(val) for name, val in {**_GPU_HELPERS, **defaults}.items()}
    cells.update(zip(code.co_freevars, original.__closure__ or ()))
    compiled_fn = _compile_scoped_function(func_def, original, cells)
    _COMPILED_CACHE[code] = compiled_fn
    return compiled_fn
