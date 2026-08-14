# 0.1.205 真机 MPD 重启恢复记录

## 0.1.222 follow-up

- A controlled TEAC UD-301 MPD restart was repeated on 2026-08-11.
- The supervisor started a new MPD process and PlaybackCore returned to
  `PLAYING`; `restart_count=1` and `recovery_count=1` were observed.
- `tools/real_device_mpd_restart_run.sh` now restores target, queue and the
  final transport state in that order. This avoids leaving a previously stopped
  user session playing after acceptance.
- Raw evidence: `artifacts/0.1.222/real-device/fnaudio-mpd-restart-0.1.222.log`.

日期：2026-08-10

## 环境

- 真机：`vinson023.eu.org:3100`
- fnOS App Center：`vinson023.eu.org:5666`
- fnAudio：`0.1.205`
- DAC：TEAC UD-301
- ALSA：`hw:CARD=UD301,DEV=0`
- MPD：56660

## 安装与状态保留

通过 fnOS App Center UI 的“手动安装 → 从 NAS 添加”选择 `/vol1/1000/fnaudio-0.1.205.fpk`，确认未验证应用提示后完成覆盖升级。SSH 只读确认服务头为 `fnAudio/0.1.205 Python/3.12.4`，音乐库、20 首 MPD 队列、当前 DAC 选择均保留。

## MPD 异常恢复

1. 通过 `mpd:` 目标开始真实播放 44.1 kHz FLAC。
2. 在播放中使用 root 权限终止 MPD 进程 PID `105795`。
3. supervisor 自动拉起新 MPD PID `106803`，`restart_count=1`。
4. 恢复后观测到：
   - MPD 原始状态：`play`
   - `playlistlength=20`
   - 当前歌曲保持不变
   - 进度从恢复位置继续增长（约 63 秒）
   - `idle.transport=PLAYING`
   - `fault.state=PLAYING`
   - `underrun.count=0`

这验证了 0.1.204/0.1.205 的恢复状态同步修复在 0.1.205 真机上生效。

恢复后的追加采样（间隔约 10 秒）为 44.71 秒、55.34 秒、65.72 秒，均保持 MPD `play`、`idle.transport=PLAYING`、`fault.state=PLAYING` 和 `underrun=0`，并显示下一曲索引 `19` 已由 MPD 原生队列预置。

## 尚未完成

本记录不等同于物理 USB 拔插验收，也不覆盖小时级播放、息屏连续播放、DoP-only DAC、外部 DLNA Renderer 或 Android 真机矩阵。USB 热插拔仍需在真实设备上完成拔出、重枚举、重新连接和播放恢复验证。
