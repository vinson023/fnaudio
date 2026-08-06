# fnAudio

fnAudio 是面向 fnOS 的本地音乐库与多目标播放器，当前源码与发布版本为 `0.1.154`。

项目同时提供浏览器播放、本机 MPD/ALSA/USB DAC 输出、外部 DLNA 推送，并可作为 DLNA MediaServer 和 MediaRenderer。后端使用 Python 3.12 标准库和 SQLite，前端使用原生 HTML、CSS、JavaScript。

## 当前基线

| 项目 | 值 |
| --- | --- |
| 版本 | `0.1.154` |
| 平台 | fnOS x86 |
| 源码目录 | `C:\path\to\fnAudio\src` |
| 原始来源 | `E:\Codex\fnaudio-0.1.7` |
| HTTP 端口 | `18080` |
| Python | fnOS `python312` |
| 测试基线 | 50 个 Python 单元测试与 2 个 Node 前端回归脚本通过 |

目录名 `fnaudio-0.1.7` 是历史遗留，不代表当前发布版本。版本判断始终以 `src/manifest` 为准。

项目根目录已初始化为 Git 仓库，当前基线位于 `main` 分支并使用 `v0.1.154` 标签标识。FPK、派生检查目录、运行时数据、缓存和嵌套第三方仓库由 `.gitignore` 排除。

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
├── src/                       # 0.1.154 可继续开发源码
│   ├── app/
│   ├── cmd/
│   ├── config/
│   ├── tests/
│   ├── wizard/
│   └── manifest
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
Get-Content manifest -Encoding UTF8
```

Windows 本地验证不能替代 fnOS 真机测试。MPD、FFmpeg、ALSA、USB DAC、fnOS 授权和 DLNA 互操作必须在目标设备复验。

## 文档规则

- 根目录文档描述当前状态，是后续开发的权威来源。
- `docs/history/` 保留原始阶段记录，不应直接当作当前 TODO。
- 每次 AI 修改都要更新 `PROJECT_CONTEXT.md`、`TODO.md` 和 `CHANGELOG_AI.md` 中受影响的部分。
- 每次源码修改后重新生成 `SOURCE_MANIFEST.sha256`，并记录测试结果。
- 不从 `E:\Codex\builds`、旧 FPK 解包目录或旧版本目录直接覆盖当前源码。

## 发布说明

当前可安装 FPK 为 `artifacts/0.1.154/fnaudio-0.1.154.fpk`，由 `src/` 通过官方 `fnpack 1.2.3` 直接构建。包的 SHA-256 为 `81562B56F54490F8C1E84E3D06B76606E2D44AF7B94649C365B364F4B464C2A9`；构建命令、内容摘要和结构校验见同目录的 `VALIDATION.md`、`PACKAGE_CONTENTS.txt` 与 `SHA256SUMS`。

该包已完成本地源码测试和归档结构校验。设备安装尚未完成，当前 fnOS 仍运行 `0.1.153`；原因和尝试记录见 `artifacts/0.1.154/VALIDATION.md`。移动端行为已由源码回归覆盖：紧凑返回/搜索、更多菜单歌词移除，以及到底部才显示分页。

当前设备音乐库为 0 项，故本轮未用真实长列表验证触控滚动、分页操作、歌词实际播放状态或“从当前开始播放全部歌曲”全流程。全新安装、端口变更、停止/启动、两种卸载、USB DAC、移动 WebView 生命周期和 DLNA 互操作也尚未完成，不能据此宣称已完成完整设备端发布验证。

项目许可证尚未明确，不应自行假设开源授权。
