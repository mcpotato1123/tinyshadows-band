"""用原作的分层素材拼一张 3:2（宽高比 1.5）的封面，供上传平台使用。

素材全部来自原作的标题画面（`解包/界面素材/custom/`）：
  titlenew_bg_1.png        1920x1080  草地背景
  titlenew_bg_3_char.png   1183x1037  苏幼晴全身（带透明）
  LOGO_white.png           3059x1527  标题 logo（带透明，深色描边）

输出 tinyshadows-band/cover/ 下的若干尺寸。
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

UI = "解包/界面素材/custom"
OUT = "tinyshadows-band/cover"
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

W, H = 1800, 1200          # 3:2


def font(sz, bold=False):
    for p in ((FONT_B if bold else FONT), FONT):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def cover(im, w, h, cx=0.5, cy=0.5):
    """按 cover 缩放并裁到 w×h；(cx,cy) 决定保留哪一段。"""
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(round(im.width * s))),
                    max(h, int(round(im.height * s)))), Image.LANCZOS)
    x = int(round((im.width - w) * cx))
    y = int(round((im.height - h) * cy))
    return im.crop((x, y, x + w, y + h))


def trimmed(im):
    """按 alpha 去掉四周空白，返回 (图, bbox)。"""
    bb = im.getchannel("A").getbbox()
    return (im.crop(bb) if bb else im), bb


def build(sub=True, corner=True):
    # --- 背景
    bg = Image.open(os.path.join(UI, "title", "titlenew_bg_1.png")).convert("RGB")
    page = cover(bg, W, H, cx=0.42, cy=0.55).convert("RGBA")

    # --- 人物：贴右下，顶上加留白免得呆毛被切
    ch = Image.open(os.path.join(UI, "title", "titlenew_bg_3_char.png")).convert("RGBA")
    ch, _ = trimmed(ch)
    th = int(round(H * 0.90))
    ch = ch.resize((max(1, int(round(ch.width * th / ch.height))), th), Image.LANCZOS)
    page.alpha_composite(ch, (W - ch.width, H - ch.height))

    # --- 标题 logo：放左侧
    lg = Image.open(os.path.join(UI, "LOGO_white.png")).convert("RGBA")
    lg, _ = trimmed(lg)
    lw = 820
    lg = lg.resize((lw, max(1, int(round(lg.height * lw / lg.width)))), Image.LANCZOS)
    lx, ly = 74, int(H * 0.28)
    page.alpha_composite(lg, (lx, ly))

    d = ImageDraw.Draw(page, "RGBA")

    if sub:
        # --- 副标题：跟 logo 左对齐
        ty = ly + lg.height + 24
        d.text((lx + 8, ty), "小米手环 9 Pro 版", font=font(46, True),
               fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(74, 44, 58, 235))
        d.text((lx + 10, ty + 62), "Vela 快应用 · 全篇 2,503 句对白", font=font(28),
               fill=(255, 236, 244, 245), stroke_width=4, stroke_fill=(74, 44, 58, 210))

    if corner:
        # 底部压一点暗角，让右下角那行字在任何背景下都读得清
        grad = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for i in range(150):
            gd.line([(0, i), (W, i)], fill=(30, 16, 24, int(150 * (i / 150.0) ** 2)))
        page.alpha_composite(grad, (0, H - 150))
        d = ImageDraw.Draw(page, "RGBA")
        d.text((W - 26, H - 40), "非官方个人移植 · 仅供学习交流",
               font=font(24), fill=(255, 255, 255, 225), anchor="rs",
               stroke_width=4, stroke_fill=(60, 38, 48, 210))
    return page.convert("RGB")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    full = build(True, True)
    plain = build(False, False)

    # PNG 只留主版当无损母版；其余出 JPG——PNG 这张有 2.8 MB，不少平台上限是 2 MB
    jobs = [
        (full, "cover-1800x1200", (1800, 1200), True),
        (full, "cover-1200x800", (1200, 800), False),
        (full, "cover-900x600", (900, 600), False),
        (plain, "cover-1800x1200-简洁", (1800, 1200), True),
        (plain, "cover-1200x800-简洁", (1200, 800), False),
    ]
    for im, name, (w, h), want_png in jobs:
        t = im if (w, h) == (W, H) else im.resize((w, h), Image.LANCZOS)
        t.save(os.path.join(OUT, name + ".jpg"), quality=92,
               subsampling=0, optimize=True)
        line = "  %-26s %dx%d  jpg %5.2f MB" % (
            name, w, h, os.path.getsize(os.path.join(OUT, name + ".jpg")) / 1048576)
        if want_png:
            t.save(os.path.join(OUT, name + ".png"))
            line += "   png %5.2f MB" % (
                os.path.getsize(os.path.join(OUT, name + ".png")) / 1048576)
        print(line)


if __name__ == "__main__":
    main()
