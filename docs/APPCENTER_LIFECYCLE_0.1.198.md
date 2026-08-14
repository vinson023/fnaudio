# App Center 生命周期验证记录（0.1.198）

## 当前证据

- 目标设备：`198.51.100.24:5666`
- 登录账号：`admin`（凭据不写入文档）
- 只读 App Center 查询成功。
- 当前已安装 fnAudio：`0.1.178`，状态 `running`。
- `app config wizard fnaudio` 返回唯一向导字段 `wizard_server_port`，默认/当前值为 `18081`。
- CLI `app install-fpk --dry-run` 能解析 FPK，但因存在自定义安装向导而转交 App Center UI；本轮未启动覆盖安装。

## 受控升级步骤

1. 在 App Center 的“手动安装”入口选择 `artifacts/0.1.198/fnaudio-0.1.198-rebuild.fpk`。
2. 向导端口填写 `18081`，确认安装卷为当前卷 `1`。
3. 升级前记录：应用版本、运行状态、`service_port`、库路径和用户配置摘要。
4. 升级后确认：版本 `0.1.198`、状态 `running`、端口仍为 `18081`，并访问 `/api/health` 与 HTTP `Server` 头。
5. 显式执行停止/启动/重启，确认 `config.json` 中 MPD、输出设备、DLNA 和库路径字段未丢失。
6. 最后再做卸载演练：默认模式应保留配置和缓存；只有显式 purge 向导才清除应用数据。

## 恢复原则

- CLI 报告 `custom wizard/UI` 时不要反复重试或绕过向导。
- 真机安装前保留当前 FPK、SHA-256、`TODO.md`、`PROJECT_CONTEXT.md` 和本记录。
- 未完成上述升级后检查前，不把目标 7 标记为完成。
