# 播放 API 兼容与模块拆分

日期：2026-08-12  
源码基线：0.1.223

## 权威接口

浏览器和 Android 新代码只使用以下服务端权威接口：

| 接口 | 作用 |
| --- | --- |
| `GET /api/playback/targets` | 输出目标与能力 |
| `GET /api/playback/status` | 当前目标的兼容状态查询 |
| `GET /api/playback/events` | 带 `state_version` 的 SSE 状态流 |
| `GET /api/playback/core` | 后端权威状态快照与插件信息 |
| `POST /api/playback/target` | 选择输出目标 |
| `POST /api/playback/queue` | 替换逻辑队列但不隐式播放 |
| `POST /api/playback/load` | 加载指定歌曲 |
| `POST /api/playback/control` | 统一传输控制，支持 `command_id` 幂等 |

`playback/http_contract.py` 现在集中保存目标分类、队列输入规范、SSE 包络和旧接口转换。
这些纯规则不依赖 HTTP Handler、MPD、ALSA 或 DLNA 网络，可独立回归。

## 兼容入口

源码搜索确认当前 Web 与 Android 均未调用下列接口。它们暂不删除，以免破坏旧页面或第三方客户端：

| 旧接口 | 后继接口 | 当前策略 |
| --- | --- | --- |
| `POST /api/player/state` | `/api/playback/queue` | 兼容同步旧前端状态 |
| `POST /api/upnp/push` | `/api/playback/load` | 只做 payload 转换 |
| `POST /api/dac/push` | `/api/playback/load` | 只做 payload 转换 |
| `POST /api/upnp/control` | `/api/playback/control` | 只做 payload 转换 |
| `POST /api/dac/control` | `/api/playback/control` | 保留当前 DAC 目标回退后转换 |

兼容响应带 `Deprecation: true`、`Link: <后继接口>; rel="successor-version"` 和
`X-fnAudio-Deprecated-API`。在至少两个已发布版本和一次真实升级验证之前不删除；
删除时应先记录访问日志命中量，并在发布说明中明确列出。

`GET /api/upnp/devices`、`GET /api/upnp/status`、`GET /api/dac/devices` 和
`GET /api/dac/status` 仍是诊断/发现接口，不等价于写操作别名，本轮不标记弃用。
`/upnp/media/*` 是 Renderer 获取媒体的协议资源，也不是旧 API。

## 大模块拆分顺序

| 风险 | 模块 | 边界 |
| --- | --- | --- |
| 低 | `server.py` | 先抽出纯 HTTP 契约、Range、认证映射和 payload 转换；Handler 只做 I/O |
| 中 | `library.py` | 以数据库查询、格式解析、扫描编排、目录变化检测分层；目标 6 先替换 O(n) 签名 |
| 中 | `app.js` | 以 API 客户端、播放状态、列表视图、移动布局拆分；需要浏览器 E2E 后再移动 DOM 代码 |
| 高 | `mpd_service.py` | 配置生成、设备协商、进程生命周期和状态监控分别抽取，必须保留 DAC 回归矩阵 |
| 高 | `metadata_service.py` | provider、持久队列、资产缓存和 Tag 写入分层，任何改动不得以空字段覆盖源 Tag |

本轮完成低风险的播放 HTTP 契约拆分。`library.py` 的目录检测由目标 6 接手；
`app.js` 的实质拆分等目标 5 建立浏览器 E2E 保护后进行，避免在没有 DOM 行为证据时大范围搬移。
