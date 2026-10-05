"""在原作全部 .rpyc 里彻底搜关键词：把每个节点子树里的字符串和 PyExpr 源码都翻出来。

只收 top-level 的几个字符串槽是不够的——screen 里的
`textbutton "黑丝" action SetField(persistent, "stockings_color", 2)`
是挂在 SLDisplayable 的 positional/parsed 里的，会被漏掉。

用法: python tools/scan_original.py stockings
"""

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rpyc_dump import slots_of, is_node  # noqa: E402
from rpyc_probe import load_rpyc  # noqa: E402

SKIP_KEYS = {"filename", "name_version", "name_serial"}


def strings_in(o, out, seen, depth=0):
    """把一个节点子树里所有像源码/字符串的东西收集起来。"""
    if depth > 12 or id(o) in seen:
        return
    if isinstance(o, str):
        out.append(o)
        return
    if isinstance(o, (int, float, bool)) or o is None:
        return
    if is_node(o) or hasattr(o, "__dict__"):
        seen.add(id(o))
        args = o.__dict__.get("_args")
        if args:
            for a in args:
                strings_in(a, out, seen, depth + 1)
        state = o.__dict__.get("_state")
        if isinstance(state, tuple):
            for a in state:
                strings_in(a, out, seen, depth + 1)
        for k, v in slots_of(o).items():
            if k in SKIP_KEYS:
                continue
            strings_in(v, out, seen, depth + 1)
    elif isinstance(o, (list, tuple)):
        seen.add(id(o))
        for v in o:
            strings_in(v, out, seen, depth + 1)
    elif isinstance(o, dict):
        seen.add(id(o))
        for v in o.values():
            strings_in(v, out, seen, depth + 1)


def main():
    key = (sys.argv[1] if len(sys.argv) > 1 else "stocking").lower()
    root = sys.argv[2] if len(sys.argv) > 2 else "原始解包/scripts_rpa"

    total = 0
    for f in sorted(glob.glob(os.path.join(root, "**", "*.rpyc"), recursive=True)):
        try:
            _d, stmts = load_rpyc(f)
        except Exception:
            continue
        found = []
        for st in stmts:
            bag = []
            strings_in(st, bag, set())
            for s in bag:
                if key in s.lower() and len(s) < 400:
                    found.append(s)
        if found:
            rel = f.replace(root, "").lstrip("\\/")
            uniq = []
            for s in found:
                if s not in uniq:
                    uniq.append(s)
            print("=== %s  (%d 条去重后)" % (rel, len(uniq)))
            for s in uniq[:12]:
                print("   " + re.sub(r"\s+", " ", s)[:150])
            total += len(uniq)
    print("\n合计 %d 条" % total)


if __name__ == "__main__":
    main()
