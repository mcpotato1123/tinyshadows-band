# 版权说明 / Assets Notice

本工程由两部分组成，版权归属不同，**请分别看待**。

**本仓库的 MIT 协议只覆盖代码**，下面第二节列出的剧本与美术**不属于** MIT 的授权范围。

> 这句话**故意不写进 LICENSE 里**：GitHub 识别协议是把 LICENSE 跟官方模板做相似度匹配，
> 在 MIT 正文后面追加任何内容都会拉低相似度、导致仓库页面上显示不出 MIT 标识。
> 所以 LICENSE 里只有纯 MIT 文本，范围说明放在这里。
> （这一节照搬 galgod-band 的做法。）

## 一、引擎与界面（MIT 协议）

来自开源项目 **galgod-band**（作者 mcpotato1123），基于 MIT 协议使用，基线版本 **2.5.2**。
本工程对其做了少量改动（章节门控、鉴赏解锁判定、补标题 logo，
并修掉上游 onHide 重名与 g 自动清立绘两处问题），
改动点见 README 的「与原作的差异」一节。

| 路径 | 内容 |
|---|---|
| `src/common/reader.js` | 设置项、存档读写、换行分页 |
| `src/pages/` | 7 个页面（标题 / 阅读 / 存档 / 章节 / CG / 设置 / 关于） |
| `src/app.ux` | 应用入口 |
| `src/manifest.json` | 应用清单（仅改了包名、名称与版本号） |
| `tools/build.js`、`tools/validate_story.py`、`tools/test_paginate.js`、`tools/check_encoding.py` | 构建与校验工具 |

以上内容详见 [LICENSE](LICENSE)。`src/pages/index/index.ux` 与 `src/pages/about/about.ux` 中的**显示文案**已替换为本作内容，版式与结构未改。

## 二、剧本与美术（不属于 MIT 范围）

| 路径 | 内容 | 版权 |
|---|---|---|
| `src/common/story/` | 剧本文字（2,503 句对白，本篇 + 后日谈） | 原作《小小的身影，重叠的内心》及其开发方 |
| `src/common/img/b/` | 背景 25 张（672×480 宽幅，供全景平移） | 同上 |
| `src/common/img/s/` | 立绘 94 张（含裸足 / 白丝 / 黑丝三套差分） | 同上 |
| `src/common/img/c/` | CG / SDCG 40 张（854×480 完整 16:9） | 同上 |
| `src/common/img/t/` | CG 鉴赏缩略图 8 张 | 同上（由上面裁切而来） |
| `src/common/home.png` | 标题画（原作 `titlenew_bg_1`） | 同上 |
| `src/common/logo.png` | 标题 logo（原作 `LOGO_white`） | 同上 |
| `src/common/icon.png` | 应用图标（原作 `gui/window_icon.png`） | 同上 |

这些都取自 PC 版 **《小小的身影，重叠的内心》**（Ren'Py 8.6）的游戏资源，
版权归原作及其开发方所有。

`src/common/assets.js` 与 `src/common/cglist.js` 是上述素材的**索引表**
（由 `tools/storygen/build_galgod_port.py` 生成）。它们是**生成物但按代码对待**，
归入 MIT 范围——和 galgod-band 对这两个文件的处理一致。

收录素材**只是为了让仓库能直接构建出可运行的包**——引擎本身不依赖任何具体素材，
换一套剧本和图片照样能跑。

## 使用限制

- 请勿用于任何商业用途。
- 本工程为非官方、非商业性的个人移植作品，与 **小米（Xiaomi）** 无关联，
  亦未获得原作方的授权、赞助或认可。
- 如版权方有异议，删除上表中列出的目录与文件即可；
  此时仍可用 `tools/storygen/` 的流水线，从你自己的原始素材重新生成一遍。
- 如有侵权，请联系删除。

## 在 MIT 范围内的内容

`src/pages/`、`src/common/reader.js`、`src/common/assets.js`、`src/common/cglist.js`、
`src/app.ux`、`src/manifest.json`、`tools/`、`preview/` 以及所有文档。
详见 [LICENSE](LICENSE)。

## 三、本移植版新增

| 路径 | 说明 |
|---|---|
| `tools/storygen/` | 把原作资源转换成 galgod 数据格式的流水线（本移植版新写） |
| `tools/preview_port.py` | 按 `game.ux` 的版面几何渲染界面预览图（本移植版新写） |
| `preview/ui-preview.png` | 上面那个工具生成的界面预览 |

这部分同样按 MIT 协议提供。
