# FN Connect 中继抓包结论（2026-08-12）

## 已验证

- `https://<fn-id>.fnos.net:443/` 返回 `302` 到 `https://fnos.net/<fn-id>/`，不是 fnOS API 代理。
- 直接访问 `https://<fn-id>.fnos.net/cgi/ThirdParty/fnaudio/...` 同样被重定向，不能作为 fnAudio 中继地址。
- 官方飞牛 App 使用 Tpps V2（Go JNI）建立本地隧道：
  - `server`: 动态公网地址和端口（本次为 `36.25.243.6:7205`）
  - `stun_server`: 动态 STUN（本次为 `36.25.243.3:3478`）
  - `transport_protocol`: `quic`
  - `visit_server`: 动态标识
  - `visitor_name`: `v-<fn-id>`
  - `token`、`visit_secret_key`: 动态敏感值
- Tpps 状态由 0 变为 1 后监听 `127.0.0.1:9018`，官方 App 的 API 基地址切换为该地址。
- 通过 ADB 转发访问该本地端口可到达 fnAudio，但没有 fnAudio 自己的 token 时返回 `HTTP 200 invalid token`。

## 当前阻塞

`api/v1/fn/con` 只返回地址发现信息（公网 IPv4/IPv6、fn 域名、HTTP/HTTPS 端口、校验值），不返回 Tpps 的完整动态配置。官方 App 本次启动复用了缓存配置，因此抓包未捕获配置签发接口。

## 后续实现要求

1. 不再把 `<fn-id>.fnos.net:443` 当作普通 fnOS origin。
2. 引入与当前 ABI 匹配的 Tpps V2 JNI 封装或等价实现。
3. 找到官方动态 P2P 配置获取接口后，按会话启动本地隧道，再把 fnAudio API/WebSocket 指向 `127.0.0.1:<port>`。
4. 隧道认证和 fnAudio 用户认证分开处理，不能复用或硬编码官方 token/secret。

抓包文件保存在 `tools/apk-analysis/fnconnect-official-20260812.mitm`，其中可能包含敏感 Cookie，仅限本地调试使用。
