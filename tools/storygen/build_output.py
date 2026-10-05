"""Build the organized deliverable from the extracted archives.

Produces:
  解包/立绘/分层原图/...   raw layered sprite PNGs
  解包/立绘/合成立绘/...   assembled sprites
  解包/背景/...            backgrounds
  解包/CG/...              event CGs + SD art
  解包/对话/...            dialogue text
  解包/说明.txt            notes
"""

import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

from compose_sprites import (build_name_map, composite, parse_layeredimage,  # noqa: E402
                             resolve, when_matches)
from extract_script import main as extract_dialogue_main  # noqa: E402

ROOT = "解包"
RAW = "原始解包"
IMG = RAW + "/images_rpa/images"
SCRIPTS = RAW + "/scripts_rpa/scripts/content"


def ensure(path):
    os.makedirs(path, exist_ok=True)


def copy_tree(src, dst, exts, flatten=False):
    n = 0
    for dirpath, _dirs, files in os.walk(src):
        for fn in sorted(files):
            if exts and os.path.splitext(fn)[1].lower() not in exts:
                continue
            target = os.path.join(dst, fn) if flatten else \
                os.path.join(dst, os.path.relpath(os.path.join(dirpath, fn), src))
            ensure(os.path.dirname(target))
            shutil.copy2(os.path.join(dirpath, fn), target)
            n += 1
    return n


def convert_tree_to_png(root):
    """Re-encode every non-PNG image under `root` as PNG, removing the original.

    Lossless: only the container changes, pixel data is preserved.
    """
    exts = {".webp", ".jpg", ".jpeg", ".bmp", ".gif", ".tga", ".avif"}
    n = 0
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            stem, ext = os.path.splitext(fn)
            if ext.lower() not in exts:
                continue
            src = os.path.join(dirpath, fn)
            dst = os.path.join(dirpath, stem + ".png")
            with Image.open(src) as im:
                im.load()
                if im.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                    im = im.convert("RGBA")
                im.save(dst, "PNG", optimize=True)
            os.remove(src)
            n += 1
    return n


def sprite_view(stem):
    """Classify a sprite layer by its file-name prefix.

    The shipped folders are mislabelled (fg/side holds syq_cos_side_*),
    so the name, not the directory, decides the view.
    """
    for view in ("cos_front", "cos_side", "front", "side"):
        if stem.startswith("syq_%s_" % view):
            return view
    return "other"


def copy_sprite_layers(src, dst):
    n = 0
    for dirpath, _dirs, files in os.walk(src):
        for fn in sorted(files):
            if not fn.lower().endswith(".png"):
                continue
            target = os.path.join(dst, sprite_view(os.path.splitext(fn)[0]), fn)
            ensure(os.path.dirname(target))
            shutil.copy2(os.path.join(dirpath, fn), target)
            n += 1
    return n


def main():
    full_matrix = "--full" in sys.argv

    # Rebuild from scratch so stale output never lingers.
    if os.path.isdir(ROOT):
        shutil.rmtree(ROOT)

    print("== 1/5 dialogue ==")
    sys.argv = ["extract_script", "--out", os.path.join(ROOT, "对话")]
    extract_dialogue_main()
    used = json.load(open(os.path.join(ROOT, "对话", "_index.json"), encoding="utf-8"))

    print("\n== 2/5 raw sprite layers ==")
    n = copy_sprite_layers(os.path.join(IMG, "fg"), os.path.join(ROOT, "立绘", "分层原图"))
    print("   %d layer files" % n)

    print("\n== 3/5 backgrounds / CG ==")
    bg_dir = os.path.join(ROOT, "背景")
    cg_dir = os.path.join(ROOT, "CG")
    copy_tree(os.path.join(IMG, "bg"), bg_dir, None, flatten=True)
    copy_tree(os.path.join(IMG, "cg"), cg_dir, None, flatten=False)
    for extra, dst in [("jianbian.png", bg_dir), ("chunbai.jpg", cg_dir)]:
        src = os.path.join(IMG, extra)
        if os.path.exists(src):
            ensure(dst)
            shutil.copy2(src, os.path.join(dst, os.path.basename(src)))
    npng = convert_tree_to_png(bg_dir) + convert_tree_to_png(cg_dir)
    nb = len([p for p in glob.glob(os.path.join(bg_dir, "*")) if os.path.isfile(p)])
    ncg = len([p for p in glob.glob(os.path.join(cg_dir, "**", "*"), recursive=True)
               if os.path.isfile(p)])
    print("   %d backgrounds, %d CG files (%d converted to PNG)"
          % (nb, ncg, npng))

    print("\n== 4/5 composited sprites ==")
    name, group_order, groups = parse_layeredimage(
        RAW + "/scripts_rpa/scripts/roles/syq.rpyc")
    name_map = build_name_map(os.path.join(IMG, "fg"))

    face_attrs = []
    for e in groups["face"]:
        if e.attr not in face_attrs:
            face_attrs.append(e.attr)
    skin_attrs = []
    for e in groups["skin"]:
        if e.attr not in skin_attrs:
            skin_attrs.append(e.attr)
    feet_attrs = []
    for e in groups["feet"]:
        if e.attr not in feet_attrs:
            feet_attrs.append(e.attr)
    postures = [p for p in ("clothes1_front", "clothes1_side", "clothes2_front")]

    # Collect the attribute sets to render.
    wanted = {}

    def add(req, tag):
        chosen, full = resolve(groups, group_order, req)
        if chosen is None:
            return
        for e in chosen.values():
            if e.image and e.image not in name_map:
                return
        key = tuple(sorted(chosen[g].attr for g in chosen))
        if key not in wanted:
            wanted[key] = (chosen, full, tag)

    # (a) full expression sheet per posture, at the default skin/feet
    for p in postures:
        for f in face_attrs:
            add([p, f], "表情全集")

    # (b) skin / feet variants
    for s in skin_attrs:
        add(["clothes1_front", "smile", s], "皮肤变体")
    for ft in feet_attrs:
        add(["clothes1_front", "smile", ft], "足部变体")

    # (c) every combination the game actually shows
    for s in used["sprites"]:
        if not s.startswith("syq_"):
            continue
        attrs = s[len("syq_"):].split()
        add(attrs, "游戏内实际使用")

    # (d) optionally the complete cross product
    if full_matrix:
        for p in postures:
            for s in skin_attrs:
                for ft in feet_attrs:
                    for f in face_attrs:
                        add([p, s, ft, f], "全组合")

    print("   %d unique sprites to render" % len(wanted))

    outroot = os.path.join(ROOT, "立绘", "合成立绘")
    manifest = []
    for i, (key, (chosen, full, tag)) in enumerate(sorted(wanted.items()), 1):
        img, used_layers = composite(chosen, name_map, group_order)
        if img is None:
            continue
        base = chosen.get("clothes_posture")
        view = "front"
        if base and base.image and base.image.startswith("syq_"):
            view = base.image[len("syq_"):-len("_base")] or "front"
        # Name as <clothes_posture>_<skin>_<feet>_<face>, dropping absent groups.
        parts = [chosen[g].attr for g in
                 ("clothes_posture", "skin", "feet", "face") if g in chosen]
        fn = "%s.png" % "_".join(parts)
        dest = os.path.join(outroot, view, fn)
        ensure(os.path.dirname(dest))
        img.save(dest)
        manifest.append({"file": os.path.relpath(dest, ROOT), "view": view,
                         "layers": [{"group": g, "attr": e.attr, "image": e.image}
                                    for g, e in ((g, chosen.get(g)) for g in group_order) if e],
                         "tag": tag})
        if i % 25 == 0:
            print("      %d/%d" % (i, len(wanted)), flush=True)

    with open(os.path.join(ROOT, "立绘", "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("   wrote %d composites" % len(manifest))

    print("\n== 5/5 notes ==")
    ngui = copy_tree(os.path.join(RAW, "images_rpa", "gui"),
                     os.path.join(ROOT, "界面素材"), None, flatten=False)
    print("   %d GUI assets" % ngui)
    write_readme(manifest, nb, ncg, n, used, ngui)


def write_readme(manifest, nb, ncg, nl, used, ngui):
    lines = []
    A = lines.append
    A("《小小的身影，重叠的内心》 / Tiny Shadows, Interwoven Hearts")
    A("素材解包说明")
    A("=" * 60)
    A("")
    A("游戏引擎：Ren'Py 8.6.0   (Windows 版)")
    A("解包来源：game/images.rpa、game/scripts.rpa")
    A("")
    A("目录结构")
    A("-" * 60)
    A("立绘/")
    A("  分层原图/            立绘原始分层 PNG（%d 个，含透明通道，画布 2284x3586）" % nl)
    A("      front/           正面（便服）")
    A("      side/            侧面（便服）")
    A("      cos_front/       制服·正面")
    A("      cos_side/        制服·侧面")
    A("  合成立绘/            按游戏内 layeredimage 规则拼合后的完整立绘（%d 张）" % len(manifest))
    A("      front/ side/ cos_front/")
    A("  _manifest.json       每张合成立绘由哪些图层构成")
    A("")
    A("注：原包中 front/side/cos_front/cos_side 四个文件夹名与实际文件名前缀")
    A("    并不对应（例如 fg/side/ 里放的是 syq_cos_side_*.png），本目录已按")
    A("    文件名前缀重新归类。")
    A("")
    A("背景/                  场景背景（%d 个，PNG）" % nb)
    A("CG/                    剧情 CG 与 SD Q 版图（%d 个，PNG）" % ncg)
    A("界面素材/              标题 / 存档 / 设置 / 回想等 UI 图（%d 个，附带）" % ngui)
    A("对话/")
    A("  中文/                游戏原始语言（简体中文）")
    A("    script.txt         序章 / 第一章")
    A("    part2.txt~part4.txt 后续章节")
    A("    end.txt extra1.txt 结局与后日谈")
    A("    全部对话.txt       全部章节合并")
    A("  日语/                日文版翻译（结构与中文一致）")
    A("  _index.json          出现过的立绘与背景清单")
    A("")
    A("立绘构成规则（取自 scripts/roles/syq.rpyc）")
    A("-" * 60)
    A("立绘是 layeredimage，按声明顺序由 4 组图层从下往上叠加：")
    A("  1. skin            皮肤：skin_blush(默认) / skin_base / skin_shy / skin_black")
    A("  2. feet            足部：bare(默认) / white_silk / black_silk")
    A("  3. clothes_posture 身体与服装（最底层的主体）：")
    A("       clothes1_front 正面  = syq_front_base")
    A("       clothes1_side  侧面  = syq_side_base")
    A("       clothes2_front 制服正面 = syq_cos_front_base")
    A("  4. face            表情（21 种）")
    A("       smile(默认) cry astonished bewilderment blush cachinnation")
    A("       cat_mouth despise pout wink wrath black shy smile_close")
    A("       laugh_open surprised_but focus calm eyes_closed not_good mask")
    A("     mask 仅适用于制服正面（cos_front）。")
    A("")
    A("合成立绘文件名 = clothes_posture_skin_feet_face，例如：")
    A("  clothes1_front_skin_blush_bare_smile.png")
    A("")
    A("注意：游戏内显示时对 syq_ 使用了")
    A("  Transform(yzoom=0.45, xzoom=-0.45, yoffset=700)")
    A("即水平镜像并缩放到 45%，因此游戏里看到的立绘是左右翻转的小图。")
    A("本目录保存的是未镜像、未缩放的原始分辨率完整立绘。")
    A("")
    A("角色名对照（scripts/roles/role.rpyc）")
    A("-" * 60)
    for var, name in [("e", "苏幼晴"), ("l", "林默"), ("s", "？？？")]:
        A("  %-10s %s" % (var, name))
    A("  其余：服务员 / 摊主 A / 摊主 B / 路人甲 / 大叔 / 店员 / 同事A /")
    A("        主管 / 王总 / 陈总 / 付费留言 / 弹幕 / 月染酱 / 年轻画师 /")
    A("        阿宅甲~丁 / 工作人员")
    A("")
    A("对话统计")
    A("-" * 60)
    A("  中文：")
    total = 0
    for ch in used["chapters"]:
        A("    %-20s %4d 句" % (ch["file"], ch["say_lines"]))
        total += ch["say_lines"]
    A("    %-20s %4d 句" % ("合计", total))
    ja = used.get("japanese_chapters") or []
    if ja:
        A("  日语：")
        tja = 0
        for ch in ja:
            A("    %-20s %4d 句" % (ch["file"], ch["say_lines"]))
            tja += ch["say_lines"]
        A("    %-20s %4d 句" % ("合計", tja))
    A("")
    A("对话中的 [场景：]/[立绘：]/[跳转 → ...] 等方括号内容为依据脚本还原的演出指示，")
    A("不是对白文本。日语版按对白编号与中文逐句对齐；若某句编号在日文包里")
    A("不存在（原文改过但译文未同步，游戏运行时同样会回落到中文），会标为")
    A("［未翻訳］并附上中文原文。")
    A("")
    A("其他")
    A("-" * 60)
    A("  本目录下所有图片均为 PNG。原包里背景与 CG 是 WebP（另有 1 张 jpg），")
    A("  已无损转成 PNG（只换容器，像素数据不变），因此文件体积比原包大。")
    A("")
    A("  游戏源文件与未经转换的原始图片（.rpyc 脚本、WebP / jpg）保存在")
    A("  同级目录 原始解包/ 中。")
    A("")
    A("未包含：音频（game/audio.rpa，1525 个文件，约 324 MB）、字体")
    A("（game/fonts.rpa）、歌词（game/lyrics.rpa）—— 如需可另行解包。")

    with open(os.path.join(ROOT, "说明.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
