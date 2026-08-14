# 文件权限与路径边界

## 权限模型

| 类型 | mode | 示例 |
| --- | --- | --- |
| 私有目录 | `0700` | 配置目录、运行目录、SQLite/元数据/转码缓存目录、MPD 数据目录 |
| 私有文件 | `0600` | `config.json`、SQLite/WAL/SHM、JSONL/MPD 日志、PID、MPD 配置、缓存文件 |
| 公开 UI 目录 | `0755` | FPK Web 静态资源目录 |
| 公开 UI 文件 | `0644` | `service_port.json`、wizard JSON、manifest 更新 |

Python 私有写入使用同目录临时文件、`fsync` 和原子替换。媒体 Tag 写回在替换前复制原始文件的 mode，并在 root 环境恢复 uid/gid，避免把用户媒体悄悄改成 root 私有文件。

生命周期脚本在创建文件前设置 `umask 077`，随后显式放开需要被 Web 服务器读取的 UI 文件。SQLite 在创建、启用 WAL 和关闭连接后加固主文件、WAL 与 SHM。

## 路径边界

- Linux 配置曲库路径使用 `realpath`，只允许 fnOS 音乐共享目录前缀；Windows 开发环境保留 `abspath`，避免 8.3 短路径与 SQLite root 字符串不一致。
- 扫描、CUE `FILE`、真实路径查询和媒体记录均验证解析后的文件仍位于配置曲库根目录。
- 指向曲库外的音频、CUE 或 sidecar 封面符号链接被拒绝。
- 共享目录删除需要 `files.manage` scope，且目标必须等于当前已配置根目录的真实路径。
- 卸载 purge 只接受 fnAudio 已知 `etc/var/data` 或 appdata 路径；意外路径即使由环境变量传入也拒绝递归删除。

## 进程身份

FPK 目前仍声明 root。fnAudio 需要访问 fnOS 授权共享目录、ALSA/DAC、SSDP 端口和可选 Tag 写回；在没有稳定服务账号、ACL 与音频组契约前直接降权会造成不可预测回归。后续若 fnOS 提供正式契约，应把扫描/网络和设备/Tag 写操作拆分权限，再进行真机迁移验证。

## 验证

`test_file_permissions.py`、`test_app_lifecycle_scripts.py`、`test_api_auth.py`、`test_library_cache.py`、`test_library_sqlite.py` 与 HTTP 集成测试共同覆盖权限、scope、原子写、卸载白名单、非法路径和符号链接逃逸。App Center 实际 uid/gid 与 mode 仍需 fnOS 部署验收。
