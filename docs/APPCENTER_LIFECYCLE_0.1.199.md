# fnOS App Center 生命周期验证（0.1.199）

日期：2026-08-09

## 结果

- 使用 `artifacts/0.1.199/fnaudio-0.1.199.fpk` 通过「设置 → 手动安装」完成 fnOS App Center 覆盖更新。
- 已安装列表可见 fnAudio，点击“打开”后 fnAudio 界面可在 App Center iframe 中加载。
- FPK SHA-256：`CF88121CBF86795D47F233B26FB3B2A7964A2C7FEBB77E9070DCC6FDC09F1D99`。
- Android Debug APK SHA-256：`F210978E58F3108D2D1570046E5298639C4F206D6A647EEDDBD0113B385B4B95`。
- 本地 Python 回归 111 项通过；Android `lintDebug`、`assembleDebug` 通过。

## 未闭环项

外部直接访问 `:18080/api/health` 曾出现连接拒绝，因此尚不能把端口可达、重启后状态保持、DAC 长时播放和完整 App Center 生命周期标记为完成，详见 `TODO.md`。
