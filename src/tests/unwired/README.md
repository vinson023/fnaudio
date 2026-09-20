# 无生产消费者的独立模块（R119）

本目录下的 Python 文件不在 `src/app/` 里，因此**不会进入 fpk 发包**：
`tools/build_release.ps1` 用 `robocopy /E /XD tests __pycache__` 从 `src/` 暂存时，
按目录名剔除任何名为 `tests` 的目录；它们仍然被 `tools/update_source_manifest.ps1`
覆盖（清单只排除 `.gradle`、`build`、`__pycache__` 等），所以逐文件 sha 审查继续有效。

保留在本目录而不是删除的原因逐文件记录在 TODO.md 与 CHANGELOG_AI.md 的 R119 条目里：

- `alsa_player.py`：带 shebang 与 argparse 的手工 ALSA 诊断入口，工作树里有未提交的
  改动，删除后 git 无法恢复；全仓 400 个生产文件、fpk 打包脚本、设备侧脚本与 git
  历史都没有按文件名调用它。
- `playback_session_contract.py`：宿主等价播放会话契约（participant / generation /
  engine epoch / keep-alive / command ticket），设备侧 `Android 等价 MediaSession`
  待办仍要求它，不能删。

两者的测试留在 `src/tests/` 顶层（`test_alsa_player.py`、
`test_playback_session_contract.py`），因为离线门禁用的是
`python -B -m unittest discover -s tests`，它不会下探没有 `__init__.py` 的子目录。
本目录的全部前提由 `src/tests/test_orphan_module_retirement.py` 钉住。
