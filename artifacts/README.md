# 构建产物策略

`0.1.168/` 保存当前可追溯的 fnOS FPK 和 Android Debug APK。该版本修复多连接历史覆盖问题，加入明确的新增/编辑动作，并保留原生认证 API、双击返回登录页与 Media3 后台播放服务。

`0.1.148/` 是整理阶段从当时源码重建的历史 FPK，不再代表当前源码版本。

`0.1.149/` 是由用户选择的更高版本升级验证包：它从 `src/` 完整复制到
`stage/` 后，仅把 `manifest` 版本改为 `0.1.149`，用于绕过应用中心的同版本
覆盖限制。它已在 fnOS 真机完成升级和冒烟验证，但不是新的源码或发布基线。

```text
artifacts/
├── 0.1.168/
│   ├── fnaudio-0.1.168.fpk
│   ├── fnaudio-android-0.1.168-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.167/
│   ├── fnaudio-0.1.167.fpk
│   ├── fnaudio-android-0.1.167-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.166/
│   ├── fnaudio-0.1.166.fpk
│   ├── fnaudio-android-0.1.166-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.165/
│   ├── fnaudio-0.1.165.fpk
│   ├── fnaudio-android-0.1.165-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.164/
│   ├── fnaudio-0.1.164.fpk
│   ├── fnaudio-android-0.1.164-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.163/
│   ├── fnaudio-0.1.163.fpk
│   ├── fnaudio-android-0.1.163-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.162/
│   ├── fnaudio-0.1.162.fpk
│   ├── fnaudio-android-0.1.162-debug.apk
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.161/
│   ├── fnaudio-0.1.161.fpk       # 上一版 Web-only 行为基线
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.160/
│   ├── fnaudio-0.1.160.fpk       # 历史过渡方案：搜索时切换为绝对定位
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.159/
│   ├── fnaudio-0.1.159.fpk       # 历史方案：搜索时隐藏播放器，存在恢复风险
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.158/
│   ├── fnaudio-0.1.158.fpk       # 历史源码构建，设备安装状态未记录
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.157/
│   ├── fnaudio-0.1.157.fpk       # 历史源码构建，设备安装状态未记录
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.156/
│   ├── fnaudio-0.1.156.fpk       # 历史源码构建，设备安装状态未记录
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.155/
│   ├── fnaudio-0.1.155.fpk       # 历史源码构建，设备安装状态未记录
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.154/
│   ├── fnaudio-0.1.154.fpk       # 历史源码构建，设备安装未完成
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.153/
│   ├── fnaudio-0.1.153.fpk       # 当前源码构建，已完成覆盖升级验收
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.152/
│   ├── fnaudio-0.1.152.fpk       # 移动端布局中间验收包
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.151/
│   ├── fnaudio-0.1.151.fpk       # 当前源码构建，已完成覆盖升级验收
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.150/
│   ├── fnaudio-0.1.150.fpk       # 当前源码构建，待真机验收
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   └── VALIDATION.md
├── 0.1.148/
│   ├── fnaudio-0.1.148.fpk
│   ├── SHA256SUMS
│   ├── PACKAGE_CONTENTS.txt
│   └── VALIDATION.md
├── 0.1.149/
│   ├── fnaudio-0.1.149.fpk       # 仅真机升级验证
│   ├── PACKAGE_CONTENTS.txt
│   ├── SHA256SUMS
│   ├── VALIDATION.md
│   └── stage/                    # 仅版本号不同的构建暂存副本
└── excluded-generated-cache/
```

`excluded-generated-cache/` 是整理时从 `src/` 隔离出的 Python 字节码缓存，仅用于说明复制清理过程，不属于源码、发布包或恢复输入。

各版本的 `_inspect/` 是本地包结构校验时从 FPK 解出的派生检查副本，不是源码、构建输入或待上传文件；需要节省空间时可直接删除这些目录，不影响 FPK、哈希或验证记录。

每个版本目录的 `VALIDATION.md` 记录构建命令、源码身份、manifest/versionName、包哈希和验证结果。`0.1.168` 是当前配套 FPK/APK，已完成本地构建和结构校验，待 Android 真机安装；`0.1.167` 保留原生认证 API 与双击返回实现，`0.1.166` 保留 CGI 路由诊断，其他版本仅作历史追溯。
