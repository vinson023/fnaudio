# fnAudio 0.1.262 App Center 升级验收

日期：2026-08-14

## 发布包

- FPK：`artifacts/0.1.262/fnaudio-0.1.262-fnpack.fpk`
- 构建方式：`tools/build_release.ps1`，内部使用原生 `fnpack`
- SHA-256：`E210FDA0607C2D5590B87FAA45FC27A44161419F482E6DA689013C51DA1D2BF1`
- 包内预检：通过（`Validated: True`）

## App Center 覆盖升级

测试目标：`198.51.100.24`，通过 fnOS 应用中心“手动安装”上传 FPK，并确认升级流程完成。

- 安装来源：手动安装
- 升级后应用中心版本：`0.1.262`
- 升级过程：应用中心显示“更新中”，随后返回已安装列表
- 同版本安装拦截验证：`0.1.261` 曾被正确拒绝为“已安装相同或更高版本”，说明版本识别生效

## 服务与端口

- `/var/apps/fnaudio/manifest`：`version = 0.1.262`
- manifest `service_port`：`53199`（fnOS 元数据端口不占用；实际后端端口由配置管理）
- 实际监听：`0.0.0.0:18083`
- 进程：`server.py --host 0.0.0.0 --port 18083` 与 MPD 均运行
- `GET http://127.0.0.1:18083/api/health`：HTTP 200
- 响应头：`Server: fnAudio/0.1.262 Python/3.12.4`
- 健康状态：MPD、library、metadata、transcode 均正常；扫描未进行；DLNA 服务已启动

## 配置与数据保留

升级后 `/vol1/@appconf/fnaudio/config.json` 保留四条音乐库路径：

- `/vol1/1000/test`
- `/vol1/1000/777`
- `/vol1/1000/music`
- `/vol1/1000/123`

同时确认 `server_port: 18083`、`transcode/library.sqlite3` 和 artwork/thumb 缓存仍存在。配置文件权限为 `0600`。

## 生命周期与恢复

- `cmd/main`、`install_callback`、`upgrade_callback` 均为 `0755`，可被 fnOS 直接执行。
- 升级没有清空 `@appconf`、`@appdata` 或元数据缓存。
- 回滚原则：保留待升级前的 fnOS 应用快照；若升级后健康检查失败，先在应用中心停止 fnAudio，再恢复对应应用目录并保留 `@appconf/fnaudio`，最后启动并复查 `/api/health`。
- 内网快速恢复工具：`tools/install_test_host_fast.ps1`；其备份目录固定为测试机 `/vol1/1000/fnaudio/fast-deploy-backups/<timestamp>/`。

## 结论

0.1.262 已完成原生 fnpack 预检、App Center 覆盖升级、生命周期可执行性、端口/服务验收、配置保留和可重复恢复记录。
