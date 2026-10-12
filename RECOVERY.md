# fnAudio 快速恢复手册

> 用途：AI 会话删除、换开发者或长时间中断后，只依赖 `C:\path\to\fnAudio` 恢复开发。

## 五分钟恢复

1. 固定工作目录为 `C:\path\to\fnAudio`，不要从 `E:\Codex`、旧 FPK 解包目录或 `artifacts/` 覆盖源码。
2. 阅读 `PROJECT_CONTEXT.md` 顶部、`TODO.md`、`DECISIONS.md` 最新决策和 `CHANGELOG_AI.md` 末尾。
3. 运行 `git status --short`。工作树可能包含用户或前一会话的未提交修改，禁止 reset、checkout 或清理未知文件。
4. 核对 `VERSION`、`src/manifest`、Web 静态资源版本和 Android `versionName/versionCode`。当前源码基线为 `0.2.51`；若版本继续演进，以 `VERSION` 和 `src/manifest` 的一致值为准。
5. 运行统一离线验证；涉及 Android 时再运行 JVM 测试、Lint 和 Debug 构建。
6. 查看 `TODO.md`。本地 1-9 连续目标已完成，剩余项目都依赖 fnOS、外部数据、模拟器/设备或负责人决策。

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_offline.ps1 -Browser

Set-Location C:\path\to\fnAudio\android-client
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug :app:assembleDebug

Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_android_emulator.ps1
```

需要同时验包时运行：

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_offline.ps1 -Package -Browser
```

恢复脚本的参数都有可用默认值，通常不带参数直接运行；下面是模拟器脚本 `tools\test_android_emulator.ps1`
的完整参数面：`-AvdName` 指定复用的 AVD（默认 `fnaudio-api35-atd`），`-SdkRoot` 指定 Android SDK
根目录（默认取环境变量 `ANDROID_SDK_ROOT`，再退回 `C:\path\to\fnAudio\tools\android-sdk`），`-InstallSdk`
允许脚本先安装缺失的 SDK 组件，`-KeepRunning` 在回归结束后保留模拟器以便继续排查。

## 发布证据快速盘点

会话丢失或需要接手历史版本时，可用只读索引工具扫描 `artifacts` 下的语义版本目录：

```powershell
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\index_release_evidence.ps1 -ArtifactRoot .\artifacts -MaxEntries 256
```

如需把盘点结果固化为会话恢复附件，可使用显式 `-OutputPath`（脚本默认仍只读）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\index_release_evidence.ps1 `
  -ArtifactRoot .\artifacts -MaxEntries 256 `
  -OutputPath .\artifacts\release-evidence-index-latest.json
```

该工具不会修改源码或发布产物，只读取每个版本目录并复用
`tools\verify_release_evidence.ps1 -Json` 生成机器可读结果。输出中的
`EvidenceComplete=false` 表示该版本缺少可验证的 provenance、源码清单或其他证据，
不等同于 FPK 损坏；尤其是早期版本可能只有 FPK 和 SHA256。单个目录失败会被记录并继续扫描，
因此可直接把输出保存为恢复盘点附件，而不会因一个历史目录损坏而中断。

校验器对产物尺寸有上界：`SHA256SUMS` 记录的每个产物默认不超过 10 GiB，Android 侧车默认不超过
1 GiB，两者都在计算 SHA-256 之前拒绝，避免为一篇损坏的证据去哈希任意大的文件。
这两个上界是显式参数 `-MaxArtifactBytes` 与 `-MaxAndroidArtifactBytes`，默认值就是发布策略，
恢复流程不需要传；传 0 或负数会被直接拒绝。回归测试用注入的小上界以字节规模验证这两条守卫，
因此门禁不再需要构造十吉字节的样例文件。

## 权威来源

发生冲突时按以下顺序判断：

1. `src/`、`android-client/` 中的可执行源码和自动测试。
2. 根目录 `PROJECT_CONTEXT.md`、`TODO.md`、`DECISIONS.md`。
3. `SOURCE_MANIFEST.sha256`、`CHANGELOG_AI.md` 和最近的验证文档。
4. `docs/history/`、旧 `artifacts/<version>/` 与第三方参考源码。

`docs/history/` 只用于追溯，不能把其中的旧 TODO 或旧 DSD/认证策略重新带回当前实现。

## 当前架构要点

- 后端是 Python 3.12 `ThreadingHTTPServer`，曲库与用户状态使用 SQLite/WAL。
- `PlaybackCore` 是队列和播放状态权威源；Browser、Android、MPD/USB DAC、DLNA Push 通过输出适配器执行。
- Android 使用 WebView + Media3 前台服务；远程输出只镜像同一服务端快照并通过 MediaSession 回传控制。
- Android 自签名 HTTPS 使用按连接保存的完整 DER 证书 SHA-256 指纹。首次登录在发送凭据前固定，后续证书变化必须拒绝。
- DLNA 出站地址受 LAN、协议、重定向、响应大小和超时边界约束；受保护非 DLNA API 只接受带 fnOS token 与 scope 的回环代理请求。
- Linux 曲库变化优先使用 inotify；不可用、溢出或真实变更时回退完整签名扫描。
- `upmpdcli_renderer.py` 只做外部兼容探测，不由 fnAudio 管理、不可选且不占用音频设备。
- MPD 默认 `mixer_type=none` 保持 bit-perfect；hardware 只接受真实 Playback Volume 控件，不可用时回退固定音量；software 明确不是 bit-perfect。
- 私有目录/文件分别为 `0700/0600`，公开 UI 目录/文件为 `0755/0644`；媒体 Tag 原子替换保留原属主和 mode。
- 主服务暂保留 fnOS 声明的 root 身份，直到有可靠共享目录 ACL、ALSA 组和 SSDP 权限契约。

## 关键路径

| 内容 | 路径 |
| --- | --- |
| fnOS 源码 | `C:\path\to\fnAudio\src` |
| Android 源码 | `C:\path\to\fnAudio\android-client` |
| 统一离线验证 | `C:\path\to\fnAudio\tools\test_offline.ps1` |
| 可复现 FPK 构建 | `C:\path\to\fnAudio\tools\build_release.ps1` |
| 源码清单生成 | `C:\path\to\fnAudio\tools\update_source_manifest.ps1` |
| Android 模拟器回归 | `C:\path\to\fnAudio\tools\test_android_emulator.ps1` |
| 当前待办 | `C:\path\to\fnAudio\TODO.md` |
| 专项设计文档 | `C:\path\to\fnAudio\docs\INDEX.md` |

## 禁止事项

- 不得把真实 token、密码、Cookie、NAS 数据库、媒体绝对路径或签名密钥写入仓库、日志、截图和测试夹具。
- 不得因为目录名或产物时间较新，就用构建副本覆盖 `src/`。
- 不得把 Windows/模拟测试描述为 USB DAC、Renderer、AirPlay 或 Android 真机通过。
- DSD 对 MPD/USB DAC 和 DLNA Renderer 必须保持原始 DSF/DFF；不支持时明确失败，禁止静默 PCM fallback。
- Tag 恢复只能来自已确认备份；没有备份时只允许审计，不得推测写回。

## 每次开发结束

1. 运行与改动风险匹配的测试，并记录未运行的设备测试。
2. 更新 `PROJECT_CONTEXT.md`、`TODO.md`、`CHANGELOG_AI.md`；架构取舍变化时追加 `DECISIONS.md`。
3. 运行 `tools\update_source_manifest.ps1` 重新生成 `SOURCE_MANIFEST.sha256`。
4. 运行 `git diff --check` 和 `git status --short`，不要提交运行时缓存、凭据或构建中间目录。
5. 构建产物必须从权威 `src/` 生成并记录 SHA-256，不能复用未知来源 FPK。

## 新会话提示词

```text
请接手 C:\path\to\fnAudio。先完整阅读 PROJECT_CONTEXT.md、RECOVERY.md、TODO.md、
ARCHITECTURE.md、DECISIONS.md、CHANGELOG_AI.md 和 docs/INDEX.md，核对 VERSION、
src/manifest 与 SOURCE_MANIFEST.sha256，并查看 git status --short。不要清理未提交修改，
不要从旧构建或历史目录覆盖源码。先运行 tools/test_offline.ps1 -Browser；涉及 Android
再运行 testDebugUnitTest、lintDebug、assembleDebug 和 tools/test_android_emulator.ps1。只按 TODO.md 中仍未完成且环境具备的事项继续。
```
