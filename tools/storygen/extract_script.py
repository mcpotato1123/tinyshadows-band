"""Extract dialogue + stage directions from a Ren'Py game's .rpyc files.

Works on the pickled AST using tools/rpyc_probe.py (permissive unpickler).

Chinese comes from scripts/content/*.rpyc (the game's source language).
Japanese is aligned onto that same spine by dialogue identifier, using the
translations in tl/japanese/scripts/content/*.rpyc. Matching by identifier
(rather than reading the translation file top-to-bottom) avoids the stale
duplicate blocks the translation file also contains.
"""

import argparse
import ast
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rpyc_probe import load_rpyc  # noqa: E402
from rpyc_dump import slots_of, is_node  # noqa: E402
from rpyc_expr import expr_text  # noqa: E402

# Character variable -> display name, recovered from scripts/roles/role.rpyc.
CHARACTERS = {
    "e": "苏幼晴",
    "l": "林默",
    "s": "？？？",
    "servant": "服务员",
    "vendor_a": "摊主 A",
    "vendor_b": "摊主 B",
    "vendor_ab": "摊主 A&B",
    "passer": "路人甲",
    "rude_uncle": "大叔",
    "clerk": "店员",
    "colleague_a": "同事A",
    "supervisor": "主管",
    "king": "王总",
    "boss_chen": "陈总",
    "comment_paid": "付费留言",
    "danmu": "弹幕",
    "yrj": "月染酱",
    "young_artist": "年轻画师",
    "otaku_a": "阿宅甲",
    "otaku_b": "阿宅乙",
    "otaku_c": "阿宅丙",
    "otaku_d": "阿宅丁",
    "staff": "工作人员",
}

# Config-only scripts that carry no dialogue.
SKIP_FILES = {"background", "bgm", "transform", "options", "gui"}

CHAPTER_ORDER = ["script", "part2", "part3", "part4", "end", "extra1"]

TAG_RE = re.compile(r"\{[^}]*\}")
TITLE = "《小小的身影，重叠的内心》"

STAGE_LABEL = {
    "scene": "场景", "show": "立绘", "hide": "隐藏",
    "jump": "跳转 →", "call": "调用 →", "if": "条件", "return": "结束",
}


def clean(text):
    """Strip Ren'Py text tags; keep the readable text."""
    if not isinstance(text, str):
        return text
    return TAG_RE.sub("", text)


def unquote(value):
    """Menu prompts store raw source literals such as "'e'"."""
    if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] \
            and value[0] in "'\"":
        try:
            out = ast.literal_eval(value)
            return out if isinstance(out, str) else value
        except Exception:
            return value[1:-1]
    return value


def find_nodes(o, want, acc=None, seen=None):
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
            find_nodes(v, want, acc, seen)
    elif isinstance(o, (list, tuple)):
        seen.add(id(o))
        for v in o:
            find_nodes(v, want, acc, seen)
    elif isinstance(o, dict):
        seen.add(id(o))
        for v in o.values():
            find_nodes(v, want, acc, seen)
    return acc


def ordered_children(node):
    """Yield child statements in source order."""
    sl = slots_of(node)
    t = type(node).__name__

    if t == "If":
        for entry in sl.get("entries", []) or []:
            yield from (entry[-1] or [])
        return

    if t == "Menu":
        for item in sl.get("items", []) or []:
            yield from (item[2] or [])
        return

    blk = sl.get("block")
    if isinstance(blk, list):
        yield from blk


def image_name(imspec):
    if not imspec:
        return None
    name = imspec[0]
    if isinstance(name, (tuple, list)):
        return " ".join(str(x) for x in name)
    return str(name)


def say_event(who_var, what, identifier=None):
    return {"kind": "say", "who_var": who_var, "what": what,
            "text": clean(what), "identifier": identifier}


def walk_script(stmts, out, sprites, backgrounds):
    """Depth-first, source-ordered walk. Appends event dicts to `out`."""

    def rec(node, label):
        t = type(node).__name__
        sl = slots_of(node)

        if t == "Label":
            label = sl.get("_name") or label
            # Ren'Py's achievement restructure splits the script into
            # auto-generated _call_achievement_* labels; don't headline them.
            if not str(label).startswith("_call_achievement"):
                out.append({"kind": "label", "name": label})
        elif t in ("Say", "TranslateSay"):
            out.append(say_event(sl.get("who"), sl.get("what"),
                                 sl.get("identifier")))
        elif t in ("Show", "Scene"):
            nm = image_name(sl.get("imspec"))
            out.append({"kind": t.lower(), "image": nm})
            if nm:
                sprites.add(nm)
                if t == "Scene":
                    backgrounds.add(nm)
        elif t == "Hide":
            out.append({"kind": "hide", "image": image_name(sl.get("imspec"))})
        elif t == "Jump":
            out.append({"kind": "jump", "target": sl.get("target")})
        elif t == "Call":
            out.append({"kind": "call", "label": sl.get("label")})
        elif t == "Return":
            out.append({"kind": "return"})
        elif t == "Menu":
            # `statement_start` is deliberately NOT emitted: Ren'Py's static
            # transform leaves it pointing at a stale, un-analysed copy of the
            # menu caption while the caption that actually runs sits in the
            # parent block (with the real translation identifier). Emitting
            # both would duplicate the line. Ren'Py only reads statement_start
            # for call return-sites (renpy/execution.py), never for display.
            for item in sl.get("items", []) or []:
                out.append({"kind": "choice", "text": clean(item[0])})
                for c in (item[2] or []):
                    rec(c, label)
            return
        elif t == "If":
            for entry in sl.get("entries", []) or []:
                out.append({"kind": "if", "condition": expr_text(entry[0])})
                for c in (entry[-1] or []):
                    rec(c, label)
            return

        for child in ordered_children(node):
            rec(child, label)

    for st in stmts:
        rec(st, None)


def format_events(events, source, names, choice_word):
    lines = []
    for ev in events:
        k = ev["kind"]
        if k == "label":
            lines += ["", "=" * 70,
                      "【%s】  (label: %s)" % (source, ev["name"]),
                      "=" * 70]
        elif k == "say":
            text = ev.get("text") or ""
            who_var = ev.get("who_var")
            who = names.get(who_var, who_var) if who_var else None
            lines.append("%s：%s" % (who, text) if who else text)
        elif k == "choice":
            lines.append("    ▶ %s：%s" % (choice_word, ev.get("text") or ""))
        elif k in STAGE_LABEL:
            if k == "return":
                lines.append("[%s]" % STAGE_LABEL[k])
            else:
                key = ev.get("image") or ev.get("target") or ev.get("label") \
                    or ev.get("condition")
                name = STAGE_LABEL[k]
                sep = " " if name.endswith("→") else "："
                lines.append("[%s%s%s]" % (name, sep, key))
    return "\n".join(lines)


def chapter_sort_key(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return CHAPTER_ORDER.index(stem) if stem in CHAPTER_ORDER else 99


def collect_japanese(tl_root):
    """{identifier: japanese_text} plus {chinese: japanese} name translations."""
    texts, names = {}, {}
    for path in sorted(glob.glob(os.path.join(tl_root, "**", "*.rpyc"),
                                 recursive=True)):
        try:
            _data, stmts = load_rpyc(path)
        except Exception:
            continue
        for n in find_nodes(stmts, {"Say", "TranslateSay"}):
            sl = slots_of(n)
            ident, what = sl.get("identifier"), sl.get("what")
            if ident and isinstance(what, str) and what:
                texts[ident] = what
        for n in find_nodes(stmts, {"TranslateString"}):
            sl = slots_of(n)
            old, new = sl.get("old"), sl.get("new")
            if isinstance(old, str) and isinstance(new, str) and new:
                names[old] = new
    return texts, names


def write_chapter(out_dir, stem, events, names, source, choice_word, combined):
    header = "%s — %s\n" % (TITLE, stem)
    text = header + "\n" + format_events(events, source, names, choice_word) + "\n"
    with open(os.path.join(out_dir, "%s.txt" % stem), "w", encoding="utf-8") as f:
        f.write(text)
    combined.append(text)
    return sum(1 for e in events if e["kind"] == "say")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", default="原始解包/scripts_rpa/scripts/content")
    ap.add_argument("--tl", default="原始解包/scripts_rpa/tl/japanese")
    ap.add_argument("--out", default="解包/对话")
    args = ap.parse_args()

    sprites, backgrounds = set(), set()
    chapters = {}
    for path in sorted(glob.glob(os.path.join(args.scripts, "*.rpyc")),
                       key=chapter_sort_key):
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem in SKIP_FILES:
            continue
        _data, stmts = load_rpyc(path)
        events = []
        walk_script(stmts, events, sprites, backgrounds)
        chapters[stem] = events

    zh_dir = os.path.join(args.out, "中文")
    os.makedirs(zh_dir, exist_ok=True)
    zh_combined, index = [], []
    print("   [中文]")
    for stem, events in chapters.items():
        n = write_chapter(zh_dir, stem, events, CHARACTERS, stem, "选择", zh_combined)
        index.append({"file": "中文/%s.txt" % stem, "say_lines": n})
        print("   %-10s %5d events  %5d 句" % (stem, len(events), n))
    with open(os.path.join(zh_dir, "全部对话.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(zh_combined))

    ja_texts, ja_names_raw = collect_japanese(args.tl)
    ja_names = {v: ja_names_raw.get(zh, zh) for v, zh in CHARACTERS.items()}
    ja_dir = os.path.join(args.out, "日语")
    os.makedirs(ja_dir, exist_ok=True)
    ja_combined, ja_index, matched, total = [], [], 0, 0
    print("   [日本語]")
    for stem, events in chapters.items():
        translated = []
        for ev in events:
            if ev["kind"] == "say":
                total += 1
                ja = ja_texts.get(ev.get("identifier"))
                if ja:
                    matched += 1
                    ev = dict(ev, what=ja, text=clean(ja))
                else:
                    ev = dict(ev, text="［未翻訳］" + (ev.get("text") or ""))
            translated.append(ev)
        n = write_chapter(ja_dir, stem, translated, ja_names, stem, "選択", ja_combined)
        ja_index.append({"file": "日语/%s.txt" % stem, "say_lines": n})
        print("   %-10s %5d events  %5d 句" % (stem, len(translated), n))
    with open(os.path.join(ja_dir, "全部对话.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(ja_combined))

    with open(os.path.join(args.out, "_index.json"), "w", encoding="utf-8") as f:
        json.dump({"chapters": index, "japanese_chapters": ja_index,
                   "sprites": sorted(sprites), "backgrounds": sorted(backgrounds)},
                  f, ensure_ascii=False, indent=1)

    print("   %d Chinese dialogue lines; Japanese matched %d/%d"
          % (sum(c["say_lines"] for c in index), matched, total))


if __name__ == "__main__":
    main()
