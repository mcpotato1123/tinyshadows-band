"""扫一遍转换后的剧本，找画面状态和演出对不上的地方。

移植版的层序是固定的：背景 -> 立绘 -> CG。Ren'Py 不是这样，
它是一条「画面栈」：`scene` 清空栈，`show` 往栈上追加。两者的差异会表现为：

  A. 立绘跨场景残留
     `show syq_ ...` 之后来一个 `scene bg_x`（没跟 show），
     Ren'Py 会把立绘一起清掉，移植版只换背景、立绘还挂着 —— 于是
     「立绘和背景对不上号」：对话已经换地方了，人还站在那。

  B. 立绘被 CG 盖住
     `scene cg_x` 之后再 `show syq_ ...`，Ren'Py 里立绘是压在 CG 上的
     （后 show 的在栈顶），移植版里 CG 层在立绘之上，人就被盖没了。

  C. 纯黑画面（bg/cg 都是 -1）是正常的，`scene black` 就长这样，不计。

判定要区分「同一个节点上既换背景又给立绘」（合法，脚本就是 scene 完立刻 show）
和「换了背景、之后好几句都没有再动立绘」（残留）。

用法: python tools/audit_stage.py [工程目录]
"""

import glob
import json
import os
import sys


def load(proj):
    src = os.path.join(proj, "src")
    idx = json.load(open(os.path.join(src, "common", "story", "index.txt"),
                         encoding="utf-8"))
    nodes = []
    for c in idx["chunks"]:
        p = os.path.join(src, c["file"].replace("/common/", "common/"))
        nodes += json.load(open(p, encoding="utf-8"))
    img = json.loads(open(os.path.join(src, "common", "assets.js"),
                          encoding="utf-8").read()
                     .split("export const IMG = ")[1].split("\n]")[0] + "\n]")
    return nodes, img


def short(img, cs):
    return ",".join(img[c["i"]].split("/")[-1][:-4] for c in cs)[:34]


def main():
    proj = sys.argv[1] if len(sys.argv) > 1 else "tinyshadows-band"
    nodes, img = load(proj)

    bg, cg, cs = -1, -1, []
    scenes_since_cs = 0        # 距离「立绘最后一次变化」经过了几次 scene
    cg_since_cs = False
    a_list, b_list = [], []

    for i, n in enumerate(nodes):
        set_bg = "bg" in n
        set_cg = "cg" in n
        set_cs = "cs" in n

        if set_bg:
            bg = n["bg"]
            cg = -1
            if not set_cs:
                scenes_since_cs += 1
        if set_cg:
            cg = n["cg"]
            if cg >= 0 and not set_cs:
                cg_since_cs = True
        if set_cs:
            cs = n["cs"]
            scenes_since_cs = 0
            cg_since_cs = False

        if n["t"] != "s" or not cs:
            continue
        text = (n.get("x") or "")[:24]

        # A：换过场景、之后一直没再动立绘 —— 立绘应该已经被 scene 清掉了
        if scenes_since_cs > 0:
            a_list.append((i, text, bg, cs, scenes_since_cs))
        # B：CG 之后才 show 的立绘 —— 应该压在 CG 上面，现在被盖住
        if cg >= 0 and cg_since_cs:
            b_list.append((i, text, cg, cs))

    print("节点 %d，说白 %d" % (len(nodes), sum(1 for n in nodes if n["t"] == "s")))
    print()
    print("A. 立绘跨场景残留：%d 处" % len(a_list))
    for i, text, bgc, csx, k in a_list[:8]:
        print("   #%-5d 换景后第%d句 bg=%-14s cs=%-34s %s"
              % (i, k, img[bgc].split("/")[-1][:-4] if bgc >= 0 else "(黑)",
                 short(img, csx), text))
    print()
    print("B. 立绘被 CG 盖住：%d 处" % len(b_list))
    for i, text, c, csx in b_list[:8]:
        print("   #%-5d cg=%-10s cs=%-34s %s"
              % (i, img[c].split("/")[-1][:-4], short(img, csx), text))
    print()
    print("合计需要处理的画面状态错位：%d 处" % (len(a_list) + len(b_list)))


if __name__ == "__main__":
    main()
