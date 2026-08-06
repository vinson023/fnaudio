# fnAudio 0.1.55

- 修正 TEAC UD-301 的 PCM 能力上限为 `192kHz/24bit`。
- 不再把 Linux 内核 USB Audio 描述中出现的 352.8kHz、384kHz 或 32bit 直接当作 DAC 实际输出能力。
- 保留 TEAC UD-301 的 Native DSD 2.8MHz / 5.6MHz 能力标识。
- 播放设备菜单和 MPD 输出能力接口现在会显示真实的 UD-301 PCM 上限。
- 新增真实 DAC 能力上限回归测试。

本版本本地回归测试：20 项全部通过。
