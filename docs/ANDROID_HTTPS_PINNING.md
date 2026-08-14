# Android 自签名 HTTPS 证书固定

## 策略

系统 CA 可验证的 HTTPS 保持平台默认校验。用户为单个连接明确启用自签名兼容时，客户端使用 TOFU：

1. 首次 TLS 握手只用于读取证书，尚未发送账号、密码或 token。
2. 对叶子证书完整 DER 编码计算 SHA-256，保存为 `sha256/<base64>`。
3. 指纹随连接资料进入 Android Keystore 加密存储。
4. 后续登录 WebSocket、OkHttp API、媒体、封面和 WebView SSL 错误都必须匹配同一指纹。
5. 证书变化直接拒绝，用户需要回到连接设置重新确认，不能自动接受新证书。

## 边界

- 固定的是完整证书 DER，不是公钥 SPKI；证书续期即使复用公钥也会触发重新确认。
- 指纹只属于规范化的单个连接资料，不得全局信任。
- HTTP 连接没有 TLS 身份保证，不能声称等同于固定证书的 HTTPS。

## 实现和测试

- `CertificatePin.java` 负责格式校验、DER 哈希和匹配。
- `FnOsAuthClient` 在认证前完成首次固定。
- `HttpClientFactory` 只为已保存指纹的自签名连接创建受限 TrustManager。
- `MainActivity` 对 WebView 自签名错误应用相同指纹。
- JVM 单元测试覆盖确定性哈希、格式规范和连接资料序列化；`testDebugUnitTest`、Lint 与 Debug 构建是离线基线。

真实证书轮换、厂商 WebView 和反向代理仍需 Android 设备验收。
