# fnAudio 源码范围清单

> 初次整理日期：2026-08-06  
> 当前源码版本：`0.2.42`（以 `src/manifest` 的 `version` 为准；本行随发布轮次更新）  
> 来源：`E:\Codex\fnaudio-0.1.7`

## 1. 已纳入 `src/`

| 路径 | 内容 |
| --- | --- |
| `src/manifest` | 当前 FPK manifest，版本 `0.2.42` |
| `src/app/server/` | Python 后端及 playback、dlna、services 子包 |
| `src/app/ui/` | HTML、CSS、JavaScript、CGI、图标和 fnOS vendor 脚本 |
| `src/app/target/bin/` | 私有 MPD 可执行文件 |
| `src/app/target/lib/` | 私有 MPD 动态库 |
| `src/app/bin/` | 空占位目录，保留 FPK 结构 |
| `src/app/www/` | 空占位目录，保留历史兼容结构 |
| `src/cmd/` | fnOS 生命周期脚本 |
| `src/config/` | fnOS 权限和资源声明 |
| `src/wizard/` | 安装、配置和卸载向导 |
| `src/tests/` | Python 单元/集成测试、Node UI 回归和本地媒体夹具 |
| `src/ICON*.PNG`、`src/logo*.svg` | 应用图标和历史 logo 资源 |

初次整理时统计（仅为历史来源证据，不代表当前规模）：

- 当前源码共 138 个文件，约 11.9 MB。
- 其中 Python 文件 39 个。
- 自动化测试为 9 个 Python 文件（50 个单元测试）和 2 个 Node 前端回归脚本。
- `src/` 内不包含 `__pycache__`。

## 2. 已纳入 `docs/history/`

- 5 份迁移、开发和阶段文档。
- 1 份整理前完整项目分析快照。
- 1 份播放架构组件说明。
- 65 份原目录已有的 `UPDATE_*.md` 发布片段。
- 本目录的说明文件。

共 73 个历史文档文件。版本片段不连续是原始材料现状。

## 3. 明确排除

| 来源内容 | 排除原因 |
| --- | --- |
| `E:\Codex\builds/` | 大量历史快照和中间包，不能代表唯一当前源码 |
| `fnaudio/`、`fnaudio-0.1.3` 至 `0.1.6` | 旧版本源码 |
| `fnaudio-0.1.7/builds/` | 当前源目录内部历史 UI 构建 |
| `fnaudio-0.1.7/transcode/library.json` | 指向旧 `0.1.6` Windows 绝对路径的陈旧缓存 |
| `fnaudio-0.1.7/*.fpk`、`app.tgz`、runtime 压缩包 | 与最终 `0.1.148` 对应关系未经验证 |
| `tmp-fnaudio-fpk-*`、`fnaudio-pack-stage-*` | 解包和打包暂存目录 |
| `references/`、`fnOS Skill/` | 第三方参考和开发技能，不是产品运行时 |
| `fnaudio-android-shell/` | 独立早期试验项目，不属于当前 fnOS 主应用 |
| `__pycache__/`、`*.pyc` | 解释器生成缓存，不属于源码 |

## 4. 隔离内容

复制过程中发现的 13 个 `.pyc` 被移出 `src/`，保存在 `artifacts/excluded-generated-cache/`。它们不是恢复输入，也不应提交或打包。

## 5. 完整性验证

`SOURCE_MANIFEST.sha256` 包含 `src/` 与 Android 权威源码/构建定义的 SHA-256 和相对路径，排除 build、Gradle 缓存、`.media3-inspect`、字节码和 APK/FPK 等派生物。运行 `tools/update_source_manifest.ps1` 可复现生成；后续以当前清单、可执行源码和 `CHANGELOG_AI.md` 为准。

当文件清单变化时，应同时：

1. 确认变化来自明确开发任务。
2. 运行相应测试。
3. 更新 `CHANGELOG_AI.md`。
4. 重新生成 `SOURCE_MANIFEST.sha256`。
