"""Helpers to recover source text from Ren'Py PyExpr/PyCode pickle objects."""

import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from rpyc_dump import slots_of, is_node  # noqa: E402


def expr_text(o):
    """Best-effort recovery of the Python source string from a PyExpr/PyCode."""
    if o is None:
        return None
    if isinstance(o, str):
        return o

    args = o.__dict__.get("_args") if hasattr(o, "__dict__") else None
    if args:
        for a in args:
            if isinstance(a, str):
                return a

    state = o.__dict__.get("_state") if hasattr(o, "__dict__") else None
    if isinstance(state, tuple):
        for a in state:
            if is_node(a) or hasattr(a, "__dict__"):
                t = expr_text(a)
                if t is not None:
                    return t
            elif isinstance(a, str) and len(a) > 1:
                return a
    return None


def walk(o, want, acc=None, seen=None):
    """Collect every node whose type name is in `want`."""
    if acc is None:
        acc = []
    if seen is None:
        seen = set()
    if id(o) in seen:
        return acc
    if is_node(o):
        seen.add(id(o))
        if type(o).__name__ in want:
            acc.append(o)
        for v in slots_of(o).values():
            walk(v, want, acc, seen)
    elif isinstance(o, (list, tuple)):
        seen.add(id(o))
        for v in o:
            walk(v, want, acc, seen)
    elif isinstance(o, dict):
        seen.add(id(o))
        for v in o.values():
            walk(v, want, acc, seen)
    return acc
