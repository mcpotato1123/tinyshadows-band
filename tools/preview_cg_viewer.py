"""渲染 CG 鉴赏查看器的效果图，验证 galgod 2.3 的「拖动看全图 + 翻差分」。

CG 现在是完整 16:9 的 854x480，屏幕只有 336 宽，所以查看器里能按住左右拖动、
看被裁掉的左右两部分；底部的 ‹ 换一张差分 › 在这一组内翻差分。

输出 galgod-port/preview/cg-viewer.png
"""

import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "galgod-port")

W, H = 336, 480
VW = 854                      # CG 宽度（对应 cg.ux 的 CG_W）
FONT = "C:/Windows/Fonts/msyh.ttc"


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def load(proj):
    src = os.path.join(proj, "src")
    assets = open(os.path.join(src, "common", "assets.js"), encoding="utf-8").read()
    img = json.loads(assets.split("export const IMG = ")[1].split("\n]")[0] + "\n]")
    cg = open(os.path.join(src, "common", "cglist.js"), encoding="utf-8").read()
    groups = json.loads(cg.split("export const CGG = ")[1])
    return src, img, groups


def draw_viewer(page, cgimg, left, name, no, total):
    """把 CG 按 cg.ux 的方式摆上去：854 宽、object-fit: fill、left 可偏移。"""
    canvas = Image.new("RGB", (VW, H), (0, 0, 0))
    canvas.paste(cgimg.convert("RGB").resize((VW, H), Image.LANCZOS), (0, 0))
    page.paste(canvas.crop((-left, 0, -left + W, H)), (0, 0))

    d = ImageDraw.Draw(page, "RGBA")
    # 顶部：组名 + 第 n / N 张
    d.rounded_rectangle((10, 10, 210, 38), radius=14, fill=(0, 0, 0, 150))
    d.text((22, 15), name, font=font(16), fill=(255, 230, 238))
    d.rounded_rectangle((W - 96, 10, W - 10, 38), radius=14, fill=(0, 0, 0, 150))
    tw = d.textlength("%d / %d" % (no, total), font=font(15))
    d.text((W - 10 - tw - 8, 16), "%d / %d" % (no, total), font=font(15),
           fill=(216, 203, 210))
    # 右上角关闭
    d.rounded_rectangle((W - 74, 44, W - 10, 78), radius=17, fill=(0, 0, 0, 158))
    tw = d.textlength("关闭", font=font(17))
    d.text((W - 42 - tw / 2, 51), "关闭", font=font(17), fill=(255, 230, 239))
    # 底部：‹ 换一张差分 ›
    d.rounded_rectangle((88, 428, 248, 470), radius=21, fill=(0, 0, 0, 158))
    d.rounded_rectangle((94, 434, 140, 464), radius=15, fill=(50, 36, 58))
    d.text((110, 437), "‹", font=font(22), fill=(255, 255, 255))
    d.rounded_rectangle((196, 434, 242, 464), radius=15, fill=(50, 36, 58))
    d.text((212, 437), "›", font=font(22), fill=(255, 255, 255))
    tw = d.textlength("换一张差分", font=font(15))
    d.text((168 - tw / 2, 443), "换一张差分", font=font(15), fill=(216, 203, 210))
    return page


def main():
    src, img, groups = load(PROJ)
    path = lambda n: os.path.join(src, "common", "img", "c", n + ".png")

    # 找「丝袜差分」那一组
    grp = next((g for g in groups if g["n"] == "丝袜差分"), groups[0])
    names = [img[i].split("/")[-1][:-4] for i in grp["im"]]

    rows = []
    # 第一行：同一张 CG 的三个拖动位置（看被裁掉的左右两部分）
    cg0 = Image.open(path(names[0])).convert("RGB")
    pan = [("拖到最左", 0), ("居中", -(VW - W) // 2), ("拖到最右", -(VW - W))]
    rows.append(("拖动看全图 · 同一张 CG（854x480 比屏幕宽 518px）",
                 [(lab, draw_viewer(Image.new("RGBA", (W, H), (0, 0, 0, 255)),
                                    cg0, off, grp["n"], 1, len(names)))
                  for lab, off in pan]))
    # 第二行：这一组的差分
    rows.append(("‹ 换一张差分 › · 白丝 / 裸足 / 黑丝",
                 [(n, draw_viewer(Image.new("RGBA", (W, H), (0, 0, 0, 255)),
                                  Image.open(path(n)).convert("RGB"),
                                  -(VW - W) // 2, grp["n"], k + 1, len(names)))
                  for k, n in enumerate(names[:3])]))

    pad, gap, hdr = 12, 10, 30
    sw = W * 3 + gap * 2 + pad * 2
    sh = pad + len(rows) * (hdr + H + pad + 22) + gap
    sheet = Image.new("RGB", (sw, sh), (26, 20, 30))
    d = ImageDraw.Draw(sheet)
    y = pad
    for title, tiles in rows:
        d.text((pad, y), title, font=font(17), fill=(255, 214, 230))
        y += hdr
        for i, (lab, t) in enumerate(tiles):
            x = pad + i * (W + gap)
            sheet.paste(t.convert("RGB"), (x, y))
            d.rectangle((x, y, x + W - 1, y + H - 1), outline=(70, 56, 78))
            tw = d.textlength(lab, font=font(15))
            d.text((x + (W - tw) / 2, y + H + 5), lab, font=font(14),
                   fill=(216, 200, 226))
        y += H + pad + gap + 22

    out = os.path.join(PROJ, "preview", "cg-viewer.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("CG 查看器效果图 -> %s  %s" % (out, sheet.size))
    print("丝袜差分组成员:", names)


if __name__ == "__main__":
    main()
