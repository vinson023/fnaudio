# 部署与真机验证手册（0.2.173 实测版）

日期：2026-11-20
适用：把当前源码部署到飞牛 `192.168.5.141`，并在安卓真机上验证

这份文档按 0.2.173 的实际执行顺序写，命令都是跑过的，不是设计稿。
文末「本次实测结果」记的是这一轮真实发生的事，包括没通过的部分。
6.2 是 0.2.171（0.2.170 从未装上），6.3 是 0.2.173（0.2.172 装上了但随即作废）。

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
VERSION                                    # 0.2.168
src/manifest                               # version=0.2.168
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
& .\tools\verify_release_evidence.ps1 -ArtifactDirectory artifacts\0.2.168
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
  node tools/install_via_app_center.js artifacts/0.2.168/fnaudio-0.2.168-fnpack.fpk \
  --out artifacts/0.2.168/install-trace
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

### 4.1 一键探针（接口 + 桌面 + 窄屏，25 项）

```bash
NODE_PATH=tools/browser-e2e/node_modules node artifacts/0.2.168/verify_deployed.js
# 期望最后一行：DEPLOY_VERIFY_OK

# 换一台机器时用环境变量指目标与输出目录，别改脚本
NODE_PATH=tools/browser-e2e/node_modules \
  FNAUDIO_HOST=http://192.168.5.2:5666 FNAUDIO_OUT=artifacts/0.2.168/deploy-verify-52 \
  node artifacts/0.2.168/verify_deployed.js
```

它检查三层：

- **接口层**：`/api/health`、`/api/access` 报的版本号、`/api/library/status` 的曲目数与 `library_paths`、
  四种 `ORDER BY`（album/artist/release_date，含降序）返回的行与顺序。
  `library_paths` 非空就是「升级没清空曲库」的直接证据。
- **桌面层**：专辑表头三格是否都是按钮、点「歌手」后行序是否真的变了、箭头是否出现、网格瓦片是否为 0。
- **窄屏层**（390×844）：表头 `display` 不是 `none` 且三个按钮齐全、点「歌手」行序变化、
  用搜索框定位曲目最多的那张专辑（曲目数取自接口的 `track_count`，不写死专辑名）、
  量 `.track-main` 宽度必须 > 200px、`.track-title` 宽度必须 > 40px。

窄屏那一层不能省。R613/R614 两次都是「接口对、桌面对、手机空白」——
只看元素存不存在会漏，必须量真实几何。截图落在 `artifacts/0.2.168/deploy-verify/`。

写这个探针时踩过四个坑，都是判据本身写错、不是产品问题，改判据时别踩回去：

| 判据 | 错在哪 | 正确写法 |
| --- | --- | --- |
| 版本号读 `health.version` | `/api/health` 只有 `ok/name/request_id/components/metrics` | 读 `/api/access` 的 `version` |
| 排序用 `localeCompare(..., "zh")` | 服务端是大小写不敏感的 NOCASE 码位序；`.141` 全 ASCII 时碰巧通过 | 折成小写再比码位 |
| 专辑详情的 DOM 行数必须等于 `track_count` | 详情列表按 `pageSize` 截断，默认 50；72 首的专辑只渲染 50 行是设计如此 | 比 `min(track_count, pageSize)` |
| 按列表序号点开目标专辑 | 大库专辑列表分页，目标可能没渲染 | 用搜索框 `#mobileSearchInput` 过滤后再点 |

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
"$ADB" -s 192.168.5.111:5555 install -r artifacts/0.2.168/fnaudio-android-0.2.168-release.apk
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
| 8 | 列标题排序 | 专辑页搜索框下方有「标题 / 歌手 / 发行日期」；点「歌手」箭头出现在该列、行序变化 |
| 9 | 专辑详情曲目 | 点开多曲目专辑，曲名与「歌手 · 专辑」都看得见，不是只有一个封面 |
| 10 | 升级后曲库 | 侧栏计数不为 0；`/api/library/status` 的 `library_paths` 非空 |

截图命令：

```bash
"$ADB" -s $D exec-out screencap -p > artifacts/0.2.168/phone-1.png
```

---

## 6. 实测结果

### 6.1 0.2.168（2026-11-19）

三个已知问题全修完才出包，逐个在真机复核：

**① 升级不再清空曲库**

- 应用中心：`0.2.167/start → 0.2.168/starting → 0.2.168/running`，`INSTALL_OK`，health 200
- `/api/library/status`：`count=118`，`library_paths` = `["/vol1/1000/music","/vol02/1000-1-9ed159d1/music"]`（非空）
- `@appcenter/etc/config.json` 与 `@appconf/config.json` 都是 1704 字节且内容一致
- `/var/apps/fnaudio/manifest` 的 `version = 0.2.168`
- 首次安装曾失败一次（端口探测误报），重试通过，见第 7 节
  ——**「重试能过」是运气，不是机制**：0.2.170 连试三次都没过，真因与修法见 6.2

**② 手机上专辑列表能排序**

390×844 视口：`#tableHead` 的 `display:flex`、`rect=[0,116,390,44]`、
`data-table-mode="album-collection"`、三个按钮 `["标题","歌手","发行日期"]`；
点「歌手」后行序 `'Til You Can't / 100 Greatest Pride Songs` → `Do It To It / 30`，箭头出现。

真机（SM-G965F / 1440×2960）：搜索框下方出现三个排序按钮，「标题」带箭头；
点「歌手」后箭头移位，顺序变为 `Acraze, Cherish → Adele → Adele → AGA`，「81 张专辑」保留。

**③ 手机上专辑详情能看到曲目**

窄屏几何：`.track` 的 `grid-template-columns` = `362px`（单列），
`.track-main` 宽 362px，`.track-title` 宽 136px。修复前分别是 `48px 267px 166px 160px 120px 0px`、48px、0px。

真机：`Dawn FM` 14 首全部显示曲名与「The Weeknd · Dawn FM」，
一路滚到 `Every Angel Is Terrifying` 自然结束，没有截断。
探针量到的 DOM 行数 14 与接口 `track_count` 14 一致。

**手机侧**

`versionCode 426` / `versionName 0.2.168` 覆盖安装成功，`firstInstallTime` 仍是 11-11
（证明是升级不是重装），启动后直接进 `MainActivity`——登录态保留。

部署探针：**25/25 PASS**，`DEPLOY_VERIFY_OK`。

**第二台机器 5.2（10,865 首的大库）**

同一套探针也跑在 5.2 上，同样 **25/25 PASS**。这台机器暴露了三件 5.141 上看不到的事：

1. **安装被一个孤儿进程挡住**。`ss -lntp` 显示 53199 被 `pid=562759, ppid=1` 占着，
   命令行是 `server/server.py --config /usr/local/apps/@appconf/fnaudio/config.json`——
   手工启动、已被 init 收养，应用中心停服务时管不到它。于是升级两次都撞
   「服务端口 53199 已被占用」，`kill` 掉再装就一次通过。**这不是重试能解决的，
   得先把孤儿进程杀掉。**
2. **曲库路径指向了空目录，且原因尚未查清**。配置里 `library_path=/vol2/1000/music`（空），
   真实音乐在 `/vol2/1000/111/music`（344 个 mp3，索引 10,865 首）。
   `/vol1/1000/fnaudio/upgrade-backups/20261118-175418/config.json` 记的旧值正是 `111/music`。

   已知的事实与推断分开写：

   - 事实：`fnaudio.jsonl` 里 `POST /api/config/library` 共 4 条，最后一次成功写入
     `ts=1795060331` = **11:52:11**，当时扫到 `count=10865`——说明那一刻路径是对的。
   - 事实：本次安装后 `@appconf/config.json` 是 **1698 字节**；用接口改回长路径后是 **1706 字节**。
     `/vol2/1000/111/music` 比 `/vol2/1000/music` 长 4 字符、在文件里出现两次，正好差 8 字节。
     所以安装写下去的就是它读到的短路径——**安装沿用了已有值，没有改它**。
   - 推断（未证实）：11:52 改成 `111/music` 之后、13:13 安装之前，这个值被改回了短路径。
     最可疑的是那个 `ppid=1` 的孤儿服务进程：我为了腾端口用 `kill` 结束它，
     若它在退出时把内存里的配置刷回磁盘，就会把 11:52 的改动盖掉。
     这条没有证据，**只作为下次升级要盯的点**。
   - 处置：用产品接口 `POST /api/config/library` 改回 `111/music`，`count` 0 → 10,865。
   - 顺带记下：`/api/library/status` 报 `count=0` 时，专辑接口仍返回旧行，这两个数会不一致。

   下次升级要在安装前后各读一次 `@appconf/config.json` 的 `library_paths` 并比对，
   才能确定到底是谁写的。现在 `install_callback` 不打印它读到/写入的路径，事后无从取证。
3. **服务读的配置路径和 5.141 不同**。5.2 上 `/usr/local/apps/@appcenter/fnaudio/etc/config.json`
   根本不存在，服务是 `--config /usr/local/apps/@appconf/fnaudio/config.json` 启动的。
   也就是说 `reconcile_config_file()` 的「两个目录」假设在 5.2 上退化成同一个文件。

### 6.2 0.2.171（2026-11-20）

0.2.170 **一次都没装上**，所以 0.2.169 之后的第一件真事是「升级被自己的端口校验挡住」。
6.1 的两条界面修复（开关搬家、401 文案）是随 0.2.171 才落到 NAS 上的。

**① 0.2.170 装不上的真因**

- `/var/log/apps/fnaudio.log` 全文只有两行：`服务端口 53199 已被占用，请返回并选择其他端口。`（14:33:04）
- `install_via_app_center.js`：`clicked 同意` → `t+2s status:upgrading` → `t+10s status:start`
  + 界面报「无法更新 fnaudio 执行脚本出错且原因未知」；`/app-center/v1/update/status` 回
  `{"code":10238,"progress":0,"status":3}`
- 死锁形状：`server.py` 与 `mpd` 的 cgroup 都是 `/system.slice/trim_http_cgi.service`，
  `cmd/main stop` 杀掉后 1 秒内出现新 PID，且 `info.log` 里没有 `Starting fnAudio`
  ——**不是我们的脚本起的**；应用中心 `/stop/check`、`/stop/start` 都 `code:0`，
  登记状态却一直是 `start`，卡片上只剩「启用」。fnOS 认为它已停，于是不去停，端口一直占着。
- 修法：`install_callback` 的端口校验带上 `existing_server_port`，扫 `/proc` 认自己的旧实例，
  是升级就放行；外来进程照旧拒绝。

**② 装上去之前又踩的两个坑（都会重犯，必须记住）**

1. **fnOS 执行的是部署目录的 `/var/apps/fnaudio/cmd/install_callback`，不是新包里的那份。**
   改 `src/cmd/*` 并重新出包，对当次升级完全无效——07:00 那次 0.2.171 仍报同样的错。
   直到 `grep -c fnaudio_holder /var/apps/fnaudio/cmd/install_callback` 返回 0 才确认。
   只能把修好的脚本同步进部署目录（备份 `install_callback.bak-R620`），装成功后才被包内版本覆盖。
2. **匹配串不能写死 `fnaudio/server.py`。** 真实路径是 `@appcenter/fnaudio/server/server.py`，
   第一版永远匹配不上，于是每次静默退回「端口被占用」——又白装一次。
   NAS 探针实测：占端口的 `1400869` 的 cmdline 含 `--port 53199`，旧串扫不到它。
   改成 `"/fnaudio/" in raw and "server.py" in raw and needle in raw` 才对上。

**③ 安装结果**

- 应用中心：`0.2.169/start → 0.2.171/starting(35%) → 0.2.171/running`，`INSTALL_OK`
- 经代理 `/api/health`：**200 / 78 ms**
- 页面资源戳：`v=0.2.171-793ac531d5d8`
- 53199 由新 PID `1420712` 持有
- 产物（**发布用，从提交 `f5bcc80` 的干净工作区重出**）：
  `fnaudio-0.2.171-fnpack.fpk` 5,486,834 B / `4A09F496…00F66B`；
  `fnaudio-android-0.2.171-release.apk` 13,013,704 B / `D2C04E36…0E07EAD`
  （`versionCode 429`，`Validated: True`）
- `verify_release_evidence.ps1`：`Validated / AndroidValidated / EvidenceComplete` 三项均 True
- `SOURCE_PROVENANCE`：`git_provenance_status: clean`、`git_tracked_edits: 0`、
  `git_untracked_inputs: 0`、`source_manifest_sha256 77E93164…`（911 行）、`staged_file_count 367`

**③-2 关于「发布包」与「已装机包」字节不同（必读）**

`.141` 上实际运行的是提交前构建的那份 `748C5DDA…`（5,486,956 B），发布的是提交后重出的
`4A09F496…`（5,486,834 B）。**fnpack 的输出不是字节可复现的**：tar 的 mtime 进了包，
`app.tgz` 与 `manifest` 里的 `checksum` 每次都变。逐文件比对的结果：

- 包内 **349 个文件全部一致**（逐个 SHA-256 相同）
- 18 个顶层文件里只有 `app.tgz` 与 `manifest` 不同
- `manifest` 只差 `checksum` 一行，而它就是 `app.tgz` 的 md5
- 两份的 `source_manifest_sha256` 同为 `77E93164…`、`asset_build` 同为 `0.2.171-793ac531d5d8`

所以没有为了「字节一致」再装一遍——要验的是内容，不是 tar 头。
**下次要留意的**：若哪天需要「发布包 == 已装机包」严格成立，得先把 `fnpack` 的
mtime 归一化（或用固定 mtime 重打包），否则只能装完再发。

**④ 真机复验：飞牛 app 载体（`com.trim.app`，远程中转 `office.app.5ddd.com:46533`，无原生桥）**

这一轮**特意换到这个载体**——0.2.169 的复验全做在独立 APK 里，而负责人用的是飞牛 app，
结论不能互推。两条都过了：

- **开关在「播放输出 → 设备身份」**：重载后资源戳 `v=0.2.171-793ac531d5d8`；
  `dlnaRendererEnabledInput` 几何 **16×17 @ (20,596)**，`elementFromPoint` 命中自身，
  `checked:false`，`inputBlock=playback-identity`、`inputPaneId=settings-pane-playback`，
  反证 `switchStillInNetworkPane=false`（「服务与网络」里已没有它）。
  截图 `artifacts/0.2.171/device/feiniu-playback.png` 肉眼可见
  「设备身份 → 作为播放器被其他设备推送 → Renderer 名称」。
- **401 说得出下一步**：用 CDP `Fetch.fulfillRequest` 真造 401 → `playNextTrack()` 返回 `false`，
  提示条文案为「登录已失效，请重新打开 fnAudio 后重试。」。
  （`const browserFetch = window.fetch.bind(window)` 在 `app.js:688` 加载时绑死，
  事后替换 `window.fetch` 拦不住任何请求，造 401 只能走 CDP。）
- **四个运输键可用**：`playNextTrack()` 返回 `true`，`Big Energy → Dawn FM`
  （`src` 从 `5481233725f22278` 换成 `037af5290a618076`）；循环 `one→off`；随机 `false→true`；
  全部请求 200。

**④-2 真机复验：独立 APK 载体（`com.fnaudio.client`，直连 `192.168.5.141:5666`，有原生桥）**

- 覆盖安装 `versionCode 429` / `versionName 0.2.171`，`lastUpdateTime` 15:31:22，
  `firstInstallTime` 仍是 11-11（升级不是重装）
- 开关同在 `playback-identity` 块内、**16×17 @ (20,596)**、可见可点、命中自身、
  `switchStillInNetworkPane=false`；`hasBridge: true`
- 截图 `artifacts/0.2.171/device/apk-playback.png`

两个载体的开关几何完全一样（同一视口），差别只在 `hasBridge`——这正是 401 分支的分水岭：
有桥走自动续期，无桥才说「登录已失效，请重新打开 fnAudio 后重试。」。

**⑤ 门禁**

- JS：**143/143**（含新增 `test_ui_browser_auth_notice.js`）
- Python：**3506 项全过**，`OK (skipped=7)`
- `SOURCE_MANIFEST.sha256`：911 条，已刷新

**⑥ 发布**

提交 `f5bcc80` 与注解标签 `v0.2.171` 已 push，Release 已发：
https://github.com/vinson023/fnaudio/releases/tag/v0.2.171

`v0.2.170` 不发——它从未装上，没有对外发布的理由。

### 6.3 0.2.173（当前版本，2026-11-20）

负责人的话：「renderer开关应该和renderer名称放在一起，不然用户两头找」。

**① 问题不在分类，在距离**

R619 已经把开关从「服务与网络」搬进了「播放与输出 → 设备身份」，分类是对的。
但 DOM 顺序是：开关（带两行 `<small>` 说明）→ 一段 `dialog-help` → 名称输入。
于是同一个面板里，用户仍要往上找开关、往下找名称。

**② 改法**

- 两者收进同一张 `.renderer-identity` 卡片：开关在上，名称紧跟其下
- 两段说明合并成一句，下沉到卡片底部
- 卡片沿用 `.library-health` 的内嵌样式（1px 边框 + 6px 圆角 + `--ui-sidebar` 底色）
- 卡片内把 `.metadata-toggle` 的 `min-height`、`.metadata-settings-grid` 的 `margin` 清零

**③ 真机实测（飞牛 app 与独立 APK 数值完全一致）**

| 量 | 值 |
| --- | --- |
| 卡片 | 380×200 @ (16,589) |
| `nameInSameCard` / `cardContainsBoth` | `true` / `true` |
| 开关 | 17×17 @ (20,603)，`switchHitIsSelf:true` |
| 名称输入 | 354×38 @ (29,655)，label 上沿 631 |
| **开关行下沿 → 名称上沿** | **8px** |
| `blockersBetween` | `[]`（中间没有任何 `<p>` 或 `<small>`） |
| `helpAfterName` | `true`（说明整段在名称之后） |
| `stillInNetworkPane` | `false` |

探针：`tools/browser-e2e/cdp_feiniu_renderer_card.js`；
截图 `artifacts/0.2.173/device/feiniu-renderer-card.png`、
`artifacts/0.2.173/device/apk-renderer-card.png`。

**④ 顺带查出的第二处矛盾：侧栏摘要与输入框各说各的**

设置侧栏「播放与输出」的摘要在进 pane 时就先算过一次，而 `loadPlaybackSettings`
的请求那时还没回来，于是摘要一直显示「跟随设备名」，下面输入框里却已经是
`fnAudio Renderer`。同一件事两处说法不同——和「开关没有」是同一类问题。

修法：采纳服务端回显之后调一次 `updateSettingsSummaries()`。
修完真机 `railSummary` 从「跟随设备名」变成 `fnAudio Renderer`。

**⑤ 0.2.172 为什么作废**

0.2.172 先装上了（`0.2.171 → 0.2.172/running`，health 200），之后才补上摘要那处修复。
再装同一个版本号时被飞牛挡回来：

```
无法安装  fnAudio 已安装相同或更高版本的 fnAudio
```

**同一版本号不能重装。** 于是 0.2.172 作废（`fnOS` 里留着的就是它那份），
改发 0.2.173。教训：同一次改动要一次性出包，装完再改源码就得再吃一个版本号。

**⑥ 安装结果与门禁**

- 应用中心：`0.2.172/upgrading → 0.2.173/starting → 0.2.173/running`，`INSTALL_OK`
- 经代理 `/api/health`：200 / 80 ms
- 产物：`fnaudio-0.2.173-fnpack.fpk` 5,487,117 B / `A67703CE…40248560`
  （provenance clean，基线 `d7b81cb`）；
  `fnaudio-android-0.2.173-release.apk` 13,014,408 B / `158E917B…2BABAF0F`（`versionCode 431`）
- `verify_release_evidence.ps1` 三项全 True
- JS：**143/143**（`test_ui_runtime_settings.js` 新增 6 条断言）
- Python：`Ran 3506 tests in 285.507s` → `OK (skipped=7)`
- 发布：注解标签 `v0.2.173`（锚在构建基线 `d7b81cb`）已 push，Release 已发
  https://github.com/vinson023/fnaudio/releases/tag/v0.2.173 ，
  附件下载回来核对尺寸与 sha256 与本地一致

### 6.4 0.2.167

#### 通过

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

### 6.5 0.2.167 没通过项（历史，均已在 0.2.168 修复）

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
| 后台跑 `load_signing_env.ps1 -ThenBuild`，APK 摘要（`Signed` / `Validated`）都打完了，任务却一直不结束、最后被判失败 | 构建失败 | **构建已经成功了**，那几行摘要就是它自己打的。挂住的是外层管道：`… 2>&1 \| Select-Object -Last 20` 要等上游 stdout 关闭，而 gradle 拉起的 java 进程继承了那个句柄，daemon 不退管道就不关。**这条是推断、没复现**（实测 0.2.170 那次：14:31 构建完成，进程挂到 18:49 才被回收，4h19m）。规避办法：输出重定向到日志文件再读，别接管道 |
| `test_offline.ps1` 立刻中止、日志 0 字节 | 用例失败 | 输出被重定向/接管道，PS 5.1 把 stderr 转成 `ErrorRecord` |
| `git_provenance_status: dirty` | 构建脚本有问题 | 工作区没提交干净 |
| 应用中心弹「无法更新 fnaudio 执行脚本出错且原因未知」+ `Target crashed` | 新包坏了 | 升级瞬间 `install_callback` 用 `sock.bind(("0.0.0.0",53199))` 探端口，旧实例还没退出，于是打印「服务端口 53199 已被占用」并 `exit 1`。**0.2.171 起升级场景已放行自己的旧实例**；0.2.170 及以前**重试也没用**（旧实例被 `trim_http_cgi.service` 保活，杀不掉），见 6.2 |
| 改了 `src/cmd/install_callback`、重新出包，装上去还报同一个错 | 修改没生效 / 包坏了 | fnOS 执行的是**部署目录**的 `/var/apps/fnaudio/cmd/install_callback`，不是新包里的那份。用 `grep -c <新加的标识> /var/apps/fnaudio/cmd/install_callback` 验证，为 0 就是没同步进去 |
| 补发一个旧版本的 Release 后，releases 页的「Latest」标到了旧版本上 | 新版本没标 Latest | GitHub 的 Latest 按**发布时间**挑，不按版本号。补发 0.2.169 之后它就抢了 0.2.173 的标记，用 `gh release edit v0.2.173 --latest` 挪回去 |
| 应用中心弹「无法安装 fnAudio 已安装相同或更高版本的 fnAudio」 | 包做坏了 | **同一版本号不能重装**。改完源码要再装一次，就得先把 `VERSION` / `src/manifest` / `versionCode` 一起往上推。0.2.172 就是这样作废的 |
| 应用中心点「停用」后状态还是 `start`、卡片只剩「启用」 | 我们的 stop 脚本坏了 | `/stop/check`、`/stop/start` 都回 `code:0`，但登记状态不变——fnOS 认为已停，所以不会去停；而 `trim_http_cgi.service` 还在保活 `server.py`，端口照旧被占 |
| `dumpsys package com.fnaudio.player` 什么都不输出 | 应用没装上 | 包名是 `com.fnaudio.client`（另有 `com.fnaudio.client.test` 是 instrumentation 包，versionCode 0，不是应用） |
| `/api/health` 里找不到 `version` | 接口坏了 | health 只有 `ok/name/request_id/components/metrics`；版本在 `/api/access`（前端「关于」也读它） |


---

## 8. 相关文件

- `docs/FNOS_APPCENTER_INSTALL_TEST.md` —— 飞牛安装规程
- `tools/install_via_app_center.js` —— 安装唯一入口
- `tools/app_center_apps.js` —— 应用中心操作（`--list` / `--inspect` / `--click` / `--stop`），
  0.2.171 起用来停用/启应用；按应用名节点收卡片，不按按钮文字找
- `tools/browser-e2e/cdp_feiniu_playback.js` —— 在飞牛 app 内嵌 WebView 里复验设置项位置
- `tools/browser-e2e/cdp_feiniu_renderer_card.js` —— 复验「开关与名称是否挨着」：
  量卡片归属、两行间距、中间有没有段落
- `tools/build_release.ps1` / `tools/build_android_release.ps1` —— 出包
- `tools/load_signing_env.ps1` —— 注入签名变量后构建
- `tools/verify_release_evidence.ps1` —— 产物证据校验
- `tools/adb_wireless.py` —— 无线调试端口发现
- `tools/run_on_nas.py` —— SSH/SFTP 执行诊断脚本
- `artifacts/0.2.168/verify_deployed.js` —— 部署验收探针（24 项，含窄屏层）
- `artifacts/0.2.171/device/feiniu-playback.png` —— 开关搬到「设备身份」后的真机截图
