"""按 game.ux 的 CSS 几何渲染界面预览图（真机之外能拿到的最接近的效果）。

它复刻的是 tinyshadows-band/src/pages/game/game.ux 里 <style> 的数值，
分页用 common/reader.js 的同一套规则（每行字数 = 正文框宽 / 字号，
断行优先落在标点之后），字体用系统里自带的微软雅黑近似原版思源黑体。

用法: python tools/preview_port.py [工程目录] [输出目录]
"""

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 336, 480

# ---- 与 game.ux 的 <style> 一一对应
PANEL_TOP, PANEL_H = 330, 150
NAME_TOP, NAME_LEFT = 292, 12
TEXT_TOP, TEXT_LEFT, TEXT_W, TEXT_PAD, TEXT_H = 338, 10, 316, 6, 122
MAX_LINES = 6
SP_W, SP_H, SP_TOP = 143, 380, 100
SP_LEFT = {"left": 10, "center": 96, "right": 182}
SIZE = 20                      # 默认字号
LINE_H = SIZE + 4
CPL = max(4, (TEXT_W - TEXT_PAD) // SIZE)
LPP = max(1, min(MAX_LINES, TEXT_H // LINE_H))

BREAK_AFTER = "，。！？；：、）」』…—"

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_B if bold else FONT, size)
    return _fonts[key]


def wrap(text, cpl):
    lines = []
    for raw in str(text or "").split("\n"):
        s = raw
        if s == "":
            lines.append("")
            continue
        while len(s) > cpl:
            cut = cpl
            for k in range(cpl, max(2, cpl - 8), -1):
                if BREAK_AFTER.find(s[k - 1]) >= 0:
                    cut = k
                    break
            lines.append(s[:cut])
            s = s[cut:]
        lines.append(s)
    return lines or [""]


def paginate(text):
    lines = wrap(text, CPL)
    return [lines[i:i + LPP] for i in range(0, len(lines), LPP)] or [[""]]


def blend(page, box, radius, fill):
    """在半透明图层上画好形状，再整体合成上去。

    注意：直接 ImageDraw 到 RGBA 图上时，带 alpha 的 fill 是把颜色**连 alpha 一起
    替换**进去，不是做混合。那样画出来的半透明遮罩其实是一片透明镂空，
    叠到别的背景上就会发黑。所以统一走这里。
    """
    layer = Image.new("RGBA", page.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill)
    page.alpha_composite(layer)


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def load_project(proj):
    src = os.path.join(proj, "src")
    assets = open(os.path.join(src, "common", "assets.js"), encoding="utf-8").read()
    img = json.loads(assets.split("export const IMG = ")[1].split("\n]")[0] + "\n]")
    idx = json.load(open(os.path.join(src, "common", "story", "index.txt"),
                         encoding="utf-8"))
    nodes = []
    for c in idx["chunks"]:
        p = os.path.join(src, c["file"].replace("/common/", "common/"))
        nodes += json.load(open(p, encoding="utf-8"))
    return src, img, idx, nodes


def asset(src, path):
    p = os.path.join(src, path.replace("/common/", "common/"))
    return p if path and os.path.exists(p) else None


def render(src, img, idx, node, chapter, progress, state):
    page = Image.new("RGBA", (W, H), (0, 0, 0, 255))

    # 背景
    if state.get("bg", -1) >= 0:
        p = asset(src, img[state["bg"]])
        if p:
            with Image.open(p) as im:
                im = im.convert("RGBA")
                s = max(W / im.width, H / im.height)
                im = im.resize((max(W, int(im.width * s)),
                                max(H, int(im.height * s))), Image.LANCZOS)
                page.alpha_composite(im, ((W - im.width) // 2, (H - im.height) // 2))
    elif state.get("bg") == -2:
        page = Image.new("RGBA", (W, H), (255, 255, 255, 255))

    # 立绘
    for c in (state.get("cs") or []):
        p = asset(src, img[c["i"]])
        if not p:
            continue
        with Image.open(p) as im:
            im = im.convert("RGBA")
            s = min(SP_W / im.width, SP_H / im.height)
            im = im.resize((max(1, int(im.width * s)),
                            max(1, int(im.height * s))), Image.LANCZOS)
        x = SP_LEFT.get(c.get("s"), 96) + (SP_W - im.width) // 2
        y = SP_TOP + (SP_H - im.height) // 2
        page.alpha_composite(im, (x, y))

    # CG
    if state.get("cg", -1) >= 0:
        p = asset(src, img[state["cg"]])
        if p:
            with Image.open(p) as im:
                im = im.convert("RGBA")
                s = max(W / im.width, H / im.height)
                im = im.resize((max(W, int(im.width * s)),
                                max(H, int(im.height * s))), Image.LANCZOS)
                page.alpha_composite(im, ((W - im.width) // 2, (H - im.height) // 2))

    d = ImageDraw.Draw(page, "RGBA")

    # 顶部信息条 + 菜单按钮（.hud 是自适应宽度的 row，不写死宽度）
    ft, fp = font(17), font(15)
    tw = d.textlength(chapter, font=ft)
    pw = d.textlength(progress, font=fp)
    blend(page, (12, 10, 12 + 10 + tw + 8 + pw + 10, 10 + 26), 13, (0, 0, 0, 140))
    d.text((22, 13), chapter, font=ft, fill=(255, 230, 239, 255))
    d.text((22 + tw + 8, 15), progress, font=fp, fill=(185, 176, 182, 255))
    blend(page, (290, 8, 290 + 36, 8 + 36), 18, (27, 21, 32, 209))
    d.text((304, 8), "≡", font=font(24), fill=(255, 216, 230, 255))

    if node["t"] == "o":
        y = 96
        for o in node["o"]:
            opts = wrap(o["x"], 15)
            h = max(52, 20 + len(opts) * 26)
            blend(page, (16, y, 16 + 304, y + h), 12, (36, 26, 43, 240))
            ty = y + 10
            for ln in opts:
                d.text((26, ty), ln, font=font(19), fill=(255, 230, 239, 255))
                ty += 26
            y += h + 8
        return page

    # 对白底板
    blend(page, (0, PANEL_TOP, W, PANEL_TOP + PANEL_H), 0, (18, 13, 19, 204))

    speaker = node.get("n") or ""
    if speaker:
        tw = d.textlength(speaker, font=font(20, True))
        blend(page, (NAME_LEFT, NAME_TOP, NAME_LEFT + tw + 20, NAME_TOP + 34),
                  9, (16, 11, 18, 189))
        d.text((NAME_LEFT + 10, NAME_TOP + 4), speaker,
               font=font(20, True), fill=(255, 216, 230, 255))

    pages = paginate(node.get("x") or "")
    lines = pages[0]
    for i, ln in enumerate(lines[:MAX_LINES]):
        d.text((TEXT_LEFT, TEXT_TOP + i * LINE_H), ln,
               font=font(SIZE), fill=(255, 255, 255, 255))

    d.text((308, 462), "▼", font=font(16), fill=(255, 158, 196, 255))
    if len(pages) > 1:
        d.text((10, 462), "1/%d" % len(pages), font=font(13),
               fill=(150, 140, 150, 255))
    return page


def render_title(src, cleared, has_auto):
    """标题页。几何取自 pages/index/index.ux 的 <style>。"""
    page = Image.new("RGBA", (W, H), (13, 9, 16, 255))

    p = asset(src, "/common/home.png")
    if p:
        with Image.open(p) as im:
            im = im.convert("RGBA")
            s = max(W / im.width, H / im.height)
            im = im.resize((max(W, int(im.width * s)),
                            max(H, int(im.height * s))), Image.LANCZOS)
            page.alpha_composite(im, ((W - im.width) // 2, (H - im.height) // 2))
    d = ImageDraw.Draw(page, "RGBA")
    blend(page, (0, 0, W, H), 0, (13, 9, 16, 87))            # .shade 0.34

    # .head：top 54，居中放 logo（288x144）
    p = asset(src, "/common/logo.png")
    if p:
        with Image.open(p) as im:
            im = im.convert("RGBA")
            page.alpha_composite(im, ((W - im.width) // 2, 54))

    # .panel：top 240，高 240
    blend(page, (0, 240, W, 480), 0, (21, 15, 25, 240))
    d = ImageDraw.Draw(page, "RGBA")

    y = 252
    resume = '最近进度 · 本篇' if has_auto else '还没有存档，从序章开始吧'
    tw = d.textlength(resume, font=font(15))
    d.text(((W - tw) / 2, y), resume, font=font(15), fill=(185, 167, 179, 255))
    y += 28

    def btn(label, y, bg=(50, 36, 58, 255), size=19):
        blend(page, (50, y, 50 + 236, y + 40), 20, bg)
        tw = d.textlength(label, font=font(size))
        d.text(((W - tw) / 2, y + (40 - size) / 2 - 1), label,
               font=font(size), fill=(255, 255, 255, 255))

    btn('开始阅读', y, (185, 80, 121, 255))
    y += 48
    if has_auto:
        btn('继续阅读', y)
        y += 48

    # .row：236 宽，5 个 46px 按钮平分（未通关时少一个「章节」）
    names = ['存档'] + (['章节'] if cleared else []) + ['CG', '设置', '关于']
    n = len(names)
    gap = (236 - 46 * n) / (n - 1)
    for i, nm in enumerate(names):
        x = 50 + i * (46 + gap)
        blend(page, (x, y, x + 46, y + 40), 20, (50, 36, 58, 255))
        tw = d.textlength(nm, font=font(16))
        d.text((x + (46 - tw) / 2, y + 11), nm, font=font(16),
               fill=(255, 255, 255, 255))
    y += 48
    btn('退出', y, (36, 26, 43, 255))
    return page


def main():
    proj = sys.argv[1] if len(sys.argv) > 1 else "tinyshadows-band"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(proj, "preview")
    os.makedirs(out, exist_ok=True)
    src, img, idx, nodes = load_project(proj)

    def chapter_of(i):
        cur = idx["chapters"][0]
        for c in idx["chapters"]:
            if i >= c["start"]:
                cur = c
        return cur

    # 画面状态是累积的：节点上的 bg/cs/cg 只是「从这句开始变成这样」，
    # 和 game.ux 的 step() 一样按 bg -> cs -> cg 的顺序套用。
    states = []
    st = {"bg": -1, "cg": -1, "cs": []}
    for n in nodes:
        if "bg" in n:
            st["bg"] = n["bg"]
        if "cs" in n:
            st["cs"] = n["cs"]
        if "cg" in n:
            st["cg"] = n["cg"]
        states.append(dict(st))

    # 挑几张有代表性的画面：带立绘的对白、带 CG 的、有背景切换的、选项
    picks = []
    seen_kind = set()
    for i, n in enumerate(nodes):
        if n["t"] == "o":
            picks.append((i, "choice"))
            continue
        if n["t"] != "s" or not (n.get("x") or "").strip():
            continue
        has_sp = bool(n.get("cs"))
        has_cg = n.get("cg", -1) >= 0
        has_bg = n.get("bg", -1) >= 0
        key = ("cg" if has_cg else "sp" if has_sp else "bg") + \
              ("/name" if n.get("n") else "/nar")
        if key in seen_kind or len([p for p in picks if p[1] == key]) >= 1:
            continue
        ch = chapter_of(i)
        end = next((c["start"] for c in idx["chapters"] if c["start"] > ch["start"]),
                   idx["nodeCount"])
        prog = "%d%%" % min(99, round(max(0, i - ch["start"]) * 100 / max(1, end - ch["start"])))
        seen_kind.add(key)
        picks.append((i, key))
    picks = picks[:8]

    tiles = []
    # 标题页：通关前（4 个按钮，无「章节」）与通关后（5 个按钮）
    tiles.append(render_title(src, False, True))
    tiles.append(render_title(src, True, True))
    print("  渲染 标题页（通关前 / 通关后）")

    for i, key in picks:
        ch = chapter_of(i)
        end = next((c["start"] for c in idx["chapters"] if c["start"] > ch["start"]),
                   idx["nodeCount"])
        prog = "%d%%" % min(99, round(max(0, i - ch["start"]) * 100 / max(1, end - ch["start"])))
        tiles.append(render(src, img, idx, nodes[i], ch["title"], prog, states[i]))
        print("  渲染 #%d (%s)" % (i, key))

    # 拼成对照表
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    pad = 10
    sheet = Image.new("RGBA", (cols * W + (cols + 1) * pad,
                               rows * H + (rows + 1) * pad), (24, 18, 28, 255))
    for k, t in enumerate(tiles):
        x = pad + (k % cols) * (W + pad)
        y = pad + (k // cols) * (H + pad)
        sheet.alpha_composite(t, (x, y))
    sheet.convert("RGB").save(os.path.join(out, "ui-preview.png"), "PNG",
                              optimize=True)
    print("预览图 -> %s" % os.path.join(out, "ui-preview.png"))


if __name__ == "__main__":
    main()
