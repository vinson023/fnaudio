# fnAudio 快速恢复手册

> 用途：AI 会话被删除、换开发者、换机器或长时间中断后，仅依赖 `C:\path\to\fnAudio` 恢复开发上下文。

## 1. 五分钟恢复

1. 打开 `C:\path\to\fnAudio\PROJECT_CONTEXT.md`，确认当前版本、已实现功能、风险和测试基线。
2. 打开 `C:\path\to\fnAudio\TODO.md`，选择最上方未完成且已具备条件的事项。
3. 涉及系统边界时查看 `ARCHITECTURE.md`，涉及取舍时查看 `DECISIONS.md`。
4. 查看 `CHANGELOG_AI.md` 的最新记录，确认上次修改和未验证内容。
5. 在 `C:\path\to\fnAudio` 运行 `git status --short`，确认是否有未提交工作。
6. 核对 `src/manifest` 必须包含 `version=0.1.151`。
7. 阅读 `artifacts/0.1.151/VALIDATION.md` 确认当前包的本地与设备验收；`artifacts/0.1.149/` 和 `artifacts/0.1.150/` 仅是历史记录，不是当前开发基线。
8. 运行基线测试和源码清单校验。

```powershell
Set-Location C:\path\to\fnAudio\src
Get-Content manifest -Encoding UTF8
python -B -m unittest discover -s tests -v
node --check app/ui/app.js
node tests/test_ui_queue_columns.js

Set-Location C:\path\to\fnAudio
Get-FileHash src\manifest,src\app\server\server.py,src\app\ui\app.js -Algorithm SHA256
```

## 2. 新会话启动提示词

新建 AI 会话时可以直接使用以下提示：

```text
请接手 C:\path\to\fnAudio 项目。当前唯一基线是 0.1.151，源码在 C:\path\to\fnAudio\src。
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
| 基线版本 | `0.1.151` |
| 整理日期 | 2026-08-06 |
| 原始源码 | `E:\Codex\fnaudio-0.1.7` |
| 当前源码 | `C:\path\to\fnAudio\src` |
| Git 基线 | `main` 分支，标签 `v0.1.151` |
| 已构建 FPK | `C:\path\to\fnAudio\artifacts\0.1.151\fnaudio-0.1.151.fpk` |
| FPK SHA-256 | `05CC22B336A9AC821B0166A31D401B0383A425DA88679CA928604F8FCBB6A039` |
| 已验证测试包 | `C:\path\to\fnAudio\artifacts\0.1.149\fnaudio-0.1.149.fpk`（仅升级验证） |
| 测试包 SHA-256 | `B7FD239E26D69AC16CE8C1F4B788AE6528F47E2DBA479FCC33B1CD9B0B507AA0` |
| manifest 原始 SHA-256 | `9170B93C59BE249579805E7075FAD6DFE5A8F99511BEA5488DE3B0AA5D9140EA` |
| server.py 原始 SHA-256 | `37E82F89827A95987F6481079945E8A09270C72DF1CD0CC818CA2B137A961093` |
| app.js 原始 SHA-256 | `8ED763723EB02C97B4CCB918EA452E48DCE2984A24A72724C86078D0D599BBF6` |
| 当前测试基线 | 50 个 Python 单元测试与 1 个 Node 前端回归脚本通过；fnOS 已完成 `0.1.150 -> 0.1.151` 覆盖升级和队列切歌 UI 验证 |

完整源码哈希见 `SOURCE_MANIFEST.sha256`。上述三个关键哈希用于快速判断是否仍是初始整理基线；后续正常开发会改变它们，变更必须记录在 `CHANGELOG_AI.md`。

## 5. 已知事实

- 项目是 fnOS FPK，不是普通 Windows 桌面程序。
- Python 服务默认监听 `0.0.0.0:18080`，多数 API 当前没有统一鉴权。
- FPK 权限声明为 root。
- 音乐库和元数据使用 `library.sqlite3`，用户状态使用 `state.sqlite3`。
- 本机播放主要依赖私有 MPD、ALSA 和 fnOS FFmpeg。
- fnAudio 同时实现 DLNA Control Point、MediaServer 和 MediaRenderer。
- Android WebView 壳不是当前主项目，也没有合入本恢复目录。
- 原工作区中的现有 FPK 未被确认与当前源码一致，因此没有作为发布基线复制；当前 FPK 是从 `C:\path\to\fnAudio\src` 重新构建的唯一可追溯包，内容和本地/设备校验记录位于 `artifacts\0.1.151\`。
- `artifacts\0.1.149\` 是以旧 `src` 完整副本、仅修改版本号构建的真机升级测试产物。它已验证设备升级、启动、端口和核心 API，但绝不能作为开发源码或替代 `0.1.151` 基线。

## 6. 禁止事项

- 不要因为目录名较新就从 `E:\Codex\builds` 复制文件覆盖 `src/`。
- 不要把 `docs/history/` 的未完成 checklist 直接合并到当前 TODO，先对照代码和测试。
- 不要把真实 Spotify secret、fnOS token、NAS 路径数据库或用户状态提交到版本库。
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
7. 检查 `git status --short`，提交内容明确的 Git commit；不要只依赖会话历史。

## 8. 清单重新生成

在 PowerShell 中从项目根目录执行：

```powershell
Set-Location C:\path\to\fnAudio
Get-ChildItem src -Recurse -File |
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
