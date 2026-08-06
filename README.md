# fnAudio

fnAudio 是面向 fnOS 的本地音乐库与多目标播放器，并提供 WebView + 原生媒体服务的轻量 Android 客户端。当前配套版本为 `0.1.162`。

项目同时提供浏览器播放、本机 MPD/ALSA/USB DAC 输出、外部 DLNA 推送，并可作为 DLNA MediaServer 和 MediaRenderer。后端使用 Python 3.12 标准库和 SQLite，前端使用原生 HTML、CSS、JavaScript。

## 当前基线

| 项目 | 值 |
| --- | --- |
| 版本 | `0.1.162` |
| 平台 | fnOS x86；Android 8.0（API 26）及以上 |
| fnOS 源码 | `C:\path\to\fnAudio\src` |
| Android 源码 | `C:\path\to\fnAudio\android-client` |
| 原始来源 | `E:\Codex\fnaudio-0.1.7` |
| HTTP 端口 | `18080` |
| Python | fnOS `python312` |
| 测试基线 | 53 个 Python 单元测试、3 个 Node 回归脚本、Android Lint/Debug 构建通过 |

目录名 `fnaudio-0.1.7` 是历史遗留，不代表当前发布版本。版本判断始终以 `src/manifest` 为准。

项目根目录已初始化为 Git 仓库，当前基线位于 `main` 分支；`0.1.162` 同时版本化 fnOS FPK 和 Android APK。FPK、APK、派生检查目录、运行时数据、缓存和嵌套第三方仓库由 `.gitignore` 排除，但其哈希和验证记录进入版本控制。

## 接手顺序

1. `PROJECT_CONTEXT.md`：当前实现、未完成项、风险和测试状态。
2. `RECOVERY.md`：会话删除或换人后的快速恢复手册。
3. `TODO.md`：当前唯一有效待办列表。
4. `ARCHITECTURE.md`：系统边界、模块和数据流。
5. `DECISIONS.md`：已确认的技术决策及其影响。
6. `CHANGELOG_AI.md`：AI 修改记录，后续只追加不覆盖。

## 目录

```text
C:\path\to\fnAudio
├── PROJECT_CONTEXT.md
├── ARCHITECTURE.md
├── DECISIONS.md
├── TODO.md
├── CHANGELOG_AI.md
├── RECOVERY.md
├── README.md
├── VERSION
├── SOURCE_MANIFEST.sha256
├── src/                       # 0.1.162 fnOS 可继续开发源码
│   ├── app/
│   ├── cmd/
│   ├── config/
│   ├── tests/
│   ├── wizard/
│   └── manifest
├── android-client/            # Android WebView + Media3 客户端
│   ├── app/
│   ├── gradle/
│   ├── gradlew
│   └── gradlew.bat
├── docs/
│   ├── INDEX.md
│   └── history/               # 旧阶段记录，只读参考
└── artifacts/
    └── README.md
```

## 本地验证

```powershell
Set-Location C:\path\to\fnAudio\src
python -B -m unittest discover -s tests -v
node --check app/ui/app.js
node tests/test_ui_queue_columns.js
node tests/test_ui_mobile_layout.js
node tests/test_ui_android_bridge.js
Get-Content manifest -Encoding UTF8

Set-Location C:\path\to\fnAudio\android-client
.\gradlew.bat :app:lintDebug :app:assembleDebug
```

Windows 本地验证不能替代 fnOS/Android 真机测试。MPD、FFmpeg、ALSA、USB DAC、fnOS token 交接、Android 后台/息屏播放和 DLNA 互操作必须在目标设备复验。

## 文档规则

- 根目录文档描述当前状态，是后续开发的权威来源。
- `docs/history/` 保留原始阶段记录，不应直接当作当前 TODO。
- 每次 AI 修改都要更新 `PROJECT_CONTEXT.md`、`TODO.md` 和 `CHANGELOG_AI.md` 中受影响的部分。
- 每次源码修改后重新生成 `SOURCE_MANIFEST.sha256`，并记录测试结果。
- 不从 `E:\Codex\builds`、旧 FPK 解包目录或旧版本目录直接覆盖当前源码。

## 发布说明

当前配套产物位于 `artifacts/0.1.162/`：

- `fnaudio-0.1.162.fpk`：SHA-256 `7253729113AEA07F55B93372EDC78BFE4E04E4EB991D71B3EFADEABD8C17CB9A`。
- `fnaudio-android-0.1.162-debug.apk`：SHA-256 `17898F32B6824C152AF5AA7DE34CE7F8C160547E1BB82028164D785A619C6EF9`。

Android 客户端支持多连接登录、加密 token 历史、登录后直达 fnAudio，并由 Media3 前台服务负责队列和后台播放。配套 FPK 为 Web UI 增加原生桥，并让 CGI 接受同源 token Cookie。

两份产物已完成本地构建、Lint、单元/回归测试、包结构、哈希和 APK 签名检查，但尚未安装到真实 fnOS 与 Android 设备。当前 APK 使用 Android Debug 证书；真机 token 交接、后台/息屏跨曲、自签名 HTTPS、多连接切换和厂商省电限制未验证，不能标记为正式发布。

项目许可证尚未明确，不应自行假设开源授权。
