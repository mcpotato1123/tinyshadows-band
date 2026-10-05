# 内容转换流水线

把 PC 版《小小的身影，重叠的内心》（Ren'Py 8.6）的解包结果，转换成 galgod-band 的数据格式。

**这些脚本不是运行游戏所必需的**，它们只是内容的来源，方便日后重新生成或对照。
运行需要在工程的上一级目录里放好解包结果（`原始解包/`、`解包/`）。

## 依赖顺序

```
①  原始解包/                     game/images.rpa 与 game/scripts.rpa 的解包结果
        ↓
②  解包/立绘/合成立绘/            按 layeredimage 规则合成好的整张立绘（2284×3586）
        ↓
③  build_galgod_port.py          生成 galgod-port/src/ 的内容部分
```

②由上级目录的 `tools/build_output.py` 产出（那一步同时也会导出对话文本与全尺寸素材）。

## 各脚本职责

| 文件 | 作用 |
|---|---|
| `rpyc_probe.py` | **宽松 unpickler**。`.rpyc` 是 `RENPY RPC2` 容器里塞的 pickle，引用了大量 renpy 的类。这里不导入 renpy，而是给每个未知类动态造一个替身，够用来遍历 AST。Ren'Py 的节点用 `__slots__` 存状态，所以读取属性要合并 `__dict__` 与 `_slots` 两半。 |
| `rpyc_dump.py` | 把 AST 打印成可读树（排查用） |
| `rpyc_expr.py` | 从 `PyExpr` / `PyCode` 里取出 Python 源码字符串 |
| `extract_script.py` | 导出对话文本（中文 / 日语）；同时提供角色名表 |
| `compose_sprites.py` | 解析 syq.rpyc 里的 `layeredimage` 定义，按分组解析属性、合成整张立绘 |
| `band_assets.py` | 按脸部包围盒推算立绘取景框（`build_galgod_port.py` 复用了这里的 `face_bbox`）；它自己也能生成一套手环尺寸素材 |
| `export_band_script.py` | 把 AST 转成扁平指令流：解析 `If` 条件为结构化子句、把 `Menu` 拍平成 label+goto、提取 `$` 里的简单赋值 |
| `build_galgod_port.py` | **主入口**。转成 galgod 节点格式、生成 `assets.js` / `cglist.js`、装配整个工程 |
| `simulate_galgod.mjs` | 用 Node 复刻 `game.ux` 的执行语义，把所有选项组合跑一遍，验证每条路都能到结局 |

## 几个踩过的坑（留作记录）

1. **每个 `.rpyc` 末尾都有一条隐式 `return`**（文件结束标记），它不是剧情结局。
   不排除掉的话，第一章跑完就会直接停在结局画面。
2. **`Menu.statement_start` 是陈旧副本**。Ren'Py 的静态变换会把菜单提示语挪到父 block 里，
   而 `statement_start` 仍指向一份未分析的拷贝（identifier 为 `None`）。
   两个都导出会把同一句话重复一遍。`statement_start` 只在 `renpy/execution.py` 里
   用于 call 返回点，不参与显示。
3. **原包的立绘目录名与文件名前缀是错位的**：`fg/side/` 里放的是 `syq_cos_side_*.png`。
   归类要按文件名前缀，不能按目录名。
4. **`resolve` 里的「生效属性集」只能取实际选中的属性**。如果把「请求过的」也算进去，
   当同一组里请求了多个值时（比如同时出现 `clothes1_front` 和 `clothes2_front`），
   落选的那个会错误地满足另一视图图层的 `when` 条件，合成出不存在组合。
5. **空的分支块会留下永不执行的跳转**。galgod 的 `validate_story.py` 把「存在不可达节点」
   判为错误，所以 `build_galgod_port.py` 里有一遍死代码清理（`prune`），会重新编号所有跳转目标。

## 数据口径

- 对白节点 **2503** 个，与 `scripts/content/*.rpyc` 里的说白节点数一致（逐章核对过）。
- 立绘属性串 **54** 种，解析后去重成 **73** 张（同一表情在不同皮肤/服装下是不同的图）。
- 资源全部为 **PNG8**：背景 25、立绘 73、CG 40、鉴赏缩略图 5。
