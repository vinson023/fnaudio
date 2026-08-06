# 构建产物策略

`0.1.156/` 保存从当前 `C:\path\to\fnAudio\src` 直接构建的唯一当前可追溯 FPK。包身份、内容摘要和本地校验结果都保存在同一目录；设备端由用户自行安装测试。

`0.1.148/` 是整理阶段从当时源码重建的历史 FPK，不再代表当前源码版本。

`0.1.149/` 是由用户选择的更高版本升级验证包：它从 `src/` 完整复制到
`stage/` 后，仅把 `manifest` 版本改为 `0.1.149`，用于绕过应用中心的同版本
覆盖限制。它已在 fnOS 真机完成升级和冒烟验证，但不是新的源码或发布基线。

```text
artifacts/
├── 0.1.156/
│   ├── fnaudio-0.1.156.fpk       # 当前源码构建，待用户安装测试
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

每个版本目录的 `VALIDATION.md` 记录构建命令、源码身份、manifest 版本、包哈希和验证结果。`0.1.156` 已完成本地测试与包结构检查，待用户安装；`0.1.153` 保留最近一次 fnOS 启动和移动端结构烟雾验收，早期版本仅作历史追溯。
