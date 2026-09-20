# 0.2.33 发布证据审计

审计日期：2026-08-29

## 已验证

- artifacts/0.2.33/fnaudio-0.2.33-fnpack.fpk 存在。
- artifacts/0.2.33/SHA256SUMS 只包含一条 FPK 校验记录。
- 校验器可对 FPK 文件执行 SHA-256 校验。

## 当前缺口

- 目录没有 SOURCE_MANIFEST.sha256。
- 目录没有 SOURCE_PROVENANCE.json。
- 因此无法证明该历史 FPK 与当前源码树之间的逐文件对应关系，也不能在严格恢复模式下复现完整构建来源。

## 恢复规则

恢复时只能把该目录作为“校验和完整、源码来源不完整”的历史产物处理。不得根据当前源码重新生成 provenance 并回填到历史目录，否则会造成证据时间线和来源混淆。

后续正式发布应使用 tools/build_release.ps1 生成 FPK、源码清单和 provenance，并在发布前使用 tools/verify_release_evidence.ps1 -RequireCompleteEvidence 验证。
