# fnAudio

fnAudio 是面向 fnOS 的本地音乐库与多目标播放器，并提供 WebView + 原生媒体服务的轻量 Android 客户端。当前配套版本为 `0.2.61`。

项目同时提供浏览器播放、本机 MPD/ALSA/USB DAC 输出、外部 DLNA 推送，并可作为 DLNA MediaServer 和 MediaRenderer。后端使用 Python 3.12 标准库和 SQLite，前端使用原生 HTML、CSS、JavaScript。

## 当前基线

| 项目 | 值 |
| --- | --- |
| 版本 | `0.2.61` |
| 平台 | fnOS x86；Android 6.0（API 23）及以上 |
| fnOS 源码 | `C:\path\to\fnAudio\src` |
| Android 源码 | `C:\path\to\fnAudio\android-client` |
| 原始来源 | `E:\Codex\fnaudio-0.1.7` |
| HTTP 端口 | 配置决定，安装默认 `53199` |
| Python | fnOS `python312` |
| 测试入口 | `tools/test_offline.ps1 -Browser`；Android 使用 `testDebugUnitTest lintDebug assembleDebug` |

目录名 `fnaudio-0.1.7` 是历史遗留，不代表当前发布版本。版本判断始终以 `src/manifest` 为准。

项目根目录已初始化为 Git 仓库，当前基线位于 `main` 分支；`0.2.61` 同时版本化 fnOS FPK 和 Android APK。FPK、APK、派生检查目录、运行时数据、缓存和嵌套第三方仓库由 `.gitignore` 排除，但其哈希和验证记录进入版本控制。

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
├── src/                       # 当前 fnOS 可继续开发源码
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
Set-Location C:\path\to\fnAudio
powershell -NoProfile -ExecutionPolicy Bypass -File tools\test_offline.ps1

Set-Location C:\path\to\fnAudio\android-client
.\gradlew.bat :app:lintDebug :app:assembleDebug
```

Windows 本地验证不能替代 fnOS/Android 真机测试。MPD、FFmpeg、ALSA、USB DAC、fnOS token 交接、Android 后台/息屏播放和 DLNA 互操作必须在目标设备复验。

## 文档规则

- 根目录文档描述当前状态，是后续开发的权威来源。
- `docs/history/` 保留原始阶段记录，不应直接当作当前 TODO。
- 每次修改都要更新 `PROJECT_CONTEXT.md`、`TODO.md` 和 `CHANGELOG_AI.md` 中受影响的部分。
- 每次源码修改后重新生成 `SOURCE_MANIFEST.sha256`，并记录测试结果。

## 发布说明

当前发布基线为 `0.2.61`；下方旧版本记录仅用于历史追溯。

当前开发版本为 `0.2.61`。Android 的 FN Connect 可在公网与 P2P 中继间显式选择，并按短 token、longToken、加密保存密码的顺序重建会话。后台元数据抓取与歌曲 Tag 写回是两个独立设置；写回默认关闭。FPK 必须通过 `tools/build_release.ps1` 从唯一的 `src/` 源目录构建；产物位于 `artifacts/0.2.61/`。播放栈对比和限制见 `docs/PLAYBACK_STACK_COMPARISON.md`。

当前离线工程状态包括 DLNA 出站网络边界、API scope 授权、结构化可观测性、用户状态并发合并、10 万曲分页基准、ContentDirectory 浏览语义和 WAV/DFF 边缘格式夹具。恢复会话后先运行 `tools/test_offline.ps1`，再依据 `TODO.md` 选择仍未完成的部署或硬件项目。

2026-08-12 的九项连续离线目标还包括资源预算、播放错误分类、兼容 API 拆分、浏览器 E2E、inotify 曲库检测、Renderer/Mixer 策略、Android HTTPS 证书固定，以及文件权限/路径边界。专项说明见 `docs/INDEX.md`。

`0.2.22` FPK 已安装到内网 fnOS并通过健康、音乐库和鉴权烟雾测试。`0.2.23` Android Debug APK 增加公网/P2P 中继显式选择，当前仍使用 Debug 证书；正式分发必须使用负责人持有的 Release keystore。

项目许可证为 GPL-3.0-or-later（第 3 版或其后任一版本，由使用者选择），完整逐字正文见 `LICENSE`，版权持有人与维护者见 `AUTHORS`，再分发义务与托管现状见 `NOTICE`。2026-09-20 负责人裁定开源、暂不托管，`git remote -v` 实测为空，因此在建立公开源码地址之前，对外分发 FPK 或 APK 必须按 `NOTICE` 随包提供对应源码。
