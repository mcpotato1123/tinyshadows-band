"""把 Ren'Py 的 .rpyc 脚本导出成手环 galgame 引擎的剧本数据（JS）。

和之前导出成纯文本不同，这里保留 Menu 的分支结构，并把每个分支
拍平成 label + goto，这样手环上的解释器只需要一个平坦的指令数组。

指令格式：
  {bg:'bg_x'} / {bg:'black'}      切换背景
  {cg:'cg2'}                      全屏 CG
  {sp:'smile'} / {sp:'shy skin_blush'} / {sp:null}   立绘
  {say:'...'} / {who:'林默', say:'...'}              对白
  {choice:[{t:'选项', go:'L0'}]}   选项
  {label:'L0'} / {goto:'L0'}       跳转
  {vib:'short'} {shake:1} {wait:400} {end:1}
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rpyc_probe import load_rpyc  # noqa: E402
from rpyc_dump import slots_of  # noqa: E402
from extract_script import CHARACTERS, clean, expr_text  # noqa: E402

TAG_RE = re.compile(r"\{[^}]*\}")

# 原作里的分支条件都是 `变量 == 常量`（可 and 连接）这种简单形式，
# 在构建期解析成结构化子句，运行期就不需要在手环上 eval。
COND_RE = re.compile(r"^(?:persistent\.)?([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(.+)$")
ASSIGN_RE = re.compile(r"^(?:persistent\.)?([A-Za-z_]\w*)\s*=\s*(.+)$")


def _literal(val):
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        pass
    if val in ("True", "true"):
        return 1
    if val in ("False", "false"):
        return 0
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
        return val[1:-1]
    return None


def parse_cond(expr):
    """'persistent.stockings_color == 0' -> [{'n','o','v'}]
    'first_choice == 0 and second_choice == 0' -> 两条子句
    'True' -> []（恒真）。无法解析返回 None。"""
    s = (expr or "").strip()
    if s in ("True", "true", "1"):
        return []
    if s in ("False", "false", "0"):
        return [{"n": "__never__", "o": "==", "v": 1}]
    out = []
    for part in re.split(r"\s+and\s+", s):
        m = COND_RE.match(part.strip())
        if not m:
            return None
        v = _literal(m.group(3))
        if v is None:
            return None
        out.append({"n": m.group(1), "o": m.group(2), "v": v})
    return out


def parse_assign(src):
    """把 `$ first_choice = 0` 这类简单赋值解析出来，其余代码忽略。"""
    if not src:
        return []
    out = []
    for stmt in re.split(r"[;\n]", src):
        m = ASSIGN_RE.match(stmt.strip())
        if not m:
            continue
        v = _literal(m.group(2))
        if v is not None:
            out.append((m.group(1), v))
    return out


def kind_of_image(name):
    if not name:
        return None
    n = name.split()[0]
    if n.startswith("syq_"):
        return "sprite"
    if n.startswith("bg_"):
        return "bg"
    if n == "black":
        return "black"
    if n.lower().startswith("sd") or n.startswith("cg") or n == "chunbai":
        return "cg"
    return "cg"


def strip_prefix(name, kind):
    if kind == "bg" and name.startswith("bg_"):
        return name
    return name


class Exporter(object):
    def __init__(self, prefix, resolver, skip_labels=()):
        self.out = []
        self.prefix = prefix
        self.resolve_sprite = resolver
        self.skip = set(skip_labels)
        self.label_seq = 0
        self.menu_seq = 0
        self.if_seq = 0

    def emit(self, cmd):
        self.out.append(cmd)

    def new_label(self, hint):
        self.label_seq += 1
        return "%s_%d" % (hint, self.label_seq)

    def walk(self, node):
        t = type(node).__name__
        sl = slots_of(node)

        if t == "Label":
            name = sl.get("_name")
            if name in self.skip:
                return
            if not str(name).startswith("_call_achievement"):
                self.emit({"label": name})
            for c in (sl.get("block") or []):
                self.walk(c)
            return

        if t in ("Say", "TranslateSay"):
            who = sl.get("who")
            text = clean(sl.get("what")) or ""
            if not text.strip():
                return
            if who:
                self.emit({"who": CHARACTERS.get(who, who), "say": text})
            else:
                self.emit({"say": text})
            return

        if t in ("Scene", "Show"):
            nm = None
            im = sl.get("imspec")
            if im and isinstance(im[0], (tuple, list)):
                nm = " ".join(str(x) for x in im[0])
            elif im:
                nm = str(im[0])
            k = kind_of_image(nm)
            cmd = None
            if k == "sprite":
                key = self.resolve_sprite(nm[len("syq_"):].strip())
                if key:
                    cmd = {"sp": key}
            elif k == "black":
                cmd = {"bg": "black"}
            elif k == "bg":
                cmd = {"bg": nm}
            elif k == "cg":
                cmd = {"cg": nm}
            if cmd is not None:
                # Scene 和 Show 在 Ren'Py 里语义不同：scene 会**清空整个画面层**
                # （背景之外的立绘、CG 一起清），show 只是往栈上追加。
                # 这个标记让下游知道要不要清立绘。
                if t == "Scene":
                    cmd["scene"] = 1
                self.emit(cmd)
            return

        if t == "Hide":
            self.emit({"sp": None})
            return

        if t == "Menu":
            items = sl.get("items") or []
            if not items:
                return
            self.menu_seq += 1
            end = "%s_M%d_end" % (self.prefix, self.menu_seq)
            opts = []
            branches = []
            for i, item in enumerate(items):
                lab = "%s_M%d_%d" % (self.prefix, self.menu_seq, i)
                opts.append({"t": clean(item[0]) or "……", "go": lab})
                branches.append((lab, item[2] or []))
            self.emit({"choice": opts})
            self.emit({"goto": end})
            for lab, blk in branches:
                self.emit({"label": lab})
                for c in blk:
                    self.walk(c)
                self.emit({"goto": end})
            self.emit({"label": end})
            return

        if t == "If":
            entries = sl.get("entries") or []
            if not entries:
                return
            self.if_seq += 1
            end = "%s_IF%d_end" % (self.prefix, self.if_seq)
            labs = []
            for i, entry in enumerate(entries):
                cond = expr_text(entry[0])
                clauses = parse_cond(cond)
                lab = "%s_IF%d_%d" % (self.prefix, self.if_seq, i)
                labs.append((lab, clauses, entry[-1] or []))
                if clauses is None:
                    continue
                self.emit({"gotoIf": {"c": clauses, "to": lab}})
            self.emit({"goto": end})
            for lab, clauses, blk in labs:
                if clauses is None:
                    continue
                self.emit({"label": lab})
                for c in blk:
                    self.walk(c)
                self.emit({"goto": end})
            self.emit({"label": end})
            return

        if t in ("Python", "PyCode"):
            src = sl.get("code")
            if src is None:
                src = node
            text = expr_text(src)
            sets = parse_assign(text)
            if sets:
                self.emit({"set": dict(sets)})
            return

        if t == "Jump":
            self.emit({"goto": sl.get("target")})
            return

        if t in ("Call", "Return", "Pass", "Init", "Define", "Default",
                 "Python", "PyCode", "Image", "Transform", "Style", "Screen",
                 "UserStatement", "With"):
            if t == "Return":
                self.emit({"end": 1})
            return

        blk = sl.get("block")
        if isinstance(blk, list):
            for c in blk:
                self.walk(c)


def js_escape(s):
    return (s.replace("\\", "\\\\").replace("'", "\\'")
             .replace("\n", "\\n").replace("\r", ""))


def to_js(cmds):
    lines = ["export default ["]
    for c in cmds:
        if "say" in c and "who" in c:
            lines.append("  { who: '%s', say: '%s' },"
                         % (js_escape(c["who"]), js_escape(c["say"])))
        elif "say" in c:
            lines.append("  { say: '%s' }," % js_escape(c["say"]))
        elif "choice" in c:
            items = ", ".join("{ t: '%s', go: '%s' }"
                              % (js_escape(o["t"]), o["go"]) for o in c["choice"])
            lines.append("  { choice: [%s] }," % items)
        elif "sp" in c:
            lines.append("  { sp: %s }," % ("null" if c["sp"] is None
                                            else "'%s'" % js_escape(c["sp"])))
        elif "bg" in c:
            lines.append("  { bg: '%s' }," % js_escape(c["bg"]))
        elif "cg" in c:
            lines.append("  { cg: '%s' }," % js_escape(c["cg"]))
        elif "label" in c:
            lines.append("  { label: '%s' }," % js_escape(c["label"]))
        elif "goto" in c:
            lines.append("  { goto: '%s' }," % js_escape(c["goto"]))
        elif "gotoIf" in c:
            g = c["gotoIf"]
            cl = ", ".join("{ n: '%s', o: '%s', v: %s }"
                           % (js_escape(x["n"]), x["o"],
                              ("'%s'" % js_escape(x["v"]))
                              if isinstance(x["v"], str) else x["v"])
                           for x in g["c"])
            lines.append("  { gotoIf: { c: [%s], to: '%s' } },"
                         % (cl, js_escape(g["to"])))
        elif "set" in c:
            body = ", ".join("%s: %s" % (k, ("'%s'" % js_escape(v))
                                         if isinstance(v, str) else v)
                             for k, v in c["set"].items())
            lines.append("  { set: { %s } }," % body)
        else:
            lines.append("  %s," % json.dumps(c, ensure_ascii=False))
    lines.append("]")
    return "\n".join(lines) + "\n"


def make_resolver(rpyc_path):
    """把剧本里的立绘属性解析成确定的图片文件名（构建期做完，引擎只管加载）。"""
    from compose_sprites import parse_layeredimage, resolve  # noqa: E402

    _name, group_order, groups = parse_layeredimage(rpyc_path)
    order = ("clothes_posture", "skin", "feet", "face")

    def resolve_attrs(s):
        attrs = s.split()
        if not (set(attrs) & POSTURES):
            attrs = attrs + ["clothes1_front"]
        chosen, _full = resolve(groups, group_order, attrs)
        if chosen is None:
            return None
        return "_".join(chosen[g].attr for g in order if g in chosen)

    return resolve_attrs


POSTURES = {"clothes1_front", "clothes1_side", "clothes2_front", "clothes2_side"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="原始解包/scripts_rpa/scripts/content")
    ap.add_argument("--rpyc", default="原始解包/scripts_rpa/scripts/roles/syq.rpyc")
    ap.add_argument("--out", default="band-galgame/src/data")
    ap.add_argument("--chapters", nargs="*",
                    default=["script", "part2", "part3", "part4", "end", "extra1"])
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    resolver = make_resolver(args.rpyc)

    index = []
    all_labels, all_gotos = set(), []
    for ch in args.chapters:
        path = os.path.join(args.src, ch + ".rpyc")
        if not os.path.exists(path):
            continue
        _d, stmts = load_rpyc(path)
        ex = Exporter(prefix=ch, resolver=resolver, skip_labels={"start"})
        for i, st in enumerate(stmts):
            # 每个 .rpyc 末尾都有一条隐式 return（文件结束），它不是剧情结局，
            # 否则第一章跑完就会直接停在结束画面。
            if type(st).__name__ == "Return" and i == len(stmts) - 1:
                continue
            ex.walk(st)

        cmds = ex.out
        # goto 之后紧跟的 return 是死代码，去掉更干净
        cleaned = []
        for c in cmds:
            if "end" in c and cleaned and "goto" in cleaned[-1]:
                continue
            cleaned.append(c)
        cmds = cleaned
        for c in cmds:
            if "label" in c:
                all_labels.add(c["label"])
            if "goto" in c:
                all_gotos.append((ch, c["goto"]))

        entry = "part1" if ch == "script" else None
        if entry is None:
            for c in cmds:
                if "label" in c:
                    entry = c["label"]
                    break

        js = "// 自动生成，请勿手改。来源：scripts/content/%s.rpyc\n" % ch
        js += "// 共 %d 条指令，入口 label: %s\n" % (len(cmds), entry)
        js += to_js(cmds)
        with open(os.path.join(args.out, "%s.js" % ch), "w", encoding="utf-8") as f:
            f.write(js)

        n_say = sum(1 for c in cmds if "say" in c)
        n_ch = sum(1 for c in cmds if "choice" in c)
        n_end = sum(1 for c in cmds if "end" in c)
        index.append({"file": "%s.js" % ch, "entry": entry, "cmds": len(cmds),
                      "say": n_say, "choice": n_ch, "end": n_end})
        print("   %-8s %5d 条  %4d 句对白  %d 选项  %d end  (入口 %s)"
              % (ch, len(cmds), n_say, n_ch, n_end, entry))

    bad = [(ch, g) for ch, g in all_gotos if g not in all_labels]
    print("   label 共 %d 个，goto 共 %d 处，无法解析的 goto: %d"
          % (len(all_labels), len(all_gotos), len(bad)))
    for ch, g in bad[:10]:
        print("      %s -> %s" % (ch, g))

    with open(os.path.join(args.out, "index.js"), "w", encoding="utf-8") as f:
        f.write("// 自动生成。章节清单\n")
        f.write("export default %s\n" % json.dumps(index, ensure_ascii=False, indent=1))
    print("   共 %d 个章节 -> %s" % (len(index), args.out))


if __name__ == "__main__":
    main()
