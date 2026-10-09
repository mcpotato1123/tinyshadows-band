"""比对两个 galgod-band 版本的同一个文件，按「变更块」给出紧凑摘要。

基线升级时先跑这个，一眼看清上游改了什么，再决定哪些补丁锚点要更新。

用法:
  python tools/galgod_diff.py <文件相对路径> [旧版本目录] [新版本目录]
  python tools/galgod_diff.py src/pages/game/game.ux galgod-band-23 galgod-band-252
  python tools/galgod_diff.py --files galgod-band-23 galgod-band-252     # 只列各文件差异行数
"""

import difflib
import io
import os
import sys


def read(p):
    return io.open(p, encoding="utf-8").read().splitlines()


def summary(a_path, b_path, max_blocks=40, ctx=2):
    a, b = read(a_path), read(b_path)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
    print("  %s: %d 行 -> %d 行，%d 个变更块"
          % (os.path.basename(a_path), len(a), len(b), len(ops)))
    print()
    for n, (tag, i1, i2, j1, j2) in enumerate(ops[:max_blocks]):
        print("  --- [%d] %s  旧[%d,%d) -> 新[%d,%d)" % (n + 1, tag, i1, i2, j1, j2))
        for l in a[max(0, i1 - ctx):i1]:
            print("        %s" % l[:104])
        for l in a[i1:i2][:8]:
            print("      - %s" % l[:104])
        for l in b[j1:j2][:8]:
            print("      + %s" % l[:104])
        if (i2 - i1) > 8 or (j2 - j1) > 8:
            print("      ...")
        print()
    if len(ops) > max_blocks:
        print("  （还有 %d 个块没显示）" % (len(ops) - max_blocks))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args and args[0] == "--files":
        old, new = args[1], args[2]
        rows = []
        for dp, _d, fs in os.walk(os.path.join(new, "src")):
            for f in fs:
                if os.path.splitext(f)[1] not in (".ux", ".js", ".json", ".txt"):
                    continue
                p2 = os.path.join(dp, f)
                rel = os.path.relpath(p2, new)
                p1 = os.path.join(old, rel)
                if not os.path.exists(p1):
                    rows.append((rel, -1, "新增"))
                    continue
                if open(p1, "rb").read() == open(p2, "rb").read():
                    continue
                a, b = read(p1), read(p2)
                sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
                ch = sum(max(i2 - i1, j2 - j1)
                         for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
                rows.append((rel, ch, "%d -> %d 行" % (len(a), len(b))))
        rows.sort(key=lambda r: -r[1])
        print("%-42s %8s  %s" % ("文件", "变更行", "行数"))
        for rel, ch, note in rows:
            print("%-42s %8s  %s" % (rel, ch if ch >= 0 else "新", note))
        return
    rel = args[0] if args else "src/pages/game/game.ux"
    old = args[1] if len(args) > 1 else "galgod-band-23"
    new = args[2] if len(args) > 2 else "galgod-band-252"
    print("== %s ==  %s -> %s" % (rel, old, new))
    summary(os.path.join(old, rel), os.path.join(new, rel))


if __name__ == "__main__":
    main()
