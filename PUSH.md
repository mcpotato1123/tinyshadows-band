# 推到 GitHub

仓库已经在本目录初始化好，`main` 分支上有 6 个提交（**232 个文件，含素材**）。
**还没推出去**——这台机器推不了，原因和三条可行路线写在下面。

先看一眼现状：

```bash
cd galgod-port
git log --oneline          # f382ff0 移植《小小的身影，重叠的内心》到小米手环 9 Pro
git status                 # 干净
```

---

## 为什么现在推不上去

`C:\Windows\System32\drivers\etc\hosts` 里把 GitHub 全系域名都指到了 `127.0.0.1`：

```
127.0.0.1 github.com
127.0.0.1 api.github.com
127.0.0.1 raw.githubusercontent.com
...
```

而 `127.0.0.1:443` 上并没有任何东西在监听，所以是**直接黑洞**。改 hosts 需要管理员权限，
当前会话没有。另外用 git 自带的 schannel 后端还会另外报一次
`SEC_E_NO_CREDENTIALS`，那是这个沙箱的 TLS 问题，和 hosts 无关。

实测代理的转发能力：

| 请求 | 结果 |
|---|---|
| `git-upload-pack`（拉取） | **HTTP 200** —— 可以走 `ghproxy.net` 拉 |
| `git-receive-pack`（推送） | **HTTP 401 `No anonymous write access.`** —— 转发是通的，但**需要凭据** |

也就是说：**技术上能推，只差认证**。`gh` CLI 没装，`.git-credentials` 也不存在。

---

## 路线 A（推荐）：解掉 hosts 限制，直连推送

最干净——token 不经过任何第三方。

1. 用**管理员**打开记事本，编辑 `C:\Windows\System32\drivers\etc\hosts`，
   把 `github.com`、`api.github.com`、`raw.githubusercontent.com` 这几行前面加 `#` 注释掉。
2. 刷新 DNS：`ipconfig /flushdns`
3. 建一个**空仓库**（不要勾选 README / .gitignore / License，否则要先 pull）。
4. 在 GitHub 上建一个 **fine-grained PAT**：`Contents: Read and write`，
   范围只限这一个仓库，有效期设最短。
5. 推送：

```bash
cd galgod-port
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
# 用户名填 GitHub 用户名，密码填 PAT
```

推完记得把 PAT 撤销掉。

---

## 路线 B：走 ghproxy.net（不用改 hosts，但 token 会经过第三方）

代理能转发推送，只差认证。**代价是 PAT 会经过 `ghproxy.net` 这个第三方**——
代理运营方理论上能看到它。所以：

- 一定要用**只限该仓库、只给 Contents 写权限、有效期最短**的 fine-grained PAT；
- 推完**立刻撤销**；
- **私有仓库不要走这条**（gh-proxy 自己也这么警告）。

```bash
cd galgod-port
git remote add proxy https://ghproxy.net/https://github.com/<你的用户名>/<仓库名>.git
git push proxy main
```

---

## 路线 C：不改任何东西，拿到别处推（最稳）

已经导出好了 `tinyshadows-band.bundle`（1.93 MB，含完整历史）：

```bash
# 在能访问 GitHub 的机器上
git clone tinyshadows-band.bundle galgod-port
cd galgod-port
git remote set-url origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

不需要 token 经过这台机器，也不需要动 hosts。

---

## 关于版权素材

仓库现在是「**连素材一起收录**」的模式，和 [galgod-band](https://github.com/mcpotato1123/galgod-band) 一致：

| 路径 | 内容 | 版权 |
|---|---|---|
| `src/common/story/` | 剧本文字（2,503 句对白） | 原作《小小的身影，重叠的内心》及其开发方 |
| `src/common/img/` | 背景 25 / 立绘 94 / CG 40 / 缩略图 8 | 同上 |
| `src/common/home.png`、`logo.png`、`icon.png` | 标题画 / 标题 logo / 应用图标 | 同上 |

这些**不在 MIT 协议范围内**。声明放在 `NOTICE.md` 而不是 `LICENSE` 里——
GitHub 是靠跟官方模板做相似度匹配来识别协议的，在 MIT 正文后面追加内容会导致
仓库页面显示不出 MIT 标识。这一段做法照搬 galgod-band。

收录它们只是为了**让仓库能直接构建出可运行的包**；引擎本身不依赖任何具体素材。

### 如果版权方有异议

删掉上表里的目录与文件即可，此时仓库仍然可用——用 `tools/storygen/` 的流水线，
从**你自己的原作拷贝**重新生成一遍：

```bash
python tools/storygen/build_output.py      # 解包原作 rpa
python tools/storygen/build_galgod_port.py # 转成 galgod 数据格式 + 生成索引表
```

### 或者干脆只发引擎+工具

把 `.gitignore` 里加回下面几行，再 `git rm -r --cached` 对应路径：

```
src/common/story/
src/common/img/
src/common/home.png
src/common/logo.png
src/common/icon.png
src/common/assets.js
src/common/cglist.js
```

注意：素材**已经写进 git 历史**了，想彻底移除要改写历史（`git filter-repo`）。

---

## 顺带一提

`dist/*.rpk`（8.44 MB 的安装包）在 `.gitignore` 里（galgod-band 上游同样忽略它）。
如果想随仓库发安装包，更合适的做法是**发 GitHub Release** 挂附件，而不是提交进仓库。

