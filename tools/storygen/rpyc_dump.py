"""Recursively dump a Ren'Py .rpyc AST using the permissive loader."""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from rpyc_probe import load_rpyc, Generic  # noqa: E402

SKIP = {"filename", "linenumber", "col_offset", "name_version", "name_serial"}


def slots_of(o):
    """Merged attribute view.

    Ren'Py AST nodes pickle their state as (dict_state, slots_state); both
    halves must be merged or attributes go missing.
    """
    if not hasattr(o, "__dict__"):
        return {}
    d = dict(o.__dict__)
    d.pop("_args", None)
    s = d.pop("_slots", None)
    if isinstance(s, dict):
        d.update(s)
    return d


def is_node(o):
    return hasattr(o, "__dict__") and (isinstance(o, Generic) or "_slots" in o.__dict__)


def dump(o, ind=0, depth=8, seen=None):
    pad = "  " * ind
    if seen is None:
        seen = set()
    n = type(o).__name__
    if is_node(o):
        s = slots_of(o)
        interesting = {k: v for k, v in s.items() if k not in SKIP}
        simple = {k: v for k, v in interesting.items() if not isinstance(v, (list, dict)) and not is_node(v)}
        print("%s%s %s" % (pad, n, simple))
        if depth <= 0:
            return
        for k, v in interesting.items():
            if isinstance(v, list) and v:
                print("%s  .%s:" % (pad, k))
                for c in v:
                    dump(c, ind + 2, depth - 1, seen)
            elif is_node(v):
                print("%s  .%s:" % (pad, k))
                dump(v, ind + 2, depth - 1, seen)
    elif isinstance(o, list):
        for c in o:
            dump(c, ind, depth, seen)
    else:
        print("%s%r" % (pad, o))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rpyc")
    ap.add_argument("--depth", type=int, default=8)
    ap.add_argument("--only", help="only dump nodes whose type name contains this")
    args = ap.parse_args()

    data, stmts = load_rpyc(args.rpyc)
    print("=== %s : %d top-level stmts ===" % (args.rpyc, len(stmts)))
    for s in stmts:
        if args.only and args.only.lower() not in type(s).__name__.lower():
            continue
        dump(s, 0, args.depth)
        print("-" * 60)


if __name__ == "__main__":
    main()
