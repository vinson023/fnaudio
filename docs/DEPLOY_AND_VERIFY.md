# 部署与真机验证手册（0.2.167 实测版）

日期：2026-11-19
适用：把当前源码部署到飞牛 `192.168.5.141`，并在安卓真机上验证

这份文档按 0.2.167 的实际执行顺序写，命令都是跑过的，不是设计稿。
文末「本次实测结果」记的是这一轮真实发生的事，包括没通过的部分。

---

## 0. 一句话流程

```
改版本坐标 → 提交 → build_release.ps1 出 FPK → load_signing_env.ps1 -ThenBuild 出 APK
   → install_via_app_center.js 装到 5.141 → 浏览器验 /api/health + 界面
   → adb 装 APK 到手机 → 手机上逐项点一遍
```

---

## 1. 环境与依赖

### 1.1 构建机（Windows）

| 依赖 | 用途 | 检查命令 |
| --- | --- | --- |
| PowerShell 5.1 | 跑 `tools/*.ps1` | `$PSVersionTable.PSVersion` |
| Python 3.12/3.13 | 服务端 + 3490 个用例 | `python -V` |
| Node.js | 前端回归 + Playwright 脚本 | `node -v` |
| Google Chrome | 应用中心安装、界面验收 | `"C:\Program Files\Google\Chrome\Application\chrome.exe"` |
| Android SDK（build-tools 36 + platform-tools） | 出 APK、adb | `tools/android-sdk/` |
| JDK 17 | Gradle 构建 | `java -version` |
| Playwright（`tools/browser-e2e/node_modules`） | 浏览器自动化 | 见下 |

Playwright 不需要单独装浏览器，脚本直接指定本机 Chrome：

```powershell
$env:NODE_PATH = "tools/browser-e2e/node_modules"
```

### 1.2 签名材料

`.secrets/release-signing.env` + `.secrets/fnaudio-release.jks`（已在仓库里，被 `.gitignore` 排除）。
APK 必须用**同一个证书**，否则覆盖安装会报
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`，卸载重装又会丢登录态。

### 1.3 目标环境

| 目标 | 地址 | 说明 |
| --- | --- | --- |
| 飞牛 NAS | `http://192.168.5.141:5666` | 应用中心入口；`:53199` 是内部端口，LAN 直连 403 属设计 |
| 应用页面 | `/cgi/ThirdParty/fnaudio/index.cgi/` | iframe 应用只走 CGI 代理 |
| 安卓手机 | `192.168.5.111:5555`（SM-G965F / Android 13） | 无线调试端口每次开关都会变，用 `tools/adb_wireless.py` 发现 |
| SSH（可选） | `root@192.168.5.141` | 读配置、看进程、查 SQLite |

PowerShell 首次运行脚本要先放开执行策略：

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
```

---

## 2. 构建

### 2.1 改版本坐标（八处）

```bash
VERSION                                    # 0.2.167
src/manifest                               # version=0.2.167
android-client/app/build.gradle            # versionName + versionCode（424→425）
README.md                                  # 6 处
ARCHITECTURE.md
docs/SOURCE_INVENTORY.md                   # 2 处
android-client/README.md                   # 2 处
RECOVERY.md
```

改完必须过版本一致性用例：

```bash
cd src && python -m unittest tests.test_release_version -v    # 2/2 OK
```

### 2.2 提交（构建要求工作区干净）

`build_release.ps1` 会把 `src`、`android-client` 的改动状态写进 `SOURCE_PROVENANCE.json`。
带脏树构建会记 `git_provenance_status: dirty`——能出包，但那不是一份可复现的证据。

```bash
git add -A -- src/app src/tests CHANGELOG_AI.md
git commit -F <功能提交信息>
git add -A -- VERSION src/manifest android-client/app/build.gradle README.md \
  ARCHITECTURE.md docs/SOURCE_INVENTORY.md android-client/README.md RECOVERY.md \
  SOURCE_MANIFEST.sha256
git commit -F <版本提交信息>
git status --porcelain -- src android-client    # 必须为空
```

清单刷新（改了 `src/` 就要跑）：

```powershell
& .\tools\update_source_manifest.ps1        # 909 entries
```

### 2.3 FPK

```powershell
& .\tools\build_release.ps1
```

输出：`artifacts/<版本>/fnaudio-<版本>-fnpack.fpk`，同时写
`SOURCE_MANIFEST.sha256`、`SOURCE_PROVENANCE.json`、`SHA256SUMS`。

### 2.4 APK（release 签名）

```powershell
& .\tools\load_signing_env.ps1 -ThenBuild
```

**注意**：不要把它的输出接进管道（`| Select-Object`）或重定向到文件。
`javac` 往 stderr 写提示，PS 5.1 在重定向/管道合并时才把原生命令的 stderr
转成 `ErrorRecord`，`$ErrorActionPreference = "Stop"` 会让构建在成功之后报失败。
要留日志就 `*> file` 由脚本自己收尾，或者干脆不加管道。

### 2.5 产物自检

```powershell
& .\tools\verify_release_evidence.ps1 -ArtifactDirectory artifacts\0.2.167
# Validated / AndroidValidated / EvidenceComplete 三项都应为 True
```

---

## 3. 部署到飞牛

### 3.1 只有一条路可作数

**浏览器打开应用中心 → 手动安装 → 上传 FPK → 同意 →（全新安装还要走完向导）→ 浏览器打开应用本身。**

SSH 解包 + `cmd/main start` 是部署，不是安装，验证不了向导与 iframe 注册。
详见 `docs/FNOS_APPCENTER_INSTALL_TEST.md`。

### 3.2 命令

```bash
NODE_PATH=tools/browser-e2e/node_modules \
  node tools/install_via_app_center.js artifacts/0.2.167/fnaudio-0.2.167-fnpack.fpk \
  --out artifacts/0.2.167/install-trace
```

可选环境变量：`FNAUDIO_HOST`（默认 `http://192.168.5.141:5666`）、
`FNAUDIO_USER`、`FNAUDIO_PASSWORD`、`FNAUDIO_CHROME`。

### 3.3 三条成功判据（缺一条都算没装上）

1. 应用中心登记版本 == 包版本，且 `status == "running"`
2. 经代理 `/cgi/ThirdParty/fnaudio/index.cgi/api/health` 返回 **200**
3. 脚本退出码 **0**

### 3.4 刚装完的 503 是正常的

服务起来的那几秒，CGI 代理会回 503（body 是应用自己的 HTML）。
等 5–10 秒再探，通常就 200 了。**不要**拿第一次的 503 判失败，
也不要拿 `:53199` 的 403 判失败。

---

## 4. 部署后验证

### 4.1 一键探针（接口 + 界面，13 项）

```bash
NODE_PATH=tools/browser-e2e/node_modules node artifacts/0.2.167/verify_deployed.js
# 期望最后一行：DEPLOY_VERIFY_OK
```

它检查：`/api/health`、`/api/library/status` 的曲目数、
四种 `ORDER BY`（album/artist/release_date，含降序）返回的行与顺序、
专辑表头三格是否都是按钮、点「歌手」后行序是否真的变了、箭头是否出现、
网格瓦片是否为 0。截图落在 `artifacts/0.2.167/deploy-verify/`。

### 4.2 手工复核（接口层）

浏览器登录后，在应用页面里执行（或直接开 DevTools Console）：

```js
await (await fetch("api/health", {credentials:"include"})).json()
await (await fetch("api/library/status", {credentials:"include"})).json()
await (await fetch("api/library/groups?view=albums&paged=1&limit=8&offset=0&sort=artist&dir=asc",
                    {credentials:"include"})).json()
```

`curl` 直接打会得到 `200 invalid token`——那是没带会话，不代表服务坏了。

### 4.3 手工复核（界面层）

1. 打开 `/cgi/ThirdParty/fnaudio/index.cgi/`
2. 侧栏「专辑」→ 应看到行列表（不是网格），上方三个列标题
3. 点「歌手」→ 行序变化 + 箭头出现在该列
4. 点「发行日期」→ 无年份的专辑被压到末尾

### 4.4 SSH 侧核对（可选）

```bash
python tools/run_on_nas.py <脚本>     # 需要 paramiko
```

常用三句：

```bash
ps aux | grep fnaudio | grep -v grep
cat /usr/local/apps/@appcenter/fnaudio/etc/config.json
ls -la /usr/local/apps/@appcenter/fnaudio/etc/transcode/library.sqlite3
```

---

## 5. 手机端测试

### 5.1 连上手机

无线调试端口每次开关都变，不要记死端口：

```bash
python tools/adb_wireless.py connect      # 自动 mDNS 发现 + 连接
./tools/android-sdk/platform-tools/adb.exe devices -l
```

**坑**：每次 `Bash` 调用之间 adb server 可能被回收，所以
`connect` 与后续命令要写在**同一条命令**里：

```bash
ADB=./tools/android-sdk/platform-tools/adb.exe
"$ADB" connect 192.168.5.111:5555 >/dev/null 2>&1
"$ADB" -s 192.168.5.111:5555 shell dumpsys package com.fnaudio.client | grep versionName
```

### 5.2 安装

```bash
"$ADB" -s 192.168.5.111:5555 install -r artifacts/0.2.167/fnaudio-android-0.2.167-release.apk
```

`-r` 覆盖安装保留登录态与缓存。证书不同会报
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`——那就说明打的不是 release 包。

### 5.3 启动并唤醒

```bash
"$ADB" -s $D shell am start -n com.fnaudio.client/.ui.MainActivity
"$ADB" -s $D shell input keyevent KEYCODE_WAKEUP
"$ADB" -s $D shell wm dismiss-keyguard
"$ADB" -s $D shell dumpsys window | grep mCurrentFocus
```

`mCurrentFocus=...NotificationShade` 表示还停在锁屏/通知栏，界面没出来。

### 5.4 配置连接到 NAS

手机里保存的档案可能来自模拟器（`10.0.2.2:18099`），装完新版会直接报
「无法连接 NAS」。改法：在登录页填

| 字段 | 值 |
| --- | --- |
| 地址 | `192.168.5.141:5666` |
| 用户名 | `admin` |
| 密码 | NAS 密码 |
| 飞牛访问码 | 未开启就留空 |
| HTTPS 安全访问 | 不勾（局域网 5666 是明文） |

adb 驱动方式（坐标按 1440×2960）：点输入框 → `KEYCODE_MOVE_END` →
连按 `KEYCODE_DEL` 清空 → `input text` → 点「登录」。
键盘挡住按钮时先 `input keyevent KEYCODE_BACK` 收键盘。

### 5.5 逐项检查

| # | 动作 | 期望 |
| --- | --- | --- |
| 1 | 启动 | 进主界面，不是「无法打开 fnAudio」 |
| 2 | 侧栏「全部音乐」 | 计数与服务端一致（本轮 118） |
| 3 | 列表 | 显示歌名/歌手/专辑，封面逐步加载 |
| 4 | 侧栏「专辑」 | 行列表 + 「N 张专辑」 |
| 5 | 点专辑 | 进详情，面包屑正确 |
| 6 | 详情曲目 | 列出该专辑的歌 |
| 7 | 播放 | 进度走动，按钮变暂停 |
| 8 | 列标题排序 | 手机上**目前没有表头**，见 6.2 |

截图命令：

```bash
"$ADB" -s $D exec-out screencap -p > artifacts/0.2.167/phone-1.png
```

---

## 6. 本次实测结果（0.2.167）

### 6.1 通过

- 应用中心：`0.2.166/running → 0.2.167/starting → 0.2.167/running`，约 10 秒，`INSTALL_OK`
- 经代理 `/api/health`：200，`ok:true`
- 曲库：**118 首 / 81 张专辑**
- 专辑三种排序：`album` / `artist` / `release_date` 均 200 且有行；
  `artist:asc` 实测顺序 `Acraze, Cherish | Adele | Adele | AGA`，正确
- 专辑表头三格都是按钮（`album` / `artist` / `release_date`），
  点「歌手」后行序改变、箭头出现
- 专辑页无网格瓦片（`album-tile` / `album-grid` 计数 0）
- 手机：`versionCode 425` / `versionName 0.2.167` 覆盖安装成功，登录态保留；
  主界面列出 118 首、侧栏计数一致、专辑页显示「81 张专辑」

### 6.2 没通过 / 需要注意

**① 升级后曲库配置被清空（严重）**

升级到 0.2.167 后 `/api/library/status` 返回
`library_paths: []`、`count: 0`，也就是用户看到「曲库空了」。

取证：`/usr/local/apps/@appconf/fnaudio/config.json` 里两个路径都在
（10:38:11 写入），但服务实际读的是
`/usr/local/apps/@appcenter/fnaudio/etc/config.json`，那一刻只有 22 字节
（`{"server_port": 53199}`）。`cmd/upgrade_callback` 里的「旧配置迁移」
本该把路径搬过来，实际没搬成。

处置：通过产品自己的接口写回并重扫，恢复 118 首：

```js
POST /api/config/library  {"library_path": "/vol1/1000/music\n/vol02/1000-1-9ed159d1/music"}
GET  /api/library/status?refresh=1        // 触发扫描，10 秒后 count=118
```

写回后 `etc/config.json` 变成完整的 1710 字节配置。
**这条必须查清并修**——升级丢用户设置比任何 UI 问题都严重。

**② 手机上没有列标题，排序点不到**

`app.css` 有 `@media(max-width:760px){.table-head{display:none!important}}`，
所以手机上专辑页只有行、没有表头，本轮新增的「按歌手/发行日期排序」
在手机端**根本够不着**。桌面端正常。

**③ 手机上专辑详情是空的**

点开专辑「23」：面包屑与封面都在，曲目区一片空白。
同一张专辑在桌面端能列出 `96 23 Sam Hunt 23 6.9 MB MP3`，
接口 `/api/library?album=23` 也返回 200 且有 items，所以是**手机端渲染**没出来，
不是数据问题。原因未查明（logcat 里没有对应 JS 报错）。

**④ 按发行日期排序在这台机器上看不出差别**

库里的 118 首**全部没有年份标签**（`tracks.year` 全为 0），
所以 `albums.release_year` 全是 0，按发行日期排等于全部并列、退回按专辑名排。
这是数据问题不是代码问题，但也意味着这条排序在本机无法用真实数据验证。

---

## 7. 常见误判

| 现象 | 不是原因 | 真正原因 |
| --- | --- | --- |
| `:53199` 打不开 / 403 | 应用没起来 | iframe 应用只走 CGI 代理，403 是设计 |
| 刚装完代理返回 503 | 装失败 | 服务还在启动，等 5–10 秒 |
| `curl` 拿到 `invalid token` | 接口坏了 | 没带 fnOS 会话 Cookie |
| 手机报「无法连接 NAS」 | NAS 挂了 | 手机里存的档案是模拟器地址 `10.0.2.2:18099` |
| `adb devices` 忽然为空 | 手机掉线 | adb server 被回收，同一条命令里重新 `connect` |
| `test_offline.ps1` 立刻中止、日志 0 字节 | 用例失败 | 输出被重定向/接管道，PS 5.1 把 stderr 转成 `ErrorRecord` |
| `git_provenance_status: dirty` | 构建脚本有问题 | 工作区没提交干净 |

---

## 8. 相关文件

- `docs/FNOS_APPCENTER_INSTALL_TEST.md` —— 飞牛安装规程
- `tools/install_via_app_center.js` —— 安装唯一入口
- `tools/build_release.ps1` / `tools/build_android_release.ps1` —— 出包
- `tools/load_signing_env.ps1` —— 注入签名变量后构建
- `tools/verify_release_evidence.ps1` —— 产物证据校验
- `tools/adb_wireless.py` —— 无线调试端口发现
- `tools/run_on_nas.py` —— SSH/SFTP 执行诊断脚本
- `artifacts/0.2.167/verify_deployed.js` —— 本次部署验收探针
