# FN Connect 中继进度

0.1.226 已将官方飞牛 App 提取的 `libgojni.so` 纳入 arm64 Android 包，并提供 `TppsTunnel` 管理配置、启动、本地端口和状态轮询。中继流量应通过 `127.0.0.1:9018` 进入 fnOS，而不是访问 `fnid.fnos.net:443`，后者只是网页入口。官方 `startWithPort()` 成功接受异步启动时返回 `1`；只有 `getConnectStatus() == 1` 才表示通道已可用。

目前 `api/v1/fn/con` 返回的是公网地址发现数据，不包含 Tpps 的 token、visit secret 和动态服务器，因此完整中继登录仍需接入官方动态 P2P 配置签发接口。缺少该配置时客户端会明确提示，不会伪装成已连接。已补上 FN Connect 历史记录恢复入口：每次重新打开 `127.0.0.1:9018` profile 时都会重新请求并建立隧道，避免使用已失效的本地端口。
