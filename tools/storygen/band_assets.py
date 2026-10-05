"""把解包出来的素材转换成小米手环 9 Pro（336x480）能用的尺寸。

- 背景 / CG：等比裁切填满 336x480，存成 JPEG（省空间）
- 立绘：按脸部包围盒自动取景成半身像，存成带透明通道的 PNG

裁切区由「该视图 smiling 表情图层的包围盒」推算，所以便服正面、便服侧面、
制服正面三套姿势都能自动取到合适的构图，不需要手调坐标。
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

from compose_sprites import (build_name_map, composite, parse_layeredimage,  # noqa: E402
                             resolve)

SCREEN_W, SCREEN_H = 336, 480

# 服装 / 姿势组，剧本里显式给出时不要再用默认值覆盖
POSTURES = {"clothes1_front", "clothes1_side", "clothes2_front", "clothes2_side"}

# 取景参数：以脸部为中心，脸顶距画面上沿的比例
CROP_W = 800
FACE_TOP_RATIO = 0.18
# 只保留画面里看得见的部分，避免整张立绘缩放后脸部太小


def face_bbox(name_map, view, face="smile"):
    """返回该视图 smile 表情图层的 alpha 包围盒。"""
    key = "syq_%s_face_%s" % (view, face)
    path = name_map.get(key)
    if path is None:
        cands = [k for k in name_map if k.startswith("syq_%s_face_" % view)]
        if not cands:
            return None
        path = name_map[sorted(cands)[0]]
    with Image.open(path) as im:
        return im.getchannel("A").getbbox()


def crop_box(bbox):
    h = int(round(CROP_W * SCREEN_H / SCREEN_W))
    cx = (bbox[0] + bbox[2]) // 2
    y0 = int(bbox[1] - FACE_TOP_RATIO * h)
    return (cx - CROP_W // 2, y0, cx + CROP_W // 2, y0 + h)


def fit_cover(im, w, h):
    """等比缩放并居中裁切，填满 w x h。"""
    s = max(w / im.width, h / im.height)
    nw, nh = max(w, int(round(im.width * s))), max(h, int(round(im.height * s)))
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return im.crop((left, top, left + w, top + h))


def fit_contain(im, w, h):
    """等比缩放并居中放到 w x h 的透明画布上（不裁切）。"""
    s = min(w / im.width, h / im.height)
    nw, nh = max(1, int(round(im.width * s))), max(1, int(round(im.height * s)))
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((w - nw) // 2, (h - nh) // 2))
    return canvas


def flatten(im):
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (0, 0, 0))
        bg.paste(im, mask=im.getchannel("A"))
        return bg
    return im.convert("RGB")


def clean_dir(d):
    """重建前清空目录，避免改名/改规则后留下过期的旧图。"""
    if os.path.isdir(d):
        for fn in os.listdir(d):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                os.remove(p)
    os.makedirs(d, exist_ok=True)


def build_backgrounds(src_dir, dst_dir, quality):
    clean_dir(dst_dir)
    n = 0
    for path in sorted(glob.glob(os.path.join(src_dir, "*"))):
        if not os.path.isfile(path):
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        with Image.open(path) as im:
            out = fit_cover(flatten(im), SCREEN_W, SCREEN_H)
        out.save(os.path.join(dst_dir, stem + ".jpg"), "JPEG",
                 quality=quality, optimize=True)
        n += 1
    return n


def build_cg(src_dir, dst_dir, quality):
    clean_dir(dst_dir)
    n = 0
    for path in sorted(glob.glob(os.path.join(src_dir, "**", "*"), recursive=True)):
        if not os.path.isfile(path):
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        with Image.open(path) as im:
            out = fit_cover(flatten(im), SCREEN_W, SCREEN_H)
        out.save(os.path.join(dst_dir, stem + ".jpg"), "JPEG",
                 quality=quality, optimize=True)
        n += 1
    return n


def sprite_key(chosen):
    return "_".join(chosen[g].attr for g in
                    ("clothes_posture", "skin", "feet", "face") if g in chosen)


def build_sprites(fg_root, rpyc, dst_dir, wanted, extra_faces):
    """wanted: 剧本里用到的立绘属性字符串列表。"""
    _name, group_order, groups = parse_layeredimage(rpyc)
    name_map = build_name_map(fg_root)

    boxes = {}
    for view in ("front", "side", "cos_front", "cos_side"):
        bb = face_bbox(name_map, view)
        if bb:
            boxes[view] = crop_box(bb)
    print("   取景框:", {k: v for k, v in boxes.items()})

    os.makedirs(dst_dir, exist_ok=True)
    clean_dir(dst_dir)
    made, skipped = {}, []

    def render(attrs):
        chosen, _full = resolve(groups, group_order, attrs)
        if chosen is None:
            skipped.append(attrs)
            return None
        key = sprite_key(chosen)
        if key in made:
            return key
        base = chosen.get("clothes_posture")
        view = "front"
        if base and base.image and base.image.startswith("syq_"):
            view = base.image[len("syq_"):-len("_base")] or "front"
        box = boxes.get(view)
        if box is None:
            skipped.append(attrs)
            return None
        img, _used = composite(chosen, name_map, group_order)
        if img is None:
            skipped.append(attrs)
            return None
        bust = img.crop(box)
        out = fit_contain(bust, SCREEN_W, SCREEN_H)
        out.save(os.path.join(dst_dir, key + ".png"), "PNG", optimize=True)
        made[key] = True
        return key

    # 剧本里实际用到的
    for s in wanted:
        attrs = s[len("syq_"):].split() if s.startswith("syq_") else []
        # 只有剧本没指定姿势时才补默认姿势，否则会把制服覆盖成便服
        if not (set(attrs) & POSTURES):
            attrs = attrs + ["clothes1_front"]
        render(attrs)
    # 补齐全套表情，方便后续章节 / 作者自己写剧本
    for f in extra_faces:
        render(["clothes1_front", f])

    return len(made), skipped


def chapter_sprites(text_path):
    txt = open(text_path, encoding="utf-8").read()
    return sorted(set(re.findall(r"\[立绘：(syq_[^\]]+)\]", txt)))


def build_title_and_ui(ui_root, dst_dir):
    """标题画面（用原作 logo / 按钮图）和对话框底板。"""
    os.makedirs(dst_dir, exist_ok=True)
    title_src = os.path.join(ui_root, "custom", "title")

    def take(name, w=None, h=None):
        p = os.path.join(title_src, name)
        if not os.path.exists(p):
            return None
        with Image.open(p) as im:
            im = im.convert("RGBA")
            if w:
                h = max(1, int(round(im.height * w / im.width)))
                im = im.resize((w, h), Image.LANCZOS)
            return im

    made = []
    bg = take("titlenew_bg_1.png")
    if bg is not None:
        with open(os.path.join(title_src, "titlenew_bg_1.png"), "rb") as f:
            pass
        # 背景要铺满，用 cover 裁切后不带 alpha
        with Image.open(os.path.join(title_src, "titlenew_bg_1.png")) as im:
            fit_cover(flatten(im.convert("RGBA")), SCREEN_W, SCREEN_H) \
                .save(os.path.join(dst_dir, "title_bg.jpg"), "JPEG",
                      quality=88, optimize=True)
        made.append("title_bg.jpg")

    for out, src, w in [
        ("title_logo.png", "title_logo_a.png", 208),
        ("btn_start.png", "title_menu_start_normal.png", 286),
        ("btn_start_on.png", "title_menu_start_click.png", 286),
        ("btn_continue.png", "title_menu_continue_normal.png", 286),
        ("btn_continue_on.png", "title_menu_continue_click.png", 286),
        ("btn_continue_lock.png", "title_menu_continue_locked.png", 286),
        ("btn_gallery.png", "title_menu_gallery_normal.png", 286),
        ("btn_gallery_on.png", "title_menu_gallery_click.png", 286),
        ("btn_system.png", "title_menu_system_normal.png", 286),
        ("btn_system_on.png", "title_menu_system_click.png", 286),
        ("btn_load.png", "title_menu_load_normal.png", 240),
        ("btn_load_on.png", "title_menu_load_click.png", 240),
    ]:
        im = take(src, w)
        if im is None:
            continue
        im.save(os.path.join(dst_dir, out), "PNG", optimize=True)
        made.append(out)

    # 对话框底板：向上渐隐 + 顶部一条粉色高光
    box_h = 168
    tb = Image.new("RGBA", (SCREEN_W, box_h), (0, 0, 0, 0))
    px = tb.load()
    for y in range(box_h):
        t = y / float(box_h - 1)
        a = int(round(255 * (0.30 + 0.62 * (t ** 0.55))))
        for x in range(SCREEN_W):
            px[x, y] = (10, 8, 20, a)
    for x in range(SCREEN_W):
        for y in range(2):
            px[x, y] = (240, 150, 200, 235)
    tb.save(os.path.join(dst_dir, "textbox.png"), "PNG", optimize=True)
    made.append("textbox.png")

    # 浮层底板
    pn = Image.new("RGBA", (SCREEN_W, SCREEN_H), (8, 6, 16, 238))
    pn.save(os.path.join(dst_dir, "panel.png"), "PNG", optimize=True)
    made.append("panel.png")

    # 名字条
    nb = Image.new("RGBA", (168, 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(nb)
    d.rounded_rectangle([0, 0, 167, 33], radius=17,
                        fill=(206, 88, 152, 235),
                        outline=(255, 200, 230, 255), width=2)
    nb.save(os.path.join(dst_dir, "namebox.png"), "PNG", optimize=True)
    made.append("namebox.png")

    # 应用图标 192x192：从 smile 半身像上截脸部，衬粉色底
    sp = os.path.join(dst_dir, "..", "sprite",
                      "clothes1_front_skin_blush_bare_smile.png")
    if os.path.exists(sp):
        with Image.open(sp) as im:
            im = im.convert("RGBA")
            side = int(im.width * 0.86)
            box = ((im.width - side) // 2, int(im.height * 0.04),
                   (im.width + side) // 2, int(im.height * 0.04) + side)
            face = im.crop(box).resize((192, 192), Image.LANCZOS)
        icon = Image.new("RGBA", (192, 192), (58, 34, 62, 255))
        icon.alpha_composite(face)
        icon.save(os.path.join(dst_dir, "icon.png"), "PNG", optimize=True)
        made.append("icon.png")

    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="解包")
    ap.add_argument("--fg", default="原始解包/images_rpa/images/fg")
    ap.add_argument("--rpyc", default="原始解包/scripts_rpa/scripts/roles/syq.rpyc")
    ap.add_argument("--ui", default="解包/界面素材")
    ap.add_argument("--out", default="band-galgame/src/assets")
    ap.add_argument("--chapters", nargs="*",
                    default=["script", "part2", "part3", "part4", "extra1"])
    ap.add_argument("--quality", type=int, default=82)
    args = ap.parse_args()

    print("== 背景 ==")
    n = build_backgrounds(os.path.join(args.src, "背景"),
                          os.path.join(args.out, "bg"), args.quality)
    print("   %d 张 -> %sx%s JPEG" % (n, SCREEN_W, SCREEN_H))

    print("== CG ==")
    n = build_cg(os.path.join(args.src, "CG"), os.path.join(args.out, "cg"),
                 args.quality)
    print("   %d 张" % n)

    print("== 立绘 ==")
    wanted = []
    for ch in args.chapters:
        p = os.path.join(args.src, "对话", "中文", ch + ".txt")
        if os.path.exists(p):
            wanted += chapter_sprites(p)
    wanted = sorted(set(wanted))
    print("   剧本用到 %d 种" % len(wanted))

    all_faces = ["smile", "cry", "astonished", "bewilderment", "blush",
                 "cachinnation", "cat_mouth", "despise", "pout", "wink",
                 "wrath", "black", "shy", "smile_close", "laugh_open",
                 "surprised_but", "focus", "calm", "eyes_closed", "not_good"]
    n, skipped = build_sprites(args.fg, args.rpyc,
                               os.path.join(args.out, "sprite"), wanted, all_faces)
    print("   %d 张半身像" % n)
    if skipped:
        print("   跳过（无对应图层）: %s" % skipped[:5])

    print("== 标题 / UI ==")
    made = build_title_and_ui(args.ui, os.path.join(args.out, "ui"))
    print("   %d 个: %s" % (len(made), ", ".join(made)))

    manifest = {}
    for sub in ("bg", "cg", "sprite", "ui"):
        d = os.path.join(args.out, sub)
        manifest[sub] = sorted(os.path.splitext(os.path.basename(p))[0]
                               for p in glob.glob(os.path.join(d, "*")))
    with open(os.path.join(args.out, "_assets.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    total = 0
    for dp, _d, fs in os.walk(args.out):
        for fn in fs:
            total += os.path.getsize(os.path.join(dp, fn))
    print("== 合计 %.1f MB -> %s ==" % (total / 1048576, args.out))


if __name__ == "__main__":
    main()
