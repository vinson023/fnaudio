# fnOS 登录错误码 8192 的取证结论

> 结论一句话：**8192 不是 fnOS 的「账号/密码错误」，而是「请求缺少必填字段」。
> 它由我们自己的客户端在最后一跳降级里亲手制造出来，并盖掉了真正的原因（131072）。**

记录日期：2026-11-18。设备 `192.168.5.111:5555`（SM-G965F / Android 13），
NAS `192.168.5.141:5666`（fnOS，官方 APP `com.trim.app` 1.37.3 / 1373019）。

## 1. 问题

真机上用错密码登录时，界面提示：

```
fnOS 拒绝了登录请求。（错误码 8192）
```

`131072`（密码错）此前已见过，`65534`（未知请求）也见过，`8192` 没有解释。
`FnOsAuthClient.messageFrom()` 只把服务端 `errno` 拼进文案，仓库里没有任何映射表，
fnOS 也**从不返回 `errmsg`**——响应体只有 `{"errno":N,"result":"fail","reqid":"..."}`。
所以只能靠协议层取证。

## 2. 方法：直接在 WebSocket 上重放，不需要 CA、不需要 frida

`FnOsAuthClient` 的登录是 WebSocket：`ws(s)://host:port/websocket?type=main`，
帧为 JSON。局域网端口 5666 上 fnOS 走的是**明文 `ws://`**——真机 `tcpdump` 抓到的
官方 APP 流量可以直接读（`appcgi.resmon.*`、`appcgi.sysinfo.*` 全是明文 JSON），
HTTP 升级请求里也没有 TLS。因此：

- **不需要往 `/system` 装 CA**：没有密文可解。
- **不需要 frida hook `libgojni.so`**：登录帧是明文 JSON，构造即可。

复现脚本（全部只读、每个 socket 只发一帧、不重试、不猜密码）：

```bash
# 单次探测，打印原始响应
FNAUDIO_PROBE_PASSWORD=*** node artifacts/fnos-login-probe/probe.js

# 逐字段变化，看哪个 errno 会动
FNAUDIO_PROBE_PASSWORD=*** node artifacts/fnos-login-probe/matrix.js

# 用刚签发的真 token 验证 token 类请求是否还存在
FNAUDIO_PROBE_PASSWORD=*** node artifacts/fnos-login-probe/token_check.js
```

## 3. 错误码语义（实测，`matrix.js` 输出）

| 请求形态 | errno | 判定 |
|---|---|---|
| `user.login` + `user` + `password`（正确） | — | `result:"succ"`，返回 `token`/`longToken` |
| `user.login` + `user` + 错密码 | `131072` | **凭据错误** |
| `user.login` + 不存在的用户 | `131072` | 凭据错误（与密码错同码，不区分） |
| `user.login` + `user` + 空密码 `""` | `131072` | 凭据错误（空串算「密码错」，不算缺失） |
| `user.login` **不带 `password` 字段** | `8192` | **必填字段缺失** |
| `user.login` **用 `username` 代替 `user`** | `8192` | **必填字段缺失**（服务端只认 `user`） |
| `user.login` 只给 `user` | `8192` | 必填字段缺失 |
| `user.login` 只给 `password` | `8192` | 必填字段缺失 |
| `user.authToken`（真 token / 垃圾 token / 不带 token） | `65534` | **请求名不存在** |
| `user.tokenLogin`（真 longToken / 垃圾 token / 不带 token） | `65534` | **请求名不存在** |
| 任意不存在的 `req` | `65534` | 请求名不存在 |

要点：

1. **8192 = 缺参数**。同一个 `user.login`，密码字段「存在但错」是 131072，
   「整个字段不在」是 8192。`username` 触发 8192 是因为服务端找不到 `user` 这个必填字段，
   不是因为它读不懂 `username`。
2. **131072 = 凭据错**，且不区分「用户不存在」与「密码错」——这是 fnOS 的设计，不是 bug。
3. **65534 = 请求名不认识**。用**刚签发、确认可用**的 `token` 去调 `user.authToken`
   同样得到 65534，与垃圾 token 无差别，所以这两个 req 名在 1.37.3 上**已经不存在**，
   不是「token 失效」。

## 4. 我们为什么看到 8192：最后一跳自己造的

`FnOsAuthClient.handleAttemptFailure()` 在同一个 socket 上按
`AUTH_TOKEN → LONG_TOKEN → LOGIN_USER → LOGIN_USERNAME` 逐跳降级，
而 `finishCredentialRejected()` **只上报最后一跳的文案**。

`matrix.js` 用错密码重放整条链，服务端逐跳的回应是：

```
AUTH_TOKEN    user.authToken                  errno=65534
LONG_TOKEN    user.tokenLogin                 errno=65534
LOGIN_USER    user.login + user + 错密码      errno=131072   ← 真正的原因
LOGIN_USERNAME user.login + username          errno=8192     ← 被显示出来的那个
```

`LOGIN_USERNAME` 这一跳发的是 `req:"user.login"` + `username` 字段
（`FnOsAuthClient.send()` 的 `nextAttempt == Attempt.LOGIN_USER ? "user" : "username"`），
这个形态 fnOS 一律判为缺参 → 8192。于是**真实原因 131072 被 8192 覆盖**。

真机端到端确认（错密码跑 `RealNasPlaybackRestoreInstrumentedTest`，
`assertTrue("fnOS authentication failed: " + error.get(), ...)` 把应用文案带了出来）：

```
java.lang.AssertionError: fnOS authentication failed:
fnOS 拒绝了登录请求。（错误码 8192）
```

即：**用户输错密码 → 看到 8192**。这与 8192 的语义（缺参）完全对不上，
是纯客户端问题。

## 5. 顺带查到的两件事

### 5.1 降级链的前两跳是死代码

`user.authToken` / `user.tokenLogin` 在 1.37.3 上返回 65534（请求名不存在），
有效 token 也一样。所以「App 重启后静默恢复会话」实际上从未走过这两跳，
每次都靠已保存的密码重新 `user.login`。副作用是：**密码没存的连接，重启后必然要求重输密码**。

官方 APP 在局域网冷启动时**完全不发 `user.*` 帧**（force-stop 后重启抓包，`user.*` 计数为 0），
它靠 HTTP 升级头里的 `x-access-code` + `x-device-id` 完成认证，直接开始拉
`appcgi.resmon.*`。这说明局域网场景 fnOS 认的是**访问码**，不是用户 token。
（抓包中该头为 base64 明文，此处不记录取值；该访问码与登录密码同值，
属用户侧的配置现状，不在本仓库范围内处理。）

### 5.2 官方 APP 局域网流量是明文

`tcpdump -A` 可直读 JSON，`x-access-code` 也随请求头明文发送。
这是 fnOS 侧的实现，我们无法改；仅作记录：局域网内 5666 端口不提供机密性。

## 6. 没有做的事（以及为什么）

- **没有改 `/system` 装 CA**：抓包证明 5666 是明文 `ws://`，装 CA 无收益，
  而 Android 13 + 仅装了 Magisk App（无 `/data/adb`、无 `su` 二进制）的机器上
  要 remount `/system` 需要额外改分区状态，风险与收益不成比例。
- **没有往 `/data/local/tmp` 推 frida**：登录帧是明文 JSON，重放即可穷举字段，
  不需要 hook Dart AOT 里的 `libgojni.so`。
- **抓包文件已删**：`/data/local/tmp/ws_cap.txt`、`ws_boot.txt` 及本地副本含明文访问码，
  取证结束后即删；本文件只保留头名，不留取值。

## 7. 待办与状态

1. ~~`messageFrom()` 增加 errno → 人话映射~~ **已做（R607）**：`knownErrnoMessage()` 返回
   `131072 → 账号或密码错误，请检查后重试。`、`8192 → 登录请求缺少参数，这台 fnOS 的登录接口可能变了，请更新客户端。`、
   `65534 → 这台 fnOS 不支持当前的登录方式，请更新客户端。`，数字仍拼在文案尾部。
2. ~~`handleAttemptFailure()` 停止 `LOGIN_USER → LOGIN_USERNAME` 的无条件降级~~ **已做（R607）**：
   降级表抽成纯函数 `nextAttemptAfterFailure()`，只在上一跳是 65534 时才换字段名，
   131072 直接上报；换字段名那一跳若失败，报的是上一跳的文案，不再拿 8192 顶替。
3. ~~删除或重写 `Attempt.AUTH_TOKEN` / `Attempt.LONG_TOKEN`~~ **裁定不删**：
   它们在「没有密码、只有令牌」的恢复路径上，删掉等于把「将来 fnOS 恢复该能力时的免密恢复」
   一起删掉；两次无效往返各约 10 ms，且只在密码为空时发生。口径记在 `DECISIONS.md` D-061。
4. **未做**：若要恢复「重启后免密」，需要按官方 APP 的路径走 `x-access-code` + `x-device-id`，
   而不是 `user.authToken`。这需要先确认访问码的存储与轮换方式，另开条目。

## 8. 改后行为（真机实测，R607）

| 场景 | 改前 | 改后 |
|---|---|---|
| 输错密码 | `fnOS 拒绝了登录请求。（错误码 8192）` | `账号或密码错误，请检查后重试。（错误码 131072）` |
| 正确密码 | 登录成功 | 登录成功（全套 29 项通过，`RealNas` 用例真跑 4.1 s） |

验证方式：用错密码跑 `RealNasPlaybackRestoreInstrumentedTest`，该用例的
`assertTrue("fnOS authentication failed: " + error.get(), …)` 会把应用文案带进
`AssertionError`，日志里直接可比对改前改后的字符串。守卫：`FnOsAuthErrnoTest`（7 例，
含「131072 必须返回 null 而不是 LOGIN_USERNAME」这条防回归）。

