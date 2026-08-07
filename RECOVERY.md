# fnAudio 快速恢复手册

> 用途：AI 会话被删除、换开发者、换机器或长时间中断后，仅依赖 `C:\path\to\fnAudio` 恢复开发上下文。

## 1. 五分钟恢复

1. 打开 `C:\path\to\fnAudio\PROJECT_CONTEXT.md`，确认当前版本、已实现功能、风险和测试基线。
2. 打开 `C:\path\to\fnAudio\TODO.md`，选择最上方未完成且已具备条件的事项。
3. 涉及系统边界时查看 `ARCHITECTURE.md`，涉及取舍时查看 `DECISIONS.md`。
4. 查看 `CHANGELOG_AI.md` 的最新记录，确认上次修改和未验证内容。
5. 在 `C:\path\to\fnAudio` 运行 `git status --short`，确认是否有未提交工作。
6. 核对根 `VERSION`、`src/manifest` 和 `android-client/app/build.gradle` 必须统一为 `0.1.171`。
7. 阅读 `artifacts/0.1.171/VALIDATION.md`，确认当前 FPK/APK 的本地验收；更低版本目录都是历史记录。
8. 运行基线测试和源码清单校验。

```powershell
Set-Location C:\path\to\fnAudio\src
Get-Content manifest -Encoding UTF8
python -B -m unittest discover -s tests -v
node --check app/ui/app.js
node tests/test_ui_queue_columns.js
node tests/test_ui_mobile_layout.js
node tests/test_ui_android_bridge.js

Set-Location C:\path\to\fnAudio
Get-FileHash src\manifest,src\app\server\server.py,src\app\ui\app.js -Algorithm SHA256
```

## 2. 新会话启动提示词

新建 AI 会话时可以直接使用以下提示：

```text
请接手 C:\path\to\fnAudio 项目。当前配套基线是 0.1.170，fnOS 源码在 C:\path\to\fnAudio\src，Android 源码在 C:\path\to\fnAudio\android-client。
开始前请完整阅读 PROJECT_CONTEXT.md、RECOVERY.md、TODO.md、ARCHITECTURE.md、
DECISIONS.md 和 CHANGELOG_AI.md，并核对 src/manifest 与 SOURCE_MANIFEST.sha256。
docs/history 只用于追溯，不是当前需求来源；不要从 E:\Codex\builds 或旧版本目录覆盖源码。
先运行现有测试并报告基线，再根据 TODO.md 的最高优先级继续。完成后同步更新根目录上下文、
待办、AI 修改记录和源码哈希清单。
```

## 3. 权威来源顺序

发生冲突时按以下优先级判断：

1. `src/` 中可执行源码和 `src/manifest`。
2. 根目录 `PROJECT_CONTEXT.md`、`TODO.md`、`DECISIONS.md`。
3. `SOURCE_MANIFEST.sha256` 和最近一次验证记录。
4. `docs/history/` 中的旧阶段文档。
5. `E:\Codex` 中的历史目录、构建快照和解包产物。

历史文档可能描述当时计划或旧路径，不能覆盖当前源码事实。

## 4. 恢复快照身份

| 项目 | 值 |
| --- | --- |
| 产品 | fnAudio |
| 基线版本 | `0.1.170` |
| 整理日期 | 2026-08-06 |
| 原始源码 | `E:\Codex\fnaudio-0.1.7` |
| fnOS 源码 | `C:\path\to\fnAudio\src` |
| Android 源码 | `C:\path\to\fnAudio\android-client` |
| Git 基线 | `main` 分支；当前发布标签 `v0.1.170` |
| 已构建 FPK | `C:\path\to\fnAudio\artifacts\0.1.170\fnaudio-0.1.170.fpk` |
| FPK SHA-256 | `3996D1E8E4E693EF889B46845F3ED59D677C5BD2B2A3295345485DDDD4FA7493` |
| Android Debug APK | `C:\path\to\fnAudio\artifacts\0.1.170\fnaudio-android-0.1.170-debug.apk` |
| APK SHA-256 | `1D4CE15B07B46289DC277A4EB26CCB7FFCA29488A6A1E29D41EC812C171A41BF` |
| 已验证测试包 | `C:\path\to\fnAudio\artifacts\0.1.149\fnaudio-0.1.149.fpk`（仅升级验证） |
| 测试包 SHA-256 | `B7FD239E26D69AC16CE8C1F4B788AE6528F47E2DBA479FCC33B1CD9B0B507AA0` |
| manifest 原始 SHA-256 | `9170B93C59BE249579805E7075FAD6DFE5A8F99511BEA5488DE3B0AA5D9140EA` |
| server.py 原始 SHA-256 | `37E82F89827A95987F6481079945E8A09270C72DF1CD0CC818CA2B137A961093` |
| app.js 原始 SHA-256 | `8ED763723EB02C97B4CCB918EA452E48DCE2984A24A72724C86078D0D599BBF6` |
| 当前测试基线 | 59 个 Python 测试、3 个 Node 回归脚本、Android Lint/Debug 构建通过；`0.1.170` 媒体卡片、右键/长按菜单、多连接、原生认证和返回流程待真机安装 |

完整源码哈希见 `SOURCE_MANIFEST.sha256`。上述三个关键哈希用于快速判断是否仍是初始整理基线；后续正常开发会改变它们，变更必须记录在 `CHANGELOG_AI.md`。

## 5. 已知事实

- 项目是 fnOS FPK，不是普通 Windows 桌面程序。
- Python 服务默认监听 `0.0.0.0:18080`，多数 API 当前没有统一鉴权。
- FPK 权限声明为 root。
- 音乐库和元数据使用 `library.sqlite3`，用户状态使用 `state.sqlite3`。
- 本机播放主要依赖私有 MPD、ALSA 和 fnOS FFmpeg。
- fnAudio 同时实现 DLNA Control Point、MediaServer 和 MediaRenderer。
- `android-client/` 是当前正式开发目录，不要再使用 `E:\Codex\fnaudio-android-shell` 的历史试验文件。
- Android 采用 WebView UI + Media3 原生播放；登录走 fnOS WebSocket，Keystore 加密地址、账号、密码和 token/longToken，历史连接通过独立页面管理。
- Android 客户端必须与 `0.1.170` 或更新 FPK 配套，当前产物和校验记录位于 `artifacts\0.1.170\`。
- `0.1.170` 的媒体卡片规则：通知小图标为白色播放圆环；无真实 artwork 时引用应用私有目录的一份透明底白色 PNG；真实封面优先，禁止为每个队列项目嵌入重复位图字节。
- `0.1.169` 的歌曲行菜单规则：桌面右键、移动端 550ms 长按，共享固定四项；长按移动超过 10px 或列表滚动即取消，成功后必须拦截松手合成点击。“收藏歌曲”只添加，“从当前开始播放所有歌曲”必须读取完整当前上下文。
- 多连接历史的关键规则：host、端口、协议或账号变化默认新增；历史页“编辑”才覆盖；“新增连接”清空表单。若列表仍只有一项，先检查 `profileIdForForm()` 是否错误复用了活动 UUID。
- `0.1.167` 的关键修复是原生认证非 GET API：真实 HTTP 200 队列错误的响应体是 fnOS nginx 返回的 `invalid token`，不是 fnAudio JSON。排障时先确认网页调用 `apiFetch()`、Android 桥存在 `requestJson()`，再检查原生请求是否携带 token Header/Cookie。
- 根页面返回不再调用 `moveTaskToBack(true)`；第一次提示，2.2 秒内第二次进入登录页。该入口必须设置 `EXTRA_SKIP_AUTO_RESUME`，否则登录页会立即恢复旧连接。
- `artifacts\0.1.149\` 是以旧 `src` 完整副本、仅修改版本号构建的真机升级测试产物。它已验证设备升级、启动、端口和核心 API，但绝不能作为开发源码或替代 `0.1.170` 基线。

## 6. 禁止事项

- 不要因为目录名较新就从 `E:\Codex\builds` 复制文件覆盖 `src/`。
- 不要把 `docs/history/` 的未完成 checklist 直接合并到当前 TODO，先对照代码和测试。
- 不要把真实 Spotify secret、fnOS token、NAS 路径数据库或用户状态提交到版本库。
- 不要把 Android 登录密码、token、Cookie、WebSocket 报文或真实设备地址写入文档、测试夹具、日志和截图。
- 不要宣称 MPD、USB DAC、WebView 或 DLNA 已完成，仅凭 Windows 单元测试不足以证明真机行为。
- 不要在未确认包源的情况下发布原工作区现成 FPK。
- 不要删除历史文档；需要废弃时在 `DECISIONS.md` 记录并移动到更明确的归档目录。

## 7. 每次开发结束必须做

1. 运行与改动风险相匹配的测试。
2. 更新 `CHANGELOG_AI.md`，记录文件、行为、验证和未验证项。
3. 更新 `TODO.md` 的完成状态和新增工作。
4. 若实现状态、风险或目录变化，更新 `PROJECT_CONTEXT.md`。
5. 若改变架构取舍，向 `DECISIONS.md` 追加新决策或标记旧决策废弃。
6. 重新生成 `SOURCE_MANIFEST.sha256`。
7. 若改 Android，同时运行 `android-client\gradlew.bat :app:lintDebug :app:assembleDebug` 并记录 APK 身份。
8. 检查 `git status --short`，提交内容明确的 Git commit；不要只依赖会话历史。

## 8. 清单重新生成

在 PowerShell 中从项目根目录执行：

```powershell
Set-Location C:\path\to\fnAudio
Get-ChildItem src,android-client -Recurse -File |
  Where-Object {
    $_.FullName -notmatch '\\(build|\.gradle)\\' -and
    $_.Name -ne 'local.properties' -and
    $_.Extension -notin '.fpk', '.apk'
  } |
  Sort-Object FullName |
  ForEach-Object {
    $relative = $_.FullName.Substring((Resolve-Path .).Path.Length + 1).Replace('\', '/')
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    "$hash  $relative"
  }
```

将结果以 UTF-8 写入 `SOURCE_MANIFEST.sha256`。更新清单时不要把运行时数据库、缓存、凭据或 `__pycache__` 纳入源码。

## 9. 遇到文档与代码不一致时

先用代码和测试确定真实行为，再修正文档。不要为了符合旧文档去回滚现有实现。若不一致涉及产品方向而非事实判断，先在 `DECISIONS.md` 写明候选方案和影响，再决定代码改动。
