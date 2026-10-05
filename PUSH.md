# 推到 GitHub

仓库已经在本目录初始化好，`main` 分支上有一个提交（39 个文件）。**还没推出去**——
这台机器推不了，原因和三条可行路线写在下面。

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

## 关于版权素材（**推之前请先决定**）

`.gitignore` 里**默认排除了原作的剧本与美术**：

```
src/common/story/        原作剧本
src/common/img/          背景 / 立绘 / CG
src/common/home.png      标题画
src/common/logo.png      标题 logo
src/common/icon.png      应用图标
src/common/assets.js     由素材生成的索引表
src/common/cglist.js     同上
```

原因：这些是 PC 版《小小的身影，重叠的内心》的资源，**版权归原作及其开发方所有，
不在 galgod-band 的 MIT 协议范围内**。公开仓库里放这些属于再分发，有可能被 DMCA 下架。

所以当前仓库是「**引擎 + 转换工具 + 文档**」：别人克隆下来要**自备原作**，
再按 README 第六节跑一遍 `tools/storygen/` 的流水线生成内容。
这对一个移植工具仓库来说是完整且自洽的。

### 如果你要连素材一起发布

三种选择，按风险从低到高：

1. **私有仓库**——自己留档，不对外分发。（把仓库设为 Private 即可）
2. **公开但只放代码**（当前状态）——推荐。
3. **公开且含素材**——把 `.gitignore` 里「版权素材」那一段注释掉，然后：

```bash
cd galgod-port
git add -f src/common/story src/common/img src/common/home.png \
           src/common/logo.png src/common/icon.png \
           src/common/assets.js src/common/cglist.js
git commit -m "加入内容素材（含原作的剧本与美术）"
git push
```

注意这会写进 git 历史，之后想彻底移除要改写历史（`git filter-repo`）。

---

## 顺带一提

`dist/*.rpk`（8.44 MB 的安装包）也在 `.gitignore` 里（galgod-band 上游同样忽略它）。
如果想随仓库发安装包，更合适的做法是**发 GitHub Release** 挂附件，而不是提交进仓库。
