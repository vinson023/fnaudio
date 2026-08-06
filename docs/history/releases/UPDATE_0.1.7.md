# fnAudio 0.1.7 阶段一进展

## MPD 本机播放

- 集成 Debian 12 amd64 MPD 0.23.12 轻量运行包到 `app/target`。
- MPD 随 fnAudio 安装，不需要用户手动安装系统 MPD。
- MPD 服务启动时优先使用应用私有 `target/lib` 动态库。
- 修正 MPD 应用根目录定位，安装后从 fnAudio 自己的 `target/bin/mpd` 启动。
- 保留独立 MPD 配置、数据库、状态、播放列表、日志和进程监督器。
- 增加 MPD `idle` 监听线程，用于后续减少轮询式状态刷新。

## 当前限制

- 当前运行包依赖飞牛 OS Debian 12 amd64 的基础系统库，适用于 x86_64 飞牛环境。
- USB DAC、DSD Native、DoP 和硬件 Mixer 能力探测还在后续步骤继续完善。
- SQLite 音乐库数据库化尚未完成。
