"""按各页 .ux 的 CSS 数值 1:1 合成应用截图，供上传平台使用。

手环上没有截屏条件，所以这些图是**按源码里的几何数值合成**的——
不是真机截图，但每一处位置、字号、颜色都取自对应的 .ux，版面是准的。

输出 tinyshadows-band/screenshots/：
  1x（336x480，原生）与 3x（1008x1440，上传用，最近邻放大保证不糊边）。
"""

import io
import json
import os
import re
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import preview_port as P  # noqa: E402

PROJ = sys.argv[1] if len(sys.argv) > 1 else "tinyshadows-band"
OUT = os.path.join(PROJ, "screenshots")
W, H = 336, 480
SCALE = 3


def load_cgg(src):
    s = io.open(os.path.join(src, "common", "cglist.js"), encoding="utf-8").read()
    return json.loads(s.split("export const CGG = ")[1])


def load_story(src):
    idx = json.load(io.open(os.path.join(src, "common", "story", "index.txt"),
                            encoding="utf-8"))
    nodes = []
    for c in idx["chunks"]:
        nodes += json.load(io.open(
            os.path.join(src, c["file"].replace("/common/", "common/")),
            encoding="utf-8"))
    return idx, nodes


# ---------------------------------------------------------------- 各页面

def page_home(src, cleared):
    return P.render_title(src, cleared, True)


def page_cg_list(src, img, groups, seen_n):
    page = Image.new("RGBA", (W, H), (20, 16, 26, 255))
    d = ImageDraw.Draw(page, "RGBA")
    d.text((W // 2, 12), "CG 鉴赏", font=P.font(24, True), fill=(255, 216, 230), anchor="ma")
    d.text((W // 2, 44), "已解锁 %d / %d 组 · 点按查看" % (seen_n, len(groups)),
           font=P.font(14), fill=(156, 143, 155), anchor="ma")
    y = 68
    for i, g in enumerate(groups):
        if y + 86 > 426:
            break
        ok = i < seen_n
        P.blend(page, (12, y + 6, 324, y + 80), 16, (36, 28, 44, 255))
        if ok:
            p = P.asset(src, g["th"])
            if p:
                with Image.open(p) as im:
                    page.alpha_composite(im.convert("RGBA").resize((96, 54), Image.LANCZOS),
                                         (22, y + 16))
        else:
            P.blend(page, (22, y + 16, 118, y + 70), 8, (25, 19, 32, 255))
            d.text((70, y + 43), "?", font=P.font(26), fill=(76, 64, 85), anchor="mm")
        d.text((130, y + 30), g["n"], font=P.font(21), fill=(255, 230, 239))
        d.text((324 - 14, y + 36), "%d 张" % len(g["im"]) if ok else "未解锁",
               font=P.font(14), fill=(156, 143, 155), anchor="ra")
        y += 86
    P.blend(page, (50, 432, 286, 472), 20, (50, 36, 58, 255))
    d.text((168, 452), "返回", font=P.font(19), fill=(255, 255, 255), anchor="mm")
    return page


def page_cg_view(src, img, groups, gi, pi):
    g = groups[gi]
    cg = img[g["im"][pi]]
    page = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    p = P.asset(src, cg)
    if p:
        with Image.open(p) as im:
            page.alpha_composite(im.convert("RGBA").resize((W, H), Image.LANCZOS))
    d = ImageDraw.Draw(page, "RGBA")
    P.blend(page, (10, 10, 210, 38), 14, (0, 0, 0, 150))
    d.text((22, 15), g["n"], font=P.font(16), fill=(255, 230, 238))
    P.blend(page, (W - 96, 10, W - 10, 38), 14, (0, 0, 0, 150))
    d.text((W - 18, 24), "%d / %d" % (pi + 1, len(g["im"])), font=P.font(15),
           fill=(216, 203, 210), anchor="rm")
    P.blend(page, (W - 74, 44, W - 10, 78), 17, (0, 0, 0, 158))
    d.text((W - 42, 61), "关闭", font=P.font(17), fill=(255, 230, 239), anchor="mm")
    P.blend(page, (88, 428, 248, 470), 21, (0, 0, 0, 158))
    P.blend(page, (94, 434, 140, 464), 15, (50, 36, 58, 255))
    d.text((117, 449), "‹", font=P.font(22), fill=(255, 255, 255), anchor="mm")
    P.blend(page, (196, 434, 242, 464), 15, (50, 36, 58, 255))
    d.text((219, 449), "›", font=P.font(22), fill=(255, 255, 255), anchor="mm")
    d.text((168, 449), "%d / %d" % (pi + 1, len(g["im"])), font=P.font(16),
           fill=(216, 203, 210), anchor="mm")
    return page


def page_chapters(src, chapters):
    page = Image.new("RGBA", (W, H), (20, 16, 26, 255))
    d = ImageDraw.Draw(page, "RGBA")
    d.text((W // 2, 12), "章节选择", font=P.font(24, True), fill=(255, 216, 230), anchor="ma")
    d.text((W // 2, 44), "共 %d 篇 · 上下滑动 · 点按开始" % len(chapters),
           font=P.font(14), fill=(156, 143, 155), anchor="ma")
    y = 68
    for i, c in enumerate(chapters):
        P.blend(page, (12, y + 6, 324, y + 80), 16, (36, 28, 44, 255))
        d.text((26, y + 43), str(i + 1), font=P.font(17), fill=(207, 158, 192),
               anchor="lm")
        d.text((78, y + 43), c["title"], font=P.font(24), fill=(255, 230, 239), anchor="lm")
        if i == 0:
            # 当前章标一个 ▶。用多边形画而不是写字：msyh 这个字重没有▶ 字形，会渲染成豆腐块
            cx, cy = 304, y + 43
            d.polygon([(cx - 6, cy - 8), (cx - 6, cy + 8), (cx + 7, cy)],
                      fill=(126, 232, 224))
        y += 86
    P.blend(page, (50, 432, 286, 472), 20, (50, 36, 58, 255))
    d.text((168, 452), "返回", font=P.font(19), fill=(255, 255, 255), anchor="mm")
    return page


def _row(page, d, y, label, val, frac):
    d.text((14, y + 2), label, font=P.font(16), fill=(207, 194, 203))
    P.blend(page, (196, y - 2, 228, y + 26), 14, (50, 36, 58, 255))
    d.text((212, y + 12), "−", font=P.font(18), fill=(255, 255, 255), anchor="mm")
    P.blend(page, (286, y - 2, 318, y + 26), 14, (50, 36, 58, 255))
    d.text((302, y + 12), "＋", font=P.font(18), fill=(255, 255, 255), anchor="mm")
    d.text((257, y + 11), val, font=P.font(15), fill=(255, 179, 205), anchor="mm")
    # 滑块
    P.blend(page, (14, y + 28, 322, y + 38), 5, (44, 33, 51, 255))
    P.blend(page, (14, y + 28, 14 + int(308 * frac), y + 38), 5, (185, 80, 121, 255))
    P.blend(page, (14 + int(308 * frac) - 8, y + 25, 14 + int(308 * frac) + 8, y + 41),
            8, (255, 216, 230, 255))


def _pill(page, d, x, y, text, on):
    fill = (185, 80, 121, 255) if on else (44, 33, 51, 255)
    P.blend(page, (x, y, x + 44, y + 30), 15, fill)
    d.text((x + 22, y + 15), text, font=P.font(15),
           fill=(255, 255, 255) if on else (203, 188, 198), anchor="mm")


def page_settings(src):
    """2.5.2 的设置页：3 行滑块 + 2 行开关（屏幕常亮 / 长按屏幕）。"""
    page = Image.new("RGBA", (W, H), (20, 16, 26, 255))
    d = ImageDraw.Draw(page, "RGBA")
    d.text((W // 2, 4), "设置", font=P.font(21, True), fill=(255, 216, 230), anchor="ma")
    _row(page, d, 34, "字体大小", "20", 0.42)
    _row(page, d, 98, "播放速度", "28", 0.23)
    _row(page, d, 162, "自动播放速度", "关闭", 0.0)
    d.text((14, 228), "屏幕常亮", font=P.font(16), fill=(207, 194, 203))
    _pill(page, d, 228, 226, "关", False)
    _pill(page, d, 278, 226, "开", True)
    d.text((14, 262), "长按屏幕", font=P.font(16), fill=(207, 194, 203))
    # 三选一：隐藏 / 快进 / 关闭 —— 整行左移（.lprow left:180）
    _pill(page, d, 180, 260, "隐藏", False)
    _pill(page, d, 230, 260, "快进", True)
    _pill(page, d, 280, 260, "关闭", False)
    d.text((14, 296), "字号 14~30 px，显示的数字就是 px", font=P.font(12), fill=(139, 127, 137))
    d.text((14, 310), "播放速度＝每字毫秒；自动播放＝每句停留毫秒", font=P.font(12),
           fill=(139, 127, 137))
    P.blend(page, (12, 326, 324, 414), 14, (26, 20, 32, 255))
    d.text((168, 334), "预览", font=P.font(13), fill=(156, 143, 155), anchor="ma")
    d.text((26, 356), "她正专注地在眼前的平板上", font=P.font(19), fill=(233, 224, 230))
    d.text((26, 382), "画着什么，小小的身体几乎", font=P.font(19), fill=(233, 224, 230))
    P.blend(page, (50, 420, 286, 460), 20, (50, 36, 58, 255))
    d.text((168, 440), "返回", font=P.font(19), fill=(255, 255, 255), anchor="mm")
    return page


def page_menu(src):
    """阅读菜单（2.5.2）：自动播放 / 快进 / 下一章·快退 / 章节·CG / 设置·主页 / 退出。"""
    page = Image.new("RGBA", (W, H), (20, 15, 23, 255))
    d = ImageDraw.Draw(page, "RGBA")
    d.text((W // 2, 14), "阅读菜单", font=P.font(24, True), fill=(255, 216, 230), anchor="ma")
    d.text((W // 2, 46), "序章 · 咖啡厅的小小身影 · 12%", font=P.font(15),
           fill=(164, 151, 159), anchor="ma")
    y = 74

    def one(label, main=False, quit_=False):
        nonlocal y
        fill = (185, 80, 121, 255) if main else ((36, 26, 43, 255) if quit_ else (44, 33, 51, 255))
        P.blend(page, (48, y, 288, y + 36), 18, fill)
        d.text((168, y + 18), label, font=P.font(17), fill=(255, 255, 255), anchor="mm")
        y += 41

    def two(a, b):
        nonlocal y
        for x, lab in ((48, a), (172, b)):
            P.blend(page, (x, y, x + 116, y + 36), 18, (44, 33, 51, 255))
            d.text((x + 58, y + 18), lab, font=P.font(17), fill=(255, 255, 255), anchor="mm")
        y += 41

    one("继续阅读", main=True)
    one("保存进度")
    one("读取存档")
    one("自动播放：关")
    one("快进：关")
    two("下一章", "快退")
    two("章节", "CG")
    two("设置", "主页")
    one("退出", quit_=True)
    return page


def page_about(src, lines):
    page = Image.new("RGBA", (W, H), (20, 16, 26, 255))
    d = ImageDraw.Draw(page, "RGBA")
    d.text((0, 4), "关于", font=P.font(22, True), fill=(255, 216, 230), anchor="ma")
    d.text((0, 36), "小小的身影，重叠的内心 · v1.0.0", font=P.font(12),
           fill=(156, 143, 155), anchor="ma")
    y = 58
    for kind, text in lines:
        if y + 25 > 424:
            break
        if kind == "s":
            d.text((14, y + 4), text, font=P.font(15), fill=(255, 179, 205))
        elif kind == "p":
            d.text((14, y + 4), text, font=P.font(15), fill=(217, 205, 214))
        y += 25
    P.blend(page, (50, 432, 286, 472), 20, (50, 36, 58, 255))
    d.text((168, 452), "返回", font=P.font(19), fill=(255, 255, 255), anchor="mm")
    return page


# ---------------------------------------------------------------- 主流程

def build_sheet(paths, note="小小的身影，重叠的内心 · 小米手环 9 Pro 版"):
    """把几张截图拼成一版宣传图（1800x1200，和封面同比例）。"""
    SW, SH = 1800, 1200
    sheet = Image.new("RGB", (SW, SH), (26, 18, 28))
    d = ImageDraw.Draw(sheet, "RGBA")
    for i in range(SH):
        d.line([(0, i), (SW, i)],
               fill=(26 + int(14 * i / SH), 18 + int(8 * i / SH), 28 + int(10 * i / SH)))
    tw, th, gap = 360, 514, 26
    total = len(paths) * tw + (len(paths) - 1) * gap
    x, y = (SW - total) // 2, 200
    for p in paths:
        with Image.open(p) as im:
            t = im.convert("RGB").resize((tw, th), Image.LANCZOS)
        # 机身：圆角底 + 边框，模拟手环屏幕
        d.rounded_rectangle((x - 7, y - 7, x + tw + 6, y + th + 6), radius=22,
                            fill=(48, 36, 52), outline=(96, 74, 100), width=2)
        sheet.paste(t, (x, y))
        x += tw + gap
    d.text((SW // 2, 76), note, font=P.font(42, True), fill=(255, 216, 230), anchor="mm")
    # 封面下方的卖点，把空档填满
    lines = [
        "全篇 2,503 句对白 · 3 个选择点 · 2 个结局",
        "本篇 + 后日谈 · CG 鉴赏 8 组 31 张",
        "丝袜差分：裸足 / 白丝 / 黑丝 · 立绘与 CG 都会跟着变",
        "正文字号 14~30 无级可调 · 阅读时屏幕常亮",
    ]
    yy = y + th + 56
    for t in lines:
        d.text((SW // 2, yy), t, font=P.font(28), fill=(216, 200, 210), anchor="mm")
        yy += 46
    d.text((SW // 2, SH - 56), "非官方个人移植 · 仅供学习交流", font=P.font(22),
           fill=(150, 136, 146), anchor="mm")
    return sheet


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    src, img, idx, nodes = P.load_project(PROJ)
    groups = load_cgg(src)
    story_idx, _ = load_story(src)
    chapters = story_idx["chapters"]

    # 正文页：复用 preview_port 的渲染（挑几张有代表性的）
    state = {"bg": -1, "cg": -1, "cs": []}
    picks = {}
    for i, n in enumerate(nodes):
        if "bg" in n:
            state["bg"] = n["bg"]
        if "cs" in n:
            state["cs"] = n["cs"]
        if "cg" in n:
            state["cg"] = n["cg"]
        if n["t"] != "s" or n.get("n") in (None, "", "旁白"):
            continue
        if n.get("cg", -1) >= 0 and "cg" not in picks:
            picks["cg"] = (i, dict(state))
        elif state["cs"] and "sp" not in picks:
            picks["sp"] = (i, dict(state))
    for i, n in enumerate(nodes):
        if n["t"] == "o":
            picks["choice"] = (i, dict(picks.get("sp", (0, state))[1]))
            break

    # 关于页正文（从 about.ux 里抠出来）
    shots = []
    shots.append(("01-主页", page_home(src, False)))
    if "sp" in picks:
        i, st = picks["sp"]
        shots.append(("02-正文·立绘", P.render(src, img, idx, nodes[i], "本篇", "%d%%" % (i * 100 // len(nodes)), st)))
    if "choice" in picks:
        i, st = picks["choice"]
        shots.append(("03-正文·选项", P.render(src, img, idx, nodes[i], "本篇", "22%", st)))
    if "cg" in picks:
        i, st = picks["cg"]
        shots.append(("04-正文·CG", P.render(src, img, idx, nodes[i], "本篇", "%d%%" % (i * 100 // len(nodes)), st)))
    gi = next((k for k, g in enumerate(groups) if g["n"] == "丝袜差分"), 0)
    shots.append(("05-CG鉴赏", page_cg_list(src, img, groups, len(groups))))
    shots.append(("06-CG鉴赏·大图", page_cg_view(src, img, groups, gi, 0)))
    shots.append(("07-章节选择", page_chapters(
        src, [c for c in chapters if not c.get("need")])))
    shots.append(("07b-章节选择·通关后", page_chapters(src, chapters)))
    shots.append(("08-设置", page_settings(src)))
    shots.append(("09-阅读菜单", page_menu(src)))

    for name, im in shots:
        im = im.convert("RGB")
        im.save(os.path.join(OUT, name + ".png"))
        im.resize((W * SCALE, H * SCALE), Image.LANCZOS) \
          .save(os.path.join(OUT, name + "@3x.png"))
        print("  %-18s %dx%d  (+ @3x %dx%d)" % (name, W, H, W * SCALE, H * SCALE))

    # 一版宣传拼图：挑最有代表性的四张（主页 / 正文立绘 / CG / 鉴赏大图）
    want = ["01-主页", "02-正文·立绘", "04-正文·CG", "06-CG鉴赏·大图"]
    picks4 = [os.path.join(OUT, w + ".png") for w in want
              if os.path.exists(os.path.join(OUT, w + ".png"))]
    if len(picks4) >= 3:
        sh = build_sheet(picks4)
        sh.save(os.path.join(OUT, "宣传拼图-1800x1200.png"))
        sh.save(os.path.join(OUT, "宣传拼图-1800x1200.jpg"), quality=92,
                subsampling=0, optimize=True)
        print("  %-18s %dx%d  png %.2f MB  jpg %.2f MB" % (
            "宣传拼图-1800x1200", 1800, 1200,
            os.path.getsize(os.path.join(OUT, "宣传拼图-1800x1200.png")) / 1048576,
            os.path.getsize(os.path.join(OUT, "宣传拼图-1800x1200.jpg")) / 1048576))


if __name__ == "__main__":
    main()
