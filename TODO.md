# fnAudio 待办

当前源码版本：`0.2.5`。本清单只记录仍然有效的工作；历史阶段事项、已完成实现和验证证据见 `PROJECT_CONTEXT.md` 与 `CHANGELOG_AI.md`。

## P1：可靠性与发布质量

- [x] 元数据补全候选支持选择非第一候选。前端只提交候选序号，服务端仅从该歌曲已保存的候选集中取值，再执行既有的“只补空白 Tag”写回。
- [x] 加入可复用本地验证链路的 GitHub Actions 工作流：Python/Node/Playwright、Android Debug 构建和 `fnpack` 包检查使用同一套脚本。
- [x] Android 正式发布构建链路：`tools/build_android_release.ps1` 强制检查签名变量和 keystore，执行 Release 构建、APK 验签、版本核对和 SHA-256 归档；已通过一次性临时 keystore 离线烟雾验证。正式证书仍必须由负责人保管和提供。
- [ ] Chromaprint/AcoustID 用于无名称或歧义歌曲：已确认测试 fnOS 有 `libchromaprint.so.1`，但没有 `fpcalc`，包内不携带该依赖，且 AcoustID 查询必须使用项目专属 client key 和配额。取得可分发二进制及 API 凭据前不得默认启用。

## P2：部署与外部系统验收

- [x] FFmpeg、转码、封面预热和元数据待办均使用有界资源模型；整库封面预热已分页、低速、可取消，并让位于交互播放。
- [x] 版本、服务头、UI 缓存键和 Android `versionCode`/`versionName` 统一；源码卫生、结构化日志、状态并发合并、DLNA Browse/SystemUpdateID 均有自动回归。
- [ ] 将 CI 工作流推送到实际远程仓库并完成首次云端运行。目前仓库未配置 Git remote，因此不能伪造云端执行结果。
- [ ] App Center 全新安装、端口修改、停止/启动、保留数据卸载和清除数据卸载验收；还需核对安装后的文件权限。
- [ ] 核实 fnOS 防火墙/反向代理隔离，并在目标固件抓取 `user.login`、`user.authToken`、`user.tokenLogin` 与 CGI token 交接的真实协议边界。

## P3：可维护性清理

- [x] 音乐库路径许可、规范化、合并与配置写入统一归属 `library.py`；设置 API、扫描与 SQLite 使用同一身份规则。
- [x] 过期 Spotify 配置已移除；已知乱码、重复字典键、重复作用域定义和不可达控制流由源码卫生测试持续拦截。
- [ ] 继续按可测试边界拆分 `server.py`、`library.py` 与 `app.js`。`app.js` 的曲目展示规则已抽至 `ui/track_presentation.js` 并有独立 Node 回归；后续不得为降低行数做机械移动，每次抽取必须保留独立回归。
- [x] 历史检查目录和构建残留已归档至 `artifacts/_scratch/`，并纳入 Git 忽略规则；正式发布包和测试缓存保留用于回滚与复现。

## P0：必须依赖真实设备或外部材料

- [ ] USB DAC：物理热插拔、设备重连、跨采样率切歌、暂停/恢复/seek、后台或息屏连续播放。
- [ ] DSD：使用 DoP-only DAC 验证 DSF/DFF 无隐式 PCM fallback。
- [ ] DLNA Renderer：使用真实原生 DSD Renderer 验证源码直推、采样率保持、自动下一曲和断开恢复。
- [ ] AirPlay：在具备 `shairport-sync`/`nqptp` 的环境验证 Receiver、元数据、ALSA 租约和后台播放。
- [ ] Android：至少两台设备验证登录/历史、网络切换、前后台/息屏自动下一首、通知/锁屏封面、耳机拔出、蓝牙媒体键、HTTP/HTTPS/IPv6/反向代理/token 过期和多版本升级。
- [ ] 取得 `0.1.213` 之前的 NAS 快照或可信音乐库副本后，再执行 Tag 审计逐文件恢复。没有可信来源时不得写回空 Tag 或猜测数据。

## 需要项目负责人决策

- [ ] 确认许可证、维护者身份、远程 Git 托管位置和正式发布策略。
- [ ] 建立 Android 正式签名 keystore、离线备份和升级密钥策略。构建链路已就绪，但正式签名身份不能由临时代用密钥替代。
- [ ] 决定是否提供 AcoustID client key、额度和可分发的 Chromaprint 运行时。
- [ ] fnOS 若提供稳定的非 root 服务账号、共享目录 ACL 和 ALSA 设备组契约，再决定是否将主服务降权。

## 完成定义

只有实现、自动测试、所需部署/设备证据和恢复文档全部同步后才能勾选。真机事项不能用 Windows 单元测试、模拟响应或静态代码检查替代。
