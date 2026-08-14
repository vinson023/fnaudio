# 0.1.225 真机封面缓存与 Tag 写回验证

## 环境与安装

- 日期：2026-08-12
- fnOS：`198.51.100.24`
- App Center：`fnaudio 0.1.225`，状态 `running`
- HTTP：`Server: fnAudio/0.1.225 Python/3.12.4`
- FPK：`artifacts/0.1.225/fnaudio-0.1.225-fnpack.fpk`
- FPK SHA-256：`0E86B11F41519AD7D17FD49A815031EDDC0784EEA0BB5E58EC45D8C9A136C6AA`

## 根因

旧实现建立专辑缓存时会在 `album_artist` 为空时回退到歌曲艺术家，但 Tag 写回查询只使用空的 `album_artist`。两边生成的 `entity_key` 不一致，导致缓存目录已有封面时，写回任务仍只能看到歌词并被标记为 `done`。专辑封面完成后的批量入队 SQL 也要求空 `album_artist` 等于回退后的艺术家，因此部分歌曲不会进入封面写回队列。

0.1.225 使用 `albums.artist` 作为规范专辑艺术家，按专辑索引为全部相关曲目排队，并用 `tag_write_backfill_version=1` 对已有有效封面缓存执行一次性低优先级回填。迁移不清空缓存、不重复下载，第二次启动不会再次重排已完成任务。

## 全库基线

- 精确按生产 `entity_key` 匹配后，共有 99 个“可写媒体 + 有效缓存封面”候选。
- 写回前 92 个候选没有 `attached_pic`，所有 99 个文件均可由 `ffprobe` 读取。
- 安装迁移后，数据库标记为 `tag_write_backfill_version=1`，Tag 任务状态为 `done=93`、`pending=116`。
- 两个验证样本完成后再次探测，缺封面候选从 92 降到 90；后台样本任务从 `pending` 变为 `done`，无 `last_error`。

## 后台端到端样本

歌曲：`/vol1/1000/777/NEW/Steve Lacy - Bad Habit.mp3`

- 写回前 SHA-256：`C1CE3134823BFC7110B3B71A57221B51FFC97FB499C9F02806A34BCC1301CDC9`
- 原样备份：`/vol1/1000/fnaudio-cover-test-backup-Bad-Habit.mp3`，哈希与源文件一致。
- 缓存封面 SHA-256：`69EE43A36F657BAAE6E35993236244904D7B59885CF3BBF644DDC316EEE62EE9`
- 写回前：1 个音频流，0 个 `attached_pic`，完整音频解码成功。
- 仅调用 `prioritize_track()` 后，运行中的后台工作线程在 15 秒内完成任务。
- 写回后：2 个流，`attached_pic=1`；提取封面 SHA-256 与缓存封面完全一致。
- 写回后 SHA-256：`DF1739C145062BC44014E1B5AC115C2EC6A41C83E992EC075232F2FC543A370B`。
- 写回后完整音频解码成功；title、artist、album、lyrics 和 duration 均保持不变。
- owner/mode 从 `root:root 000` 保持为 `root:root 000`。该异常严格权限是测试库既有状态，不是写回造成的变化。

## 辅助样本边界

`Ed Sheeran - Bad Habits.flac` 验证了缓存键修复、封面嵌入、逐字节提取和原 Tag 保留。其原始备份与写回后文件执行完整解码时都会报告相同的 FLAC 帧错误，因此该文件不作为“写回后完整解码成功”的证据。原样备份保留在 `/vol1/1000/fnaudio-cover-test-backup-Bad-Habits.flac`。

## 证据

完整的前后 `ffprobe` JSON、SQLite 只读快照、候选探测脚本和迁移状态脚本位于 `artifacts/0.1.225/real-device/`。数据库快照的 `PRAGMA integrity_check` 均为 `ok`。
