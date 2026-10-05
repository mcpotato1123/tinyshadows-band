"""把《小小的身影，重叠的内心》的素材与剧本，装配成 galgod-band 工程。

做法：以 galgod-band 2.2 的源码为基底（页面、reader.js 全部原样保留），
只替换它下面这几样属于「内容」的东西：

  src/common/img/b/*.png    背景   336x480
  src/common/img/s/*.png    立绘   143x380（galgod 的左/中/右三槽几何）
  src/common/img/c/*.jpg    CG     336x480
  src/common/assets.js      IMG / BG / SP 索引表
  src/common/cglist.js      CGG 鉴赏分组
  src/common/story/*        剧本节点分片 + index.txt
  src/manifest.json         改成本作的包名/名称
  src/pages/about/about.ux  关于页文案

galgod 的剧本是扁平节点数组，资源号即 IMG 下标，bg/cg/cs 都挂在对白节点上
表示「从这句开始画面变成这样」，所以转换时要把画面变更攒到下一句对白上。
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

from band_assets import face_bbox, sprite_key  # noqa: E402
from compose_sprites import (build_name_map, composite,  # noqa: E402
                             parse_layeredimage, resolve as resolve_attrs)
from extract_script import find_nodes  # noqa: E402
from export_band_script import Exporter, load_rpyc, make_resolver  # noqa: E402
from rpyc_dump import slots_of  # noqa: E402
from rpyc_expr import expr_text  # noqa: E402

CHUNK = 128
VER = "1.0.0"
APP_NAME = "小小的身影，重叠的内心"
W, H = 336, 480                 # 小米手环 9 Pro 屏幕（designWidth 336 → 1px = 1 物理像素）
# CG 按屏幕尺寸出图（336x480）。原作 CG 是 16:9 的宽图，这里做居中裁切。
# （曾经出过 854x480 的完整 16:9 配拖动查看，后来去掉了滑动，就一并回到屏幕尺寸。）
LOGO_W = 288                    # 标题页 logo 的显示宽度
SPRITE_W, SPRITE_H = 143, 380   # game.ux 里 .sp 的槽位尺寸
# 立绘取景：以脸为中心，脸顶距画面上沿的比例
CROP_W = 714
FACE_TOP_RATIO = 0.13

# 服装 / 姿势组：剧本里显式给出时不要再用默认值覆盖
POSTURES = {"clothes1_front", "clothes1_side", "clothes2_front", "clothes2_side"}
# layeredimage 的 feet 组：裸足 / 白丝 / 黑丝。原作的 syq_adjuster 会按
# persistent.stockings_color 在运行期注入其中之一，所以三种都要出图。
FEET_ALL = ["bare", "white_silk", "black_silk"]

# 便服正面的全套表情，用来给作者留出写新桥段的空间
ALL_FACES = ["smile", "cry", "astonished", "bewilderment", "blush",
             "cachinnation", "cat_mouth", "despise", "pout", "wink",
             "wrath", "black", "shy", "smile_close", "laugh_open",
             "surprised_but", "focus", "calm", "eyes_closed", "not_good"]

CHAPTER_TITLES = {
    "script": "序章 · 咖啡厅的小小身影",
    "part2": "第一章 · 漫展与骤雨",
    "part3": "第二章 · 丝袜与心事",
    "part4": "第三章 · 渐近的距离",
    "end": "尾声 · 春白",
    "extra1": "后日谈 · 小小的未来",
}

# CG 鉴赏分组：按「该 CG 第一次出现在哪一章」归档，这样分组名一定是准的
CG_GROUPS = []

# CG 鉴赏页的分组名要短（分组标签位置很窄），这里单独给一套
CHAPTER_SHORT = {
    "script": "序章",
    "part2": "第一章",
    "part3": "第二章",
    "part4": "第三章",
    "end": "尾声",
    "extra1": "后日谈",
}

# CG 鉴赏分组名。原作画廊的按钮只有 id（cg1…cg6 / SD1 / SD2），没有标题，
# 这几个名字是按每组代表性 CG 的画面起的。
GALLERY_NAMES = {
    "cg1": "草地",
    "cg2": "咖啡厅",
    "cg3": "漫展",
    "cg4": "脚边特写",
    "cg5": "丝袜差分",
    "cg6": "卧床",
    "SD2": "Q版 · 被窝",
    "SD1": "Q版",
    "chunbai": "尾声",
}

# 原作画廊没收录、但本作剧情里出现过的图，按前缀并进最近的组
GALLERY_EXTRA = {
    "cg21": "cg2", "cg22": "cg2",
    "cg32": "cg3",
    "SD12": "SD1", "SD13": "SD1", "SD14": "SD1", "SD15": "SD1",
    "SD20": "SD2", "SD21": "SD2",
}

# 关于页正文（替换 galgod 原本的 GalGod 介绍）。's' 小节标题 / 'p' 正文 / 'g' 空行
MY_ABOUT = [
    ["s", "故事梗概"],
    ["p", "周六下午的咖啡馆，林默在平时「专属」的座位上，遇见了一个趴在桌上用平板画画的小女孩。"],
    ["g", ""],
    ["p", "她叫苏幼晴。看起来只是个初中生，实际上却是网上小有名气的画师兼主播「月染酱」。"],
    ["g", ""],
    ["p", "一支滚落到脚边的触控笔，让两个人第一次说上了话。"],
    ["g", ""],
    ["p", "从咖啡馆到漫展，从直播间到日常的一来一往——小小的身影，一点一点重叠进彼此的生活里。"],
    ["g", ""],
    ["s", "本移植版"],
    ["p", "这是把原作《小小的身影，重叠的内心》移植到小米手环 9 Pro 上的个人版本。"],
    ["g", ""],
    ["p", "引擎与界面直接使用开源项目 galgod-band（MIT 协议），未作改动；本版本提供的是剧本、立绘、背景与 CG。"],
    ["g", ""],
    ["p", "全篇 2503 句对白、3 处分支选择，含真结局与一个「擦肩而过」的分支。"],
    ["g", ""],
    ["p", "结构上分为「本篇」与「后日谈」两部分。默认不提供章节选择，走完真结局之后，标题页才会出现「章节」按钮，可以自由选择重看本篇或后日谈。"],
    ["g", ""],
    ["p", "丝袜差分总共有三套：裸足、白丝、黑丝。剧情里会问到你的偏好，立绘和 CG 都会跟着变；CG 鉴赏里点开「丝袜差分」那一组，用底部的‹ ›可以把三套都翻出来看。"],
    ["g", ""],
    ["p", "操作：轻触推进对白，长按呼出阅读菜单。菜单里可以存档、读档、跳到下一章、切换自动/快速播放，也可以随时回到主页。"],
    ["g", ""],
    ["p", "在设置里可以无级调节正文字号与打字机速度，排版会按当前字号即时重排。"],
    ["g", ""],
    ["s", "版权信息"],
    ["p", "本应用为非官方、非商业性的个人移植作品，与小米（Xiaomi）无关联，亦未获其授权或认可。"],
    ["g", ""],
    ["p", "剧本文字与全部美术资源（背景 / 立绘 / CG）版权归原作《小小的身影，重叠的内心》及其开发方所有。"],
    ["g", ""],
    ["p", "引擎与界面代码来自开源项目 galgod-band，版权归其作者所有，基于 MIT 协议使用。"],
    ["g", ""],
    ["p", "素材仅用于学习与交流，请勿用于任何商业用途。如有侵权，请联系删除。"],
    ["g", ""],
    ["s", "开源协议"],
    ["p", "galgod-band 的代码基于 MIT 协议开源，详见 galgod-band 仓库根目录的 LICENSE 文件。"],
    ["g", ""],
    ["p", "Copyright (c) 2026 The GalGod Band Project Contributors"],
]


def sub(s, old, new, what=''):
    """带保护的字符串替换。

    换 galgod 基线版本（比如 2.2 -> 2.3）时，页面结构一变，
    s.replace(旧, 新) 匹配不上就会**静默不生效** —— 页面看着能跑，
    但补丁其实没打上（标题没换、按钮没藏）。所以这里直接报错。
    """
    if old not in s:
        head = old.strip().splitlines()[0][:88] if old.strip() else '(空)'
        rows = [r for r in old.splitlines() if r.strip()][:3]
        head = ' \\\\ '.join(r[:96] for r in rows) if rows else '(空)'
        raise SystemExit('✖ 页面补丁锚点失效%s：%s\\n'
                         '  galgod 基线版本变了，需要更新 tools/build_galgod_port.py 里的锚点。'
                         % (('（' + what + '）') if what else '', head))
    return s.replace(old, new, 1)


def patch_pages(dst_pages, ver):
    """替换页面里属于「作品内容」的文案，引擎与版式保持 galgod 原样。"""
    done = []

    # 标题页：用原作的大 logo 图当标题，「章节」按钮通关前不显示
    p = os.path.join(dst_pages, "index", "index.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        s = sub(s, 
            '      <text class="title">GalGod</text>\n'
            '      <text class="sub">想成为Galgame领域大神！！！</text>\n',
            '      <image class="logo" src="/common/logo.png"></image>\n',
            "标题-换成logo图")
        # 标题文字样式换成 logo 图的尺寸
        s = sub(s, 
            "  .sub { font-size: 17px; color: #d6bcc8; margin-top: 6px; }",
            "  .logo { width: %dpx; height: %dpx; }"
            % (LOGO_W, int(round(LOGO_W * 1527 / 3059))),
            "标题-logo样式")
        # 原作只有本篇与后日谈，所以默认不给章节选择：
        # 走完真结局（cleared）之后才出现「章节」按钮。
        s = sub(s, 
            '<div class="btn btn-5" onclick="openChapters" onswipe="ban">',
            '<div class="btn btn-5" if="{{cleared}}" onclick="openChapters" onswipe="ban">')
        s = sub(s, "import { loadAutoSave } from '../../common/reader.js'",
                      "import { loadAutoSave, loadCleared } from '../../common/reader.js'")
        s = sub(s, "    hasAuto: false,\n    autoText: ''",
                      "    hasAuto: false,\n    autoText: '',\n    cleared: false")
        s = sub(s, "  refresh() {\n    loadAutoSave((d) => {",
                      "  refresh() {\n    loadCleared((ok) => { this.cleared = ok })\n"
                      "    loadAutoSave((d) => {")
        # 两篇的结构下「第N章」不好看，直接显示篇名
        s = sub(s, "this.autoText = '第' + ((d.chapter || 0) + 1) + '章'",
                      "this.autoText = (d.chapter === 1 ? '后日谈' : '本篇')")
        open(p, "w", encoding="utf-8").write(s)
        done.append("index")

    # 阅读菜单：同样把「章节」藏起来；藏起来时 CG 占满整行，避免留半行空位
    p = os.path.join(dst_pages, "game", "game.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        old_row = ('      <div class="mrow">\n'
                   '        <div class="mbtn mbtn-half" onclick="goChapters" '
                   'onswipe="blockSwipe"><text class="mbtn-t">章节</text></div>\n'
                   '        <div class="mbtn mbtn-half" onclick="goCg" '
                   'onswipe="blockSwipe"><text class="mbtn-t">CG</text></div>\n'
                   '      </div>\n')
        new_row = ('      <div class="mrow" if="{{showChapters}}">\n'
                   '        <div class="mbtn mbtn-half" onclick="goChapters" '
                   'onswipe="blockSwipe"><text class="mbtn-t">章节</text></div>\n'
                   '        <div class="mbtn mbtn-half" onclick="goCg" '
                   'onswipe="blockSwipe"><text class="mbtn-t">CG</text></div>\n'
                   '      </div>\n'
                   '      <div class="mbtn" if="{{!showChapters}}" onclick="goCg" '
                   'onswipe="blockSwipe"><text class="mbtn-t">CG</text></div>\n')
        if old_row in s:
            s = sub(s, old_row, new_row)
        else:
            done.append("game(章节按钮未匹配!)")
        # 只有两篇，「跳到下一章」在通关前等于直接跳去后日谈（剧透），
        # 所以和章节按钮一起解锁
        s = sub(s, 
            '      <div class="mbtn" onclick="nextChapter" onswipe="blockSwipe">',
            '      <div class="mbtn" if="{{showChapters}}" onclick="nextChapter" '
            'onswipe="blockSwipe">')
        s = sub(s, "    autoOn: false,\n    fastOn: false",
                      "    autoOn: false,\n    fastOn: false,\n    showChapters: false")
        s = sub(s, "loadCleared((ok) => { this.cleared = ok })",
                      "loadCleared((ok) => { this.cleared = ok; "
                      "this.showChapters = !!ok })")
        open(p, "w", encoding="utf-8").write(s)
        if "game(章节按钮未匹配!)" not in done:
            done.append("game")

    # 章节页：条目现在叫「本篇 / 后日谈」，副标题的「章」要跟着改成「篇」
    p = os.path.join(dst_pages, "chapters", "chapters.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        if "共 {{count}} 章" in s:
            s = sub(s, "共 {{count}} 章", "共 {{count}} 篇")
            open(p, "w", encoding="utf-8").write(s)
            done.append("chapters")

    # CG 鉴赏：解锁判定改成「该组任意一张差分看过就算解锁」。
    # 原作画廊就是这个语义（renpy/common/00gallery.rpy 的 __GalleryButton.check_unlock
    # 对每张图取 check_unlock，任一张通过即解锁），而且 unlocked_advance 默认 False，
    # 所以解锁之后可以把这一组的差分全部翻一遍。
    # 原作按 g.u（组内第一张）判解锁的话，选了黑丝就看不到白丝那组了。
    p = os.path.join(dst_pages, "cg", "cg.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        if "anySeen(g)" not in s:
            s = sub(s, 
                "  ban() {},\n  lock() { this.lockTap = Date.now() },",
                "  ban() {},\n"
                "  lock() { this.lockTap = Date.now() },\n\n"
                "  // 组内任意一张看过就算解锁（差分组只要看到过其中一张，\n"
                "  // 就能把这一组翻完）\n"
                "  anySeen(g) {\n"
                "    const im = g.im || []\n"
                "    for (let i = 0; i < im.length; i++) {\n"
                "      if (this.seen[im[i]]) return true\n"
                "    }\n"
                "    return !!this.seen[g.u]\n"
                "  },")
            s = sub(s, "      const ok = !!this.seen[g.u]",
                          "      const ok = this.anySeen(g)")
            s = sub(s, "    if (!this.seen[g.u]) {",
                          "    if (!this.anySeen(g)) {")
        # 本作**不再给 cg.ux 打任何补丁**：鉴赏页就是 galgod 2.2 的原版——
        # 列表 + 大图 + 底部 ‹ n/N › 翻差分，没有拖动/滑动那一套。
        if "cg" not in done:
            done.append("cg")
        open(p, "w", encoding="utf-8").write(s)

    # 立绘丝袜：原作的 syq_adjuster 按 persistent.stockings_color 决定立绘穿什么。
    # 移植版在 game.ux 里按同一套规则换图（剧本里的 stockings_color 就是那个值）。
    p = os.path.join(dst_pages, "game", "game.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        if "feetIdx(" not in s:
            s = sub(s, 
                "import { IMG } from '../../common/assets.js'",
                "import { IMG, SP_FEET } from '../../common/assets.js'")
            s = sub(s, 
                "  renderSprites(cs) {\n"
                "    let l = '', c = '', r = ''\n"
                "    for (let i = 0; i < cs.length; i++) {\n"
                "      const ch = cs[i]\n"
                "      const src = IMG[ch.i] || ''",
                "  // 立绘的丝袜跟着剧情里的 stockings_color 走，和原作的 syq_adjuster 一致：\n"
                "  // 0 = 裸足 / 1 = 白丝 / 2 = 黑丝，没设定时按裸足。\n"
                "  // 制服（cos）那套把鞋袜画在底图里了，没有 feet 图层，SP_FEET 里查不到，\n"
                "  // 这时原样返回。\n"
                "  feetIdx(i) {\n"
                "    const v = SP_FEET[i]\n"
                "    if (!v) return i\n"
                "    const k = this.flags ? (this.flags.stockings_color || 0) : 0\n"
                "    const n = (k === 1 || k === 2) ? k : 0\n"
                "    return (v[n] === undefined || v[n] < 0) ? i : v[n]\n"
                "  },\n\n"
                "  renderSprites(cs) {\n"
                "    let l = '', c = '', r = ''\n"
                "    for (let i = 0; i < cs.length; i++) {\n"
                "      const ch = cs[i]\n"
                "      const src = IMG[this.feetIdx(ch.i)] || ''")
            # 丝袜设置变了（剧情里选完）就重画一次立绘
            s = sub(s, 
                "        if (node.t === 'f') { this.flags[node.v] = (this.flags[node.v] || 0) + node.n; this.pc++ }\n"
                "        else if (node.t === 'sf') { this.flags[node.v] = node.n; this.pc++ }",
                "        if (node.t === 'f') {\n"
                "          this.flags[node.v] = (this.flags[node.v] || 0) + node.n\n"
                "          if (node.v === 'stockings_color' && this.csRaw) this.renderSprites(this.csRaw)\n"
                "          this.pc++\n"
                "        } else if (node.t === 'sf') {\n"
                "          this.flags[node.v] = node.n\n"
                "          if (node.v === 'stockings_color' && this.csRaw) this.renderSprites(this.csRaw)\n"
                "          this.pc++\n"
                "        }")
            open(p, "w", encoding="utf-8").write(s)
            done.append("game")

    # 屏幕常亮：galgod 2.3 新增（manifest 的 features 里要声明 system.brightness）。
    # 只搬这一项——2.3 的 game.ux 另一处改动是「全景背景」，本作明确不要。
    p = os.path.join(dst_pages, "game", "game.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        if "setKeepScreenOn(" not in s:
            s = sub(s, "import { IMG, SP_FEET } from '../../common/assets.js'\n",
                    "import { IMG, SP_FEET } from '../../common/assets.js'\n"
                    "import brightness from '@system.brightness'\n",
                    "常亮-导入")
            # 用不依赖缩进的短锚点：onInit 的这几行在 try 里，缩进比 onShow 深一层，
            # 多行锚点容易对齐错。
            s = sub(s, "' auto=' + s.auto + ' fast=' + s.fast)",
                    "' auto=' + s.autoMs + ' fast=' + s.fast + ' keepOn=' + s.keepOn)",
                    "常亮-日志")
            s = sub(s, "        this.bootstrap()",
                    "        this.applyScreenKeepOn()\n        this.bootstrap()",
                    "常亮-onInit")
            s = sub(s, "      this.fastOn = !!s.fast\n"
                       "      this.applyFont()\n"
                       "    })",
                    "      this.fastOn = !!s.fast\n"
                    "      this.applyFont()\n"
                    "      this.applyScreenKeepOn()\n"
                    "    })",
                    "常亮-onShow")
            s = sub(s, "  onHide() { this.clearTimers(); this.flushAutoSave(); this.flushSeen() },",
                    "  onHide() {\n"
                    "    this.clearTimers()\n"
                    "    this.setKeepScreenOn(false)   // 离开阅读页就别占着屏幕了\n"
                    "    this.flushAutoSave()\n"
                    "    this.flushSeen()\n"
                    "  },\n\n"
                    "  // ------------------------------------------------------------ 屏幕常亮\n"
                    "  // Vela 用 @system.brightness 的 setKeepScreenOn；manifest 的 features 里\n"
                    "  // 必须声明 system.brightness，否则调用会抛错。\n"
                    "  // 包一层 try/catch：万一某些固件没这个接口，也只是不常亮，不能让阅读崩掉。\n"
                    "  setKeepScreenOn(on) {\n"
                    "    try {\n"
                    "      brightness.setKeepScreenOn({ keepScreenOn: !!on })\n"
                    "    } catch (e) {\n"
                    "      this.log('设置屏幕常亮失败: ' + (e && e.message ? e.message : e))\n"
                    "    }\n"
                    "  },\n"
                    "  applyScreenKeepOn() {\n"
                    "    const s = this.settings || {}\n"
                    "    this.setKeepScreenOn(!!s.keepOn)\n"
                    "  },",
                    "常亮-onHide")
            open(p, "w", encoding="utf-8").write(s)
            done.append("game-keepon")

    # 关于页：正文 + 版本号
    p = os.path.join(dst_pages, "about", "about.ux")
    if os.path.exists(p):
        s = open(p, encoding="utf-8").read()
        s = re.sub(r"const APP_VER = '[^']*'", "const APP_VER = '%s'" % ver, s)
        rows = []
        for kind, text in MY_ABOUT:
            rows.append("  ['%s', '%s'],"
                        % (kind, text.replace("\\", "\\\\").replace("'", "\\'")))
        s = re.sub(r"const ABOUT = \[.*?\n\]",
                   "const ABOUT = [\n" + "\n".join(rows) + "\n]", s, flags=re.S)
        s = sub(s, "GalGod · 小米手环 9 Pro 版 · v",
                      "小小的身影 · 小米手环 9 Pro 版 · v")
        open(p, "w", encoding="utf-8").write(s)
        done.append("about")

    return done

# 原作里指向标题画面的跳转：这条分支是「擦肩而过」的收尾，
# 原作会回标题让玩家重来，移植版给它一张独立的结局卡。
LABEL_ALIAS = {"splashscreen": "__early_end__"}


# ------------------------------------------------------------------ 立绘

def clean_dir(d):
    """重建前清空目录，避免改名/改规则后留下过期的旧图。"""
    if os.path.isdir(d):
        for fn in os.listdir(d):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                os.remove(p)
    os.makedirs(d, exist_ok=True)


def fit_cover(im, w, h):
    """等比缩放并居中裁切，填满 w x h。"""
    s = max(w / im.width, h / im.height)
    nw, nh = max(w, int(round(im.width * s))), max(h, int(round(im.height * s)))
    im = im.resize((nw, nh), Image.LANCZOS)
    return im.crop(((nw - w) // 2, (nh - h) // 2,
                    (nw - w) // 2 + w, (nh - h) // 2 + h))


def save_png8(im, path, keep_alpha=False):
    """存成 PNG8。

    真机上 JPEG 解码不可靠（galgod 的 build.js 会就此告警），所以全部用 PNG；
    再用调色板量化把体积压下来——336x480 这个尺寸下画质差异看不出来。
    """
    if keep_alpha:
        im.convert("RGBA").quantize(colors=255, method=Image.FASTOCTREE) \
            .save(path, "PNG", optimize=True)
    else:
        im.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=256) \
            .save(path, "PNG", optimize=True)


def build_flat(src_dir, out_dir, names, w=336, h=480, finder=None):
    """背景 / CG：从全分辨率原图缩到屏幕尺寸，存 PNG8。"""
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for name in names:
        src = finder(src_dir, name) if finder else None
        if src is None:
            for e in (".png", ".jpg", ".jpeg", ".webp"):
                p = os.path.join(src_dir, name + e)
                if os.path.exists(p):
                    src = p
                    break
        if src is None:
            continue
        with Image.open(src) as im:
            im = im.convert("RGBA")
            if im.getchannel("A").getextrema()[0] < 250:
                # 带透明区的 CG（SD12~15 之类）按 Ren'Py 的 scene 语义压到黑底：
                # scene 会把整个画面层换成这一张，所以透明处露出来的是窗口底色，
                # 而 manifest 的 display.backgroundColor 就是 #000000。
                # 直接 convert("RGB") 丢 alpha 的话，透明像素里存的杂色会露出来
                # （SD15 会变成白底）。
                flat = Image.new("RGB", im.size, (0, 0, 0))
                flat.paste(im, mask=im.getchannel("A"))
                out = flat
            else:
                out = im.convert("RGB")
            save_png8(fit_cover(out, w, h), os.path.join(out_dir, name + ".png"))
        n += 1
    return n


def build_thumbs(cg_dir, out_dir, names, prefix="g"):
    """CG 鉴赏页的缩略图槽是 96x54 横图，这里从竖幅 CG 中央裁一条 16:9 出来。"""
    os.makedirs(out_dir, exist_ok=True)
    out = {}
    for i, name in enumerate(names):
        src = os.path.join(cg_dir, name + ".png")
        if not os.path.exists(src):
            continue
        with Image.open(src) as im:
            im = im.convert("RGB")
            w = im.width
            h = max(1, int(round(w * 54 / 96)))
            top = max(0, min(im.height - h, int(im.height * 0.45 - h / 2)))
            im = im.crop((0, top, w, top + h)).resize((96, 54), Image.LANCZOS)
        fn = "%s%d.png" % (prefix, i)
        im.convert("P", palette=Image.ADAPTIVE, colors=256) \
            .save(os.path.join(out_dir, fn), "PNG", optimize=True)
        out[name] = "/common/img/t/" + fn
    return out


def build_sprites(fg_root, rpyc, out_dir, wanted, extra_faces):
    """按 layeredimage 规则合成 143x380 立绘。

    原作的丝袜不是写在剧本里的：`show syq_ smile` 从来不带 feet 属性，
    是 `syq_adjuster` 按 `persistent.stockings_color` 在运行期注入
    裸足 / 白丝 / 黑丝。移植版要支持「丝袜切换」，就得把三种都出出来，
    再由引擎按当前设置挑一张（见 assets.js 的 SP_FEET）。

    返回 (出图数, {裸足key: [裸足key, 白丝key, 黑丝key]})。
    """
    _name, group_order, groups = parse_layeredimage(rpyc)
    name_map = build_name_map(fg_root)
    boxes = {}
    h = int(round(CROP_W * SPRITE_H / SPRITE_W))
    for view in ("front", "side", "cos_front", "cos_side"):
        bb = face_bbox(name_map, view)
        if not bb:
            continue
        cx = (bb[0] + bb[2]) // 2
        y0 = int(bb[1] - FACE_TOP_RATIO * h)
        boxes[view] = (cx - CROP_W // 2, y0, cx + CROP_W // 2, y0 + h)

    os.makedirs(out_dir, exist_ok=True)
    clean_dir(out_dir)
    made = {}
    variants = {}
    skipped = []

    def emit(chosen):
        key = sprite_key(chosen)
        if key in made:
            return key
        base = chosen.get("clothes_posture")
        view = "front"
        if base and base.image and base.image.startswith("syq_"):
            view = base.image[len("syq_"):-len("_base")] or "front"
        box = boxes.get(view)
        if box is None:
            skipped.append(key)
            return None
        img, _used = composite(chosen, name_map, group_order)
        if img is None:
            skipped.append(key)
            return None
        bust = img.crop(box)
        s = min(SPRITE_W / bust.width, SPRITE_H / bust.height)
        bust = bust.resize((max(1, int(round(bust.width * s))),
                            max(1, int(round(bust.height * s))), ), Image.LANCZOS)
        canvas = Image.new("RGBA", (SPRITE_W, SPRITE_H), (0, 0, 0, 0))
        canvas.alpha_composite(bust, ((SPRITE_W - bust.width) // 2, 0))
        save_png8(canvas, os.path.join(out_dir, key + ".png"), keep_alpha=True)
        made[key] = True
        return key

    reqs = []
    for s in wanted:
        # wanted 是剧本里的原始属性串（"smile" / "shy skin_blush"）
        attrs = s.split()
        if not (set(attrs) & POSTURES):
            attrs = attrs + ["clothes1_front"]
        reqs.append(attrs)
    for f in extra_faces:
        reqs.append(["clothes1_front", f])

    for attrs in reqs:
        chosen, _full = resolve_attrs(groups, group_order, attrs)
        if chosen is None:
            continue
        bare = emit(chosen)
        posture = chosen["clothes_posture"].attr
        skin = chosen["skin"].attr if "skin" in chosen else None
        face = chosen["face"].attr if "face" in chosen else None
        keys = []
        for feet in FEET_ALL:
            req = [posture] + ([skin] if skin else []) + \
                  ([face] if face else []) + [feet]
            ch2, _f2 = resolve_attrs(groups, group_order, req)
            if ch2 is None:
                keys = []
                break                       # 这个姿势没有 feet 图层（制服）
            keys.append(emit(ch2))
        if bare and len(keys) == 3 and all(keys):
            variants[bare] = keys
    if skipped:
        print("      跳过（缺取景框）:", sorted(set(skipped))[:5])
    return len(made), variants


def view_boxes(fg_root):
    name_map = build_name_map(fg_root)
    h = int(round(CROP_W * SPRITE_H / SPRITE_W))
    boxes = {}
    for view in ("front", "side", "cos_front", "cos_side"):
        bb = face_bbox(name_map, view)
        if not bb:
            continue
        cx = (bb[0] + bb[2]) // 2
        y0 = int(bb[1] - FACE_TOP_RATIO * h)
        boxes[view] = (cx - CROP_W // 2, y0, cx + CROP_W // 2, y0 + h)
    return name_map, boxes


# ------------------------------------------------------------------ 剧本

def load_commands(rpyc_dir, chapters, resolver):
    out = {}
    for ch in chapters:
        path = os.path.join(rpyc_dir, ch + ".rpyc")
        if not os.path.exists(path):
            continue
        _d, stmts = load_rpyc(path)
        ex = Exporter(prefix=ch, resolver=resolver, skip_labels={"start"})
        for i, st in enumerate(stmts):
            # 每个 .rpyc 末尾的隐式 return 是文件结束，不是剧情结局
            if type(st).__name__ == "Return" and i == len(stmts) - 1:
                continue
            ex.walk(st)
        # 清掉两类死指令：
        #  - 紧跟 goto 的 return（文件末尾的隐式 return 被跳转挡在后面）
        #  - 紧跟 choice 的 goto（选项节点不会落空，靠 o.j 跳走）
        cmds = []
        for c in ex.out:
            prev = cmds[-1] if cmds else None
            if prev is not None:
                if "end" in c and "goto" in prev:
                    continue
                if "goto" in c and "choice" in prev:
                    continue
            cmds.append(c)
        out[ch] = cmds
    return out


class Builder(object):
    def __init__(self, bg_index, sp_index, cg_index, resolver=None):
        self.nodes = []
        self.bg_index = bg_index
        self.sp_index = sp_index
        self.cg_index = cg_index
        self.resolver = resolver
        self.pending = {}
        self.labels = {}
        self.patches = []
        self.unresolved = set()

    def node(self, n):
        """建节点。所有节点都自动带上还攒着的画面状态。

        这一点是关键：分支块里可能**只有图片切换、没有对白**，比如原作的

            if persistent.stockings_color == 0:
                show cg522
            elif persistent.stockings_color == 1:
                show cg521

        如果状态一直攒着等下一句对白，三个分支就会互相覆盖，最后只剩最后一个
        生效——黑丝/白丝差分就是这么丢掉的。挂到节点上之后，分支里那条 `j`
        会各自带上自己那份状态，只有条件成立、真走到它时才应用。
        """
        if self.pending:
            n.update(self.pending)
            self.pending = {}
        self.nodes.append(n)
        return len(self.nodes) - 1

    def clear_layer(self):
        """对应 Ren'Py 的 `scene`：清空整个画面层。

        Ren'Py 的 `scene X` 是「先把画面栈清空，再 show X」，所以背景之外的
        立绘、CG 都会一起消失。移植版的层序是固定的（背景 -> 立绘 -> CG），
        必须显式把这两层清掉，否则上一幕的立绘会跨场景残留——
        对话已经切到公司了，人还站在咖啡馆里。
        """
        self.pending["cs"] = []
        self.pending["cg"] = -1

    def bg(self, code):
        self.pending["bg"] = self.bg_index.get(code, -1)
        self.pending["cg"] = -1          # 切背景时显式清掉 CG 槽

    def cg(self, code):
        idx = self.cg_index.get(code)
        if idx is None:
            return
        self.pending["cg"] = idx
        self.pending["cs"] = []          # CG 与立绘互斥

    def sp(self, key):
        if not key:
            self.pending["cs"] = []
            return
        # 剧本里存的是原始属性串（"smile" / "shy skin_blush"），
        # 到这里才解析成具体图片名
        k = self.resolver(key) if self.resolver else key
        idx = self.sp_index.get(k if k else key)
        if idx is None:
            self.unresolved.add("sprite:" + str(k or key))
            return
        self.pending["cs"] = [{"k": "syq", "i": idx, "s": "center"}]

    def say(self, who, text):
        self.node({"t": "s", "n": who or "", "x": text})

    def label(self, name):
        self.labels[name] = len(self.nodes)

    def jump(self, label):
        i = self.node({"t": "j", "j": 0})
        self.patches.append((i, "j", label))

    def cj(self, clause, label):
        i = self.node({"t": "cj", "v": clause["n"], "op": clause["o"],
                       "n": clause["v"], "j": 0})
        self.patches.append((i, "j", label))

    def branch(self, clauses, label):
        """条件成立就跳到 label。多个子句按 and 语义串成链。"""
        if not clauses:
            self.jump(label)
            return
        if len(clauses) == 1:
            self.cj(clauses[0], label)
            return
        fail = "__and_fail_%d" % len(self.nodes)
        for cl in clauses[:-1]:
            nxt = "__and_next_%d" % len(self.nodes)
            self.cj(cl, nxt)
            self.jump(fail)
            self.label(nxt)
        self.cj(clauses[-1], label)
        self.jump(fail)
        self.label(fail)

    def choice(self, items):
        opts = []
        ni = len(self.nodes)
        for k, (text, target) in enumerate(items):
            opts.append({"x": text, "j": 0, "c": None})
            self.patches.append((ni, "opt:%d" % (k + 1), target))
        self.node({"t": "o", "o": opts})

    def setflag(self, name, value):
        self.node({"t": "sf", "v": name, "n": value})

    def ending(self, text):
        self.node({"t": "e", "x": text})


def convert(cmds, b):
    for c in cmds:
        # scene 先清层，再应用这一条自己的图片
        if c.get("scene"):
            b.clear_layer()
        if "label" in c:
            b.label(c["label"])
        elif "set" in c:
            for k, v in c["set"].items():
                b.setflag(k, v)
        elif "bg" in c:
            b.bg(c["bg"])
        elif "cg" in c:
            b.cg(c["cg"])
        elif "sp" in c:
            b.sp(c["sp"])
        elif "say" in c:
            b.say(c.get("who"), c["say"])
        elif "goto" in c:
            b.jump(c["goto"])
        elif "gotoIf" in c:
            b.branch(c["gotoIf"]["c"], c["gotoIf"]["to"])
        elif "choice" in c:
            b.choice([(o["t"], o["go"]) for o in c["choice"]])
        elif "end" in c:
            # 剧本里的显式结局：统一交给收尾的真结局节点，
            # 这样通关标记 true_end_finish 一定会被写上
            b.jump("__story_end__")


def resolve(b):
    """把符号 label 补成节点下标。"""
    nodes = b.nodes
    end_pc = len(nodes)
    for i, key, label in b.patches:
        label = LABEL_ALIAS.get(label, label)
        target = b.labels.get(label)
        if target is None:
            b.unresolved.add("jump:" + label)
            target = end_pc
        if key == "j":
            nodes[i]["j"] = target
        elif key.startswith("opt:"):
            n = int(key.split(":")[1]) - 1
            nodes[i]["o"][n]["j"] = target
    return nodes


def write_story(out_dir, nodes, parts):
    """parts: [{"id","title","start","need"?,"hide"?}, ...]"""
    story_dir = os.path.join(out_dir, "common", "story")
    if os.path.isdir(story_dir):
        shutil.rmtree(story_dir)
    os.makedirs(story_dir, exist_ok=True)
    chunks = []
    for i in range(0, len(nodes), CHUNK):
        part = nodes[i:i + CHUNK]
        name = "chunk-%03d.txt" % (i // CHUNK)
        with open(os.path.join(story_dir, name), "w", encoding="utf-8") as f:
            f.write(json.dumps(part, ensure_ascii=False, separators=(",", ":")))
        chunks.append({"file": "/common/story/" + name, "start": i,
                       "count": len(part)})

    index = {"ver": 1, "title": "小小的身影，重叠的内心",
             "nodeCount": len(nodes), "chunkSize": CHUNK, "entry": 0,
             "chapters": parts, "chunks": chunks}
    with open(os.path.join(story_dir, "index.txt"), "w", encoding="utf-8") as f:
        f.write(json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    return len(chunks)


def js_array(items):
    return "[\n" + ",\n".join('  "%s"' % s for s in items) + "\n]"


def js_obj(d):
    return "{\n" + ",\n".join('  "%s": %d' % (k, v) for k, v in d.items()) + "\n}"


def build_branding(ui_root, common):
    """标题画 / 标题 logo / 应用图标：都用原作的标题美术。"""
    title = os.path.join(ui_root, "custom", "title")
    made = []

    p = os.path.join(title, "titlenew_bg_1.png")
    if os.path.exists(p):
        with Image.open(p) as im:
            save_png8(fit_cover(im.convert("RGB"), W, H),
                      os.path.join(common, "home.png"))
        made.append("home.png")

    # 标题页用的是大张的透明 logo（不是 title_logo_a 那张小的）
    p = os.path.join(ui_root, "custom", "LOGO_white.png")
    if os.path.exists(p):
        with Image.open(p) as im:
            im = im.convert("RGBA")
            im = im.resize((LOGO_W, max(1, int(round(im.height * LOGO_W / im.width)))),
                           Image.LANCZOS)
            save_png8(im, os.path.join(common, "logo.png"), keep_alpha=True)
        made.append("logo.png")

    # 应用图标：原作的 gui/window_icon.png（本来就是 250x250 的不透明方图）
    p = os.path.join(ui_root, "window_icon.png")
    if os.path.exists(p):
        with Image.open(p) as im:
            side = min(im.size)
            im = im.convert("RGBA")
            im = im.crop(((im.width - side) // 2, 0,
                          (im.width - side) // 2 + side, side))
            save_png8(im.resize((192, 192), Image.LANCZOS),
                      os.path.join(common, "icon.png"), keep_alpha=True)
        made.append("icon.png")

    return made


def original_gallery(rpyc):
    """从原作的 screens/gallery_screen.rpyc 里解析出画廊分组。

    原作画廊用的是 Ren'Py 内置的 Gallery：
        g.button("cg5")
        g.image("cg512").image("cg510").image("cg511")   # 白丝 / 裸足 / 黑丝
    一个 button 挂多张 image 就是「差分」，点开之后可以左右翻。
    与其我自己拍脑袋分组，不如直接读原作的定义——尤其是丝袜那 12 张。

    Ren'Py 的语义（renpy/common/00gallery.rpy）：
      * 按钮只要**任意一张**差分被看过就解锁；
      * `unlocked_advance` 默认 False，所以解锁后可以翻到没看过的那几张。
    """
    _d, stmts = load_rpyc(rpyc)
    code = ""
    for n in find_nodes(stmts, {"Python", "PyCode"}):
        t = expr_text(slots_of(n).get("code") or n)
        if t and "Gallery()" in t:
            code = t
            break
    groups = []
    cur = None
    for line in code.splitlines():
        line = line.strip()
        m = re.match(r'^g\.button\("([^"]+)"\)', line)
        if m:
            cur = {"id": m.group(1), "im": []}
            groups.append(cur)
            continue
        m = re.match(r'^g\.image\("([^"]+)"\)', line)
        if m and cur is not None:
            cur["im"].append(m.group(1))
    return groups


def gallery_name(gid):
    return GALLERY_NAMES.get(gid, gid)


def prune(nodes, marks):
    """删掉不可达节点，并重编号所有跳转目标。

    空的分支块会留下一串永远不会执行的 j 节点。galgod 自带的
    tools/validate_story.py 把「存在不可达节点」判为错误，所以这里清干净。
    """
    n = len(nodes)
    seen = set()
    stack = [0]
    while stack:
        i = stack.pop()
        if i in seen or not (0 <= i < n):
            continue
        seen.add(i)
        node = nodes[i]
        t = node["t"]
        if t == "j":
            stack.append(node["j"])
        elif t == "cj":
            stack.append(node["j"])
            stack.append(i + 1)
        elif t == "o":
            for o in node["o"]:
                stack.append(o["j"])
            stack.append(i + 1)
        elif t != "e":
            stack.append(i + 1)

    order = [i for i in range(n) if i in seen]
    remap = {old: new for new, old in enumerate(order)}
    out = []
    for old in order:
        node = dict(nodes[old])
        if node["t"] in ("j", "cj"):
            node["j"] = remap[node["j"]]
        elif node["t"] == "o":
            node["o"] = [dict(o, j=remap[o["j"]]) for o in node["o"]]
        out.append(node)

    new_marks = []
    for cid, title, start in marks:
        if start in remap:
            new_marks.append((cid, title, remap[start]))
        else:
            nxt = next((o for o in order if o >= start), None)
            new_marks.append((cid, title,
                              remap[nxt] if nxt is not None else len(out)))
    return out, new_marks, n - len(order)


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="galgod-band-ref")
    # 只从 2.3 取这三样：屏幕常亮跨了
    # manifest / reader.js / settings.ux 三个文件。
    # 2.3 对它们的改动**仅限**常亮，所以整份拿来就等于
    # 「2.2 + 常亮」，不必在 2.2 上去手改一堆坐标。
    ap.add_argument("--keepon-ref", default="galgod-band-23")
    ap.add_argument("--out", default="galgod-port")
    ap.add_argument("--rpyc", default="原始解包/scripts_rpa/scripts/content")
    ap.add_argument("--syq", default="原始解包/scripts_rpa/scripts/roles/syq.rpyc")
    ap.add_argument("--fg", default="原始解包/images_rpa/images/fg")
    ap.add_argument("--compose", default="解包/立绘/合成立绘")
    ap.add_argument("--bg-src", default="解包/背景")
    ap.add_argument("--cg-src", default="解包/CG")
    ap.add_argument("--ui", default="解包/界面素材",
                    help="原作界面素材目录（取 custom/title 下的标题画与 logo）")
    ap.add_argument("--chapters", nargs="*",
                    default=["script", "part2", "part3", "part4", "end", "extra1"])
    args = ap.parse_args()

    src = os.path.join(args.ref, "src")
    dst = os.path.join(args.out, "src")
    if not os.path.isdir(src):
        raise SystemExit("找不到 galgod 参考源码: %s" % src)

    # ---- 1. 以 galgod 源码为基底
    # 整棵 common/ 重建，避免改名/改规则后留下过期的旧图
    common = os.path.join(dst, "common")
    if os.path.isdir(common):
        shutil.rmtree(common)
    if os.path.isdir(dst):
        p = os.path.join(dst, "pages")
        if os.path.isdir(p):
            shutil.rmtree(p)
    os.makedirs(dst, exist_ok=True)
    shutil.copy2(os.path.join(src, "app.ux"), os.path.join(dst, "app.ux"))
    shutil.copy2(os.path.join(src, "manifest.json"), os.path.join(dst, "manifest.json"))
    shutil.copytree(os.path.join(src, "pages"), os.path.join(dst, "pages"))
    os.makedirs(common, exist_ok=True)
    shutil.copy2(os.path.join(src, "common", "reader.js"),
                 os.path.join(common, "reader.js"))

    # 屏幕常亮是 2.3 才有的，而它跨了三个文件：manifest 要声明 system.brightness、
    # reader.js 要有 keepOn 这个设置项、settings.ux 要有对应的开关和行距。
    # 2.3 对这三个文件的改动**仅限**常亮，所以整份拿过来即可，不必在 2.2 上
    # 手改一堆滑块坐标。其余一切（含 game.ux）都用 2.2 的。
    copied = []
    kon = os.path.join(args.keepon_ref, "src")
    if os.path.isdir(kon):
        for rel in ("manifest.json", "common/reader.js",
                    "pages/settings/settings.ux"):
            s2 = os.path.join(kon, rel.replace("/", os.sep))
            if os.path.exists(s2):
                shutil.copy2(s2, os.path.join(dst, rel.replace("/", os.sep)))
                copied.append(rel)
    print("[1/5] 复制 galgod %s 引擎与页面（7 个页面 + reader.js）；"
          "另从 %s 取屏幕常亮：%s"
          % (os.path.basename(os.path.normpath(args.ref)),
             os.path.basename(os.path.normpath(args.keepon_ref)),
             "、".join(copied) if copied else "（没找到）"))

    # ---- 2. 素材
    # 先把剧本读出来（只走 AST、不需要资源下标），这样才能知道要用到哪些立绘。
    # 这里用恒等解析器，拿到的 c["sp"] 是原始属性串（"smile"），
    # 真正解析成图片名是在 Builder.sp() 里做的。
    cmds = load_commands(args.rpyc, args.chapters, lambda s: s)
    wanted = set()
    for ch in cmds:
        for c in cmds[ch]:
            if c.get("sp"):
                wanted.add(c["sp"])
    print("      剧本用到 %d 种立绘属性" % len(wanted))

    exts = (".png", ".jpg", ".jpeg", ".webp")

    def collect(root):
        names = []
        for dp, _dirs, files in os.walk(root):
            for f in files:
                if os.path.splitext(f)[1].lower() in exts:
                    names.append(os.path.splitext(f)[0])
        return sorted(set(names))

    def find_src(root, name):
        for dp, _dirs, files in os.walk(root):
            for f in files:
                if os.path.splitext(f)[0] == name and \
                        os.path.splitext(f)[1].lower() in exts:
                    return os.path.join(dp, f)
        return None

    bgs = collect(args.bg_src)
    cgs = collect(args.cg_src)

    for sub, src_dir, names, (tw, th) in (
            ("b", args.bg_src, bgs, (W, H)),
            ("c", args.cg_src, cgs, (W, H))):
        d = os.path.join(common, "img", sub)
        if os.path.isdir(d):
            shutil.rmtree(d)
        build_flat(src_dir, d, names, w=tw, h=th, finder=find_src)

    sp_dir = os.path.join(common, "img", "s")
    nsp, sp_feet = build_sprites(args.fg, args.syq, sp_dir,
                                 sorted(wanted), ALL_FACES)
    sps = sorted(os.path.splitext(f)[0] for f in os.listdir(sp_dir))
    print("[2/5] 素材：背景 %d / 立绘 %d（其中 %d 组有丝袜差分）/ CG %d，全部 PNG8"
          % (len(bgs), nsp, len(sp_feet), len(cgs)))

    # ---- 3. 索引表
    img = []
    bg_index = {"black": -1, "white": -2}
    for name in bgs:
        bg_index[name] = len(img)
        img.append("/common/img/b/%s.png" % name)
    sp_index = {}
    for name in sps:
        sp_index[name] = len(img)
        img.append("/common/img/s/%s.png" % name)
    cg_index = {}
    for name in cgs:
        cg_index[name] = len(img)
        img.append("/common/img/c/%s.png" % name)

    # ---- 3. 剧本（cmds 在素材那一步已经读好，用的是原始属性串）
    b = Builder(bg_index, sp_index, cg_index,
                resolver=make_resolver(args.syq))
    marks = []
    for ch in args.chapters:
        if ch not in cmds:
            continue
        marks.append((ch, CHAPTER_TITLES.get(ch, ch), len(b.nodes)))
        convert(cmds[ch], b)
    # 收尾：主线走完先跳到真结局；悲剧分支（splashscreen）落在「未完待续」卡上。
    b.jump("__story_end__")
    b.label("__early_end__")
    b.ending("—— 未完待续 ——")
    b.label("__story_end__")
    b.setflag("true_end_finish", 1)
    b.ending("—— 小小的身影，重叠的内心 ——")
    nodes = resolve(b)
    nodes, marks, pruned = prune(nodes, marks)

    # 章节选择只给「本篇 / 后日谈」两项（原作就只有这两部分）。
    # marks 仍按文件粒度保留——CG 鉴赏分组要用它算「首次出现在哪一段」。
    # 后日谈标 need=1：通关（走到真结局）之前，chapters.ux 不会把它列出来。
    after_start = next((s for cid, _t, s in marks if cid == "extra1"), len(nodes))
    parts = [{"id": "main", "title": "本篇", "start": 0},
             {"id": "after", "title": "后日谈", "start": after_start, "need": 1}]
    nchunks = write_story(dst, nodes, parts)
    kinds = {}
    for n in nodes:
        kinds[n["t"]] = kinds.get(n["t"], 0) + 1
    print("[3/5] 剧本 %d 节点 / %d 分片 / %d 个章节（本篇 + 后日谈）  节点类型 %s"
          % (len(nodes), nchunks, len(parts), kinds))
    if pruned:
        print("      清理不可达节点 %d 个（空分支块留下的死跳转）" % pruned)
    if b.unresolved:
        print("      未解析的引用:", sorted(b.unresolved)[:10])

    # 每张 CG 第一次出现在哪一篇（只记首次，后面的出现不再重复归档）。
    # 分组跟着章节选择的粒度走，所以用 parts（本篇 / 后日谈），不用文件级的 marks。
    cg_names = {}
    for name in cgs:
        cg_names[cg_index[name]] = name
    cg_first = {}
    cg_done = set()
    for i, n in enumerate(nodes):
        ci = n.get("cg", -1)
        if ci is None or ci < 0 or ci not in cg_names or ci in cg_done:
            continue
        cg_done.add(ci)
        pid = parts[0]["id"]
        for p in parts:
            if i >= p["start"]:
                pid = p["id"]
        cg_first.setdefault(pid, set()).add(cg_names[ci])

    # 剧情里实际出现过的 CG（鉴赏只列这些，否则会有永远解不开的条目）
    used_cg = set()
    for n in nodes:
        ci = n.get("cg", -1)
        if ci is not None and ci >= 0 and ci in cg_names:
            used_cg.add(cg_names[ci])

    # ---- 4. 索引表
    with open(os.path.join(common, "assets.js"), "w", encoding="utf-8") as f:
        f.write("// 由 tools/build_galgod_port.py 自动生成，请勿手改\n")
        f.write("// 图片索引表：下标即剧本节点里的资源号\n")
        f.write("export const IMG = %s\n\n" % js_array(img))
        f.write("// 背景代号 -> 图片下标（-1 纯黑 / -2 纯白）\n")
        f.write("export const BG = %s\n\n" % js_obj(
            {k: v for k, v in sorted(bg_index.items(), key=lambda kv: kv[1])}))
        f.write("// 立绘 key -> 图片下标\n")
        f.write("export const SP = %s\n\n" % js_obj(
            {k: v for k, v in sorted(sp_index.items(), key=lambda kv: kv[1])}))
        f.write("// 立绘丝袜差分：裸足那版的下标 -> [裸足, 白丝, 黑丝] 三个下标。\n")
        f.write("// 原作的 syq_adjuster 会按 persistent.stockings_color 注入 feet 属性，\n")
        f.write("// 移植版在运行时按同一套规则挑一张，见 game.ux 的 feetIdx()。\n")
        feet_lines = []
        for bare, keys in sorted(sp_feet.items(), key=lambda kv: sp_index[kv[0]]):
            feet_lines.append('  "%d": [%s]'
                              % (sp_index[bare],
                                 ", ".join(str(sp_index[k]) for k in keys)))
        f.write("export const SP_FEET = {\n" + ",\n".join(feet_lines) + "\n}\n")

    # 鉴赏分组：直接采用原作 gallery_screen.rpyc 里的 Gallery 结构。
    # 尤其是 cg5 那批丝袜差分（白丝/裸足/黑丝）归在一个按钮下，
    # 打开后就能用 ‹ › 来回翻——这正是原作「差分画像」的用法。
    raw = original_gallery(
        os.path.join(args.rpyc, "..", "screens", "gallery_screen.rpyc"))
    raw = [g for g in raw if g["im"]]
    raw_order = {g["id"]: g["im"] for g in raw}

    # 先决定每张用到的 CG 归哪一组，再丢空组。
    # 反过来的话，原作组里没被本作用到的图会把组掏空，本该并进去的图
    # 就会各自变成一个只有一张的组。
    owner = {}
    for g in raw:
        for m in g["im"]:
            owner.setdefault(m, g["id"])
    for name in used_cg:
        if name not in owner:
            owner[name] = GALLERY_EXTRA.get(name, name)

    order = [g["id"] for g in raw]
    for name in sorted(used_cg):
        if owner[name] not in order:
            order.append(owner[name])

    by_group = {}
    for name in used_cg:
        by_group.setdefault(owner[name], set()).add(name)

    entries = []
    for gid in order:
        have = by_group.get(gid)
        if not have:
            continue
        # 组内顺序：原作定义过的按原作排（cg5 是 白丝/裸足/黑丝 交替），
        # 本作额外用到的追加在后面
        members = [m for m in raw_order.get(gid, []) if m in have]
        members += sorted(have - set(members))
        entries.append((gid, gallery_name(gid), members))

    thumbs = build_thumbs(os.path.join(common, "img", "c"),
                          os.path.join(common, "img", "t"),
                          [e[2][0] for e in entries])
    groups = []
    for gid, title, members in entries:
        groups.append({"n": title,
                       "th": thumbs.get(members[0],
                                        "/common/img/c/%s.png" % members[0]),
                       "u": cg_index[members[0]],
                       "im": [cg_index[m] for m in members]})
    with open(os.path.join(common, "cglist.js"), "w", encoding="utf-8") as f:
        f.write("// 由 tools/build_galgod_port.py 自动生成，请勿手改\n")
        f.write("// 分组取自原作 screens/gallery_screen.rpyc 的 Gallery()；\n")
        f.write("// 一个分组里的多张图是差分，鉴赏页可以用 ‹ › 左右翻。\n")
        f.write("export const CGG = %s\n"
                % json.dumps(groups, ensure_ascii=False, separators=(",", ":")))
    print("[4/5] assets.js（IMG %d 项）/ cglist.js（%d 组，覆盖 %d 张剧情 CG）"
          % (len(img), len(groups), len(used_cg)))
    for g in groups:
        print("        %-10s %2d 张" % (g["n"], len(g["im"])))

    # ---- 5. 标题画 / 图标 / manifest / 页面文案
    made = build_branding(args.ui, common)
    mf = json.load(open(os.path.join(dst, "manifest.json"), encoding="utf-8"))
    mf["package"] = "com.tinyshadows.band"
    mf["name"] = APP_NAME
    mf["versionName"] = VER
    mf["versionCode"] = 1
    mf["display"] = {"backgroundColor": "#000000"}
    with open(os.path.join(dst, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(mf, f, ensure_ascii=False, indent=2)

    patched = patch_pages(os.path.join(dst, "pages"), VER)
    print("[5/5] manifest.json 包名 %s / 名称 %s / 版本 %s；页面文案已替换：%s"
          % (mf["package"], mf["name"], VER, "、".join(patched) or "无"))
    print("完成 -> %s" % args.out)


if __name__ == "__main__":
    main()
