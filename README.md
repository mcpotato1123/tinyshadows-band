# 小小身影 · 小米手环 9 Pro 版

把《小小的身影，重叠的内心》移植到**小米手环 9 Pro** 上的视觉小说工程。

**引擎与界面来自开源项目 [galgod-band](https://github.com/mcpotato1123/galgod-band)（MIT），基线版本 2.3**；
本工程提供的是剧本、立绘、背景、CG 与资源索引，另有少量针对本作的改动（见「与原作的差异」一节）。

![界面预览](preview/ui-preview.png)

- 屏幕 336×480，`designWidth: 336`，所以 CSS 里 **1px = 1 物理像素**，直接按像素写。
- 分为 **本篇** 与 **后日谈** 两部分（和原作一致），共 **2503 句对白**、3 处分支选择、**43 处条件跳转**、2 个结局。
- **默认没有章节选择**：走完真结局后，标题页才会出现「章节」按钮，可自由选择本篇 / 后日谈。
- 背景 25 张、立绘 94 张（含丝袜差分）、CG 40 张（都是屏幕尺寸 336×480），
  **全部 PNG**（真机上 JPEG 解码不可靠，见下文）。
- 构建产物 **5.17 MB**，已实测可打包通过。

---

## 一、打包成 rpk

需要 Node.js（建议 18+）。**首次构建需要能访问 npm registry**（要装 `aiot-toolkit`）。

```bash
npm install          # 只装 aiot-toolkit 与 jsc
npm run build        # → dist/com.tinyshadows.band.debug.1.0.0.rpk
```

> **Windows 上的已知现象**：构建收尾时 `aiot-toolkit` 用 rimraf 删临时工程的
> `node_modules` 软链接会报 `EPERM`，退出码变成 1，还会留下 `.temp_<工程名>` 目录。
> **此时 rpk 其实已经生成好了**。`tools/build.js` 已经处理了这一点（构建前后各清理一次，
> 并把退出码 1 当作成功），只要看到 `✔ 完成` 和 `产物: dist\...rpk` 就是好的。
> 如果残留了 `.temp_<工程名>`，手动删掉即可。

其他脚本：

| 命令 | 作用 |
|---|---|
| `npm run build` | 出 debug 包（可直接侧载，**不需要签名**） |
| `npm run release` | 出 release 包（需要 `sign/` 下的证书） |
| `npm run start` | 起模拟器预览（需要 AIoT-IDE / 模拟器环境） |
| `npm run validate` | 剧本校验：分块、资源引用、跳转、全图可达 |
| `npm test` | 运行时分页测试（字号 14~30 全量） |
| `npm run check` | = validate + test |
| `npm run audit` | 扫画面状态与演出对不上的地方（立绘跨场景残留等） |
| `npm run preview` | 重新渲染 `preview/ui-preview.png`（正文页） |

### 出 release 包

release 需要签名证书：

```bash
mkdir sign
openssl req -newkey rsa:2048 -nodes -keyout sign/private.pem -x509 -days 3650 -out sign/certificate.pem
npm run release
```

---

## 二、安装到手环

以 **Astrobox** 为例（debug 包可以直接侧载，不需要证书）：

1. 把 `dist/` 里的 `*.debug.*.rpk` 传到手机；
2. 打开 Astrobox →【探索】→ `安装快应用`；
3. 找到那个文件（若列表里没有，点**左上角**的菜单图标 → 找手机型号图标 → 打开 Download 目录）。

---

## 三、工程结构

```
galgod-port/
├── src/
│   ├── manifest.json          应用清单：包名 / 名称 / 图标 / 路由 / features / designWidth
│   ├── app.ux                 应用入口
│   ├── pages/                 ← galgod 原版界面，共 7 个页面
│   │   ├── index/             标题页（文案已换成本作标题）
│   │   ├── game/              阅读页：对白、立绘、CG、选项、菜单、打字机
│   │   ├── saves/             存档 / 读档（6 槽 + 自动存档）
│   │   ├── chapters/          章节选择
│   │   ├── cg/                CG 鉴赏
│   │   ├── settings/          字号 / 速度 / 自动播放
│   │   └── about/             关于（正文已换成本作介绍）
│   └── common/
│       ├── reader.js          ← galgod 原版：设置、存档、换行分页
│       ├── assets.js          资源索引表（本工程生成）
│       ├── cglist.js          CG 鉴赏分组（本工程生成）
│       ├── home.png           标题画（原作 titlenew_bg_1）
│       ├── icon.png           应用图标（原作 gui/window_icon.png）
│       ├── logo.png           标题 logo（原作 custom/LOGO_white.png）
│       ├── img/b/             背景 25 张
│       ├── img/s/             立绘 94 张（143×380，含裸足/白丝/黑丝三套）
│       ├── img/c/             CG 40 张
│       ├── img/t/             鉴赏缩略图 8 张（96×54）
│       └── story/             剧本：index.txt + 21 个分片
├── tools/
│   ├── build.js               ← galgod 原版：构建前检查 + 构建包装 + 产物校验
│   ├── validate_story.py      ← galgod 原版：剧本校验器
│   ├── test_paginate.js       ← galgod 原版：分页测试
│   ├── check_encoding.py      ← galgod 原版：编码检查
│   ├── preview_port.py        按 game.ux 的版面几何渲染界面预览图
│   ├── audit_stage.py         扫画面状态与演出对不上的地方
│   └── storygen/              内容转换流水线（见第六节）
├── preview/ui-preview.png     界面预览（正文页）
├── LICENSE                    galgod-band 的 MIT 协议
└── NOTICE.md                  版权说明（引擎 MIT / 素材归原作）
```

---

## 四、剧本数据格式

剧本是**扁平的节点数组**，每 128 个节点切一个分片文件，`story/index.txt` 记录章节与分片索引。
节点里的资源号是 `assets.js` 中 `IMG` 数组的下标。

| 节点 | 含义 |
|---|---|
| `{"t":"s","n":说话人,"x":文本,"bg":背景号,"cg":CG号,"cs":[立绘]}` | 对白。**画面状态挂在节点上**，表示「从这一句开始画面变成这样」，所以背景/立绘会一直保持到下一次改变 |
| `{"t":"o","o":[{"x":选项文字,"j":跳转节点,"c":条件}]}` | 选项。`c` 为 `null` 或 `[变量, 运算符, 值]` |
| `{"t":"j","j":节点号}` | 无条件跳转 |
| `{"t":"cj","v":变量,"op":"==","n":值,"j":节点号}` | **条件跳转**：成立则跳转，否则继续下一条 |
| `{"t":"sf","v":变量,"n":值}` | 给变量赋值 |
| `{"t":"f","v":变量,"n":值}` | 给变量累加 |
| `{"t":"e","x":结局文字}` | 结局画面（轻触返回标题） |

立绘项是 `{"k":"角色码","i":IMG下标,"s":"left|center|right"}`。
`game.ux` 只提供左 / 中 / 右三个立绘槽位（143×380）。

### 资源索引

`src/common/assets.js`：

```js
export const IMG = [ "/common/img/b/xxx.png", ... ]   // 下标即剧本里的资源号
export const BG  = { "black": -1, "white": -2, "bg_coffee_1": 3, ... }
export const SP  = { "clothes1_front_skin_blush_bare_smile": 25, ... }
```

`src/common/cglist.js` 的 `CGG` 是鉴赏分组，按「该 CG 第一次出现在哪一章」归档，
`u` 是解锁所需的 CG 下标，`im` 是该组包含的下标列表。

---

## 五、已做的验证

| 检查 | 工具 | 结果 |
|---|---|---|
| 剧本结构（分块连续、引用不越界、跳转合法、**全图可达**、资源文件齐全） | `tools/validate_story.py`（galgod 原版） | **✔ 通过**，2677/2677 节点可达 |
| 运行时排版（字号 14~30 全量，不超行、不超页、不丢字、不压 ▼） | `tools/test_paginate.js`（galgod 原版） | **✔ 通过** |
| 全部文本编码 | `tools/check_encoding.py` | **✔ 34 个文件均为合法 UTF-8**，README 引用的图都在 |
| 画面状态与演出是否对得上 | `tools/audit_stage.py`（本工程） | **✔ 188 → 2 处**（余下为分支扁平化误报） |
| 分支可玩通 | `tools/storygen/simulate_galgod.mjs`（本工程） | **✔ 27/27 条选项组合都能走到结局卡片** |
| 打包 | `node tools/build.js` | **✔ dist/*.rpk 8.44 MB，220 条目，0 个非 PNG 图片** |

`validate_story.py` 会把「存在不可达节点」判为错误，所以转换时专门做了一遍死代码清理
（空分支块会留下永不执行的跳转）。

---

## 六、内容是怎么来的

原始素材取自 PC 版《小小的身影，重叠的内心》（Ren'Py 8.6）的 `game/images.rpa`
与 `game/scripts.rpa`。转换流水线在 `tools/storygen/`，需要把解包结果放在仓库上一级目录
（`原始解包/`、`解包/`）。

```
rpyc_probe.py / rpyc_dump.py / rpyc_expr.py    宽松 unpickler，直接读 .rpyc 的 AST
        ↓  export_band_script.py               把 AST 转成扁平指令流（含条件跳转、变量赋值）
        ↓  band_assets.py                      把立绘按 layeredimage 规则合成、按表情取景
        ↓  build_galgod_port.py                转成 galgod 节点格式 + 生成索引表 + 装配工程
```

几个关键处理：

- **立绘是分层拼的**。原作是 layeredimage（皮肤 → 足部 → 服装 → 表情四层），
  这里在构建期就合成好整张，运行期只加载一张图。共 73 张，取景框按「脸部包围盒」自动推算，
  便服正面 / 便服侧面 / 制服正面三套姿势都能自动取到合适的构图。
- **条件分支完整保留**。原作有 43 处按 `stockings_color` / `first_choice` / `second_choice`
  分支的剧情（切换的是不同的 CG），转换成了 `cj` 条件跳转，不是拍平。
- **全部转 PNG8**。galgod 的 `build.js` 会对 JPEG 告警（真机解码不可靠），
  所以背景和 CG 都转成 PNG，再用调色板量化压体积——336×480 这个尺寸下画质差异看不出来。

单独重跑转换：

```bash
python tools/storygen/build_galgod_port.py            # 重新生成 src/ 里的内容部分
node  tools/storygen/simulate_galgod.mjs galgod-port  # 跑一遍全部剧情分支
```

---

## 七、与原作的差异

- **引擎不同**。原作是 Ren'Py（PC），这里是 VelaOS 快应用。剧本解释、存档、回想都由
  galgod-band 的 `game.ux` + `reader.js` 负责，不是原作的运行时。
- **没有音频**。小米手环 9 Pro 没有扬声器，原作的 BGM / 语音未收录。
- **立绘的显示变换不保留**。原作对 `syq_` 用了 `Transform(yzoom=0.45, xzoom=-0.45, yoffset=700)`
  （水平镜像 + 缩放到 45%），移植版按手环的 143×380 槽位重新取景，不做镜像。
- **一处分支的收尾不同**。原作「擦肩而过」那条线是 `goto splashscreen` 回标题画面，
  移植版给它一张 `—— 未完待续 ——` 的结局卡。
- **保留了 galgod 的彩蛋**：在「关于」页 2 秒内连点标题 7 次，可以解锁后日谈与全部 CG。
- 原作的 `persistent.gallery_unlocked_new` 等存档变量不参与移植版逻辑。

### 画面状态：`scene` 会清空整个画面层

这是移植时踩过的一个坑，值得单独写一下。

Ren'Py 的 `scene X` 是「**先把画面栈清空，再 show X**」，所以背景之外的立绘、CG 都会一起消失；
`show X` 只是往栈上追加。移植版的层序是固定的（背景 → 立绘 → CG），一开始只换了背景、
没清立绘，结果**上一幕的立绘会跨场景残留**：对话已经切到公司了，苏幼晴还站在咖啡馆里。

原作的演出顺序是这样的：

```
[立绘：syq_ cat_mouth]          ← 苏幼晴
苏幼晴：都上班的人了……
[场景：bg_office_3]             ← 切到公司，Ren'Py 连同立绘一起清掉
——世界从来都是一个草台班子。      ← 林默的内心独白，画面里只有公司背景
```

修正后 `Scene` 会带上 `scene` 标记，`Builder.clear_layer()` 据此清掉立绘与 CG 槽。
用 `tools/audit_stage.py` 可以量化这个问题：

```
修正前：A. 立绘跨场景残留 188 处   B. 立绘被 CG 盖住 0 处
修正后：A. 立绘跨场景残留   2 处   B. 立绘被 CG 盖住 0 处
```

（剩下 2 处是分支块在扁平化之后线性相邻造成的误报，不是真错位。）

同样地，剧本里**只有图片切换、没有对白**的分支块（原作的丝袜差分就是这种）也必须
把状态挂到块内那条 `j` 上，不能攒着等下一句对白——否则三个分支会互相覆盖，只剩最后一个生效。

### 章节选择的行为

`story/index.txt` 里只有两个章节条目：

```json
{"id":"main","title":"本篇","start":0}
{"id":"after","title":"后日谈","start":2366,"need":1}
```

`need:1` 表示「通关后才出现」，由 `chapters.ux` 结合 `reader.js` 的 `cleared` 标记过滤。
`cleared` 在走到真结局时由 `game.ux` 写入（判据是 `true_end_finish === 1`，由剧本收尾的
`{"t":"sf"}` 节点设置）。

在这个基础上，`tools/storygen/build_galgod_port.py` 还把三处 UI 也一并门控了：

| 位置 | 通关前 | 通关后 |
|---|---|---|
| 标题页的「章节」按钮 | 不显示 | 显示 |
| 阅读菜单的「章节 / CG」行 | 只显示占满整行的「CG」 | 显示「章节 + CG」两个半宽按钮 |
| 阅读菜单的「跳到下一章」 | 不显示（只有两篇，点了等于直接剧透后日谈） | 显示 |

顶部信息条里的篇名与进度、标题页的「最近进度」也会随之显示 `本篇` / `后日谈`。

### CG 鉴赏的差分切换

**分组直接取自原作的画廊定义**（`scripts/screens/gallery_screen.rpyc` 里的 Ren'Py `Gallery()`），
不是我另起一套。原作一个按钮可以挂多张图，那就是「差分」：

```python
g.button("cg5")
 .image("cg512").image("cg510").image("cg511")   # 白丝 / 裸足 / 黑丝
 .image("cg522").image("cg520").image("cg521")
 .image("cg532").image("cg530").image("cg531")
```

移植版的鉴赏页沿用同一套分组，**点开一组后用底部的 `‹ ›` 在差分之间翻**，
序号显示「第 n / N 张」。丝袜那一组是 9 张（本作用到的 3 个场景 × 白/裸/黑），
翻页顺序就是 白丝 → 裸足 → 黑丝 循环。

解锁判定按原作的语义来：`renpy/common/00gallery.rpy` 里一个按钮只要**任意一张**差分
被看过就解锁，而且 `unlocked_advance` 默认 False——解锁之后可以把没看过的那几张也翻出来。
所以选了黑丝也能在鉴赏里看到白丝。galgod 原来的 `cg.ux` 是拿组内第一张判解锁的，
选了黑丝的玩家会看不到这一组，这里改成了「任一张看过即解锁」。
这是本作对 `cg.ux` 的**唯一**改动。

分组名原作只有 id（cg1…cg6 / SD1 / SD2），现在的名字是按每组代表性 CG 的画面起的。

### CG 鉴赏用的是 galgod 2.2 的原版界面

鉴赏页就是 galgod **2.2** 的 `cg.ux` 原样：列表 → 大图 → 底部 `‹ n/N ›` 翻差分。
**没有拖动/滑动那一套**——那是 galgod 2.3 才加的功能（把 CG 出成 854 宽的完整 16:9、
比屏幕宽一倍多，靠按住左右拖动看被裁掉的部分），本作**没有采用**。

相应地，CG 和背景一样按屏幕尺寸出图（**336×480**，居中裁切），不在包里塞用不到的像素。

> galgod 2.3 同时对背景做了同样的处理（一张 672 宽的图、用定时器来回平移），
> 本作也没有采用：背景就是一张静态的 336×480 铺满屏幕。
> 所以除了「屏幕常亮」取自 2.3 之外，引擎其余部分一律是 2.2 的。

### 屏幕常亮

阅读时不让手环熄屏，走 Vela 的 `@system.brightness`：

```js
import brightness from '@system.brightness'
brightness.setKeepScreenOn({ keepScreenOn: true })
```

manifest 的 `features` 里必须声明 `system.brightness`，否则调用会抛错——已经声明了。
调用包了 try/catch：万一某些固件没有这个接口，也只是不常亮，不会让阅读崩掉。
开关在**设置页**（默认开），离开阅读页（`onHide`）会自动关掉。

### 标题与图标

标题页的标题用的是原作的大张透明 logo（`custom/LOGO_white.png`，缩放成 288×144），
不是文字；应用图标取自原作 `gui/window_icon.png`（250×250，缩到 192×192）。

---

## 八、版权

> 想把这个工程推到 GitHub 的话，看 [PUSH.md](PUSH.md)：里面写了这台机器推不出去的原因、
> 三条可行路线，以及**哪些是版权素材、默认不进仓库**。

- **引擎与界面**：来自 [galgod-band](https://github.com/mcpotato1123/galgod-band)，MIT 协议，
  基线 2.2（屏幕常亮取自 2.3）；本工程对其做了少量改动（章节门控、鉴赏解锁判定、补标题 logo、屏幕常亮），
  改动点都写在上面「与原作的差异」一节里。
- **剧本与美术**：取自 PC 版《小小的身影，重叠的内心》，版权归原作及其开发方所有，
  **不在 MIT 范围内**，请勿用于商业用途。

详见 [NOTICE.md](NOTICE.md)。
