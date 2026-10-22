# 0.2.100 发布同步核验

- 版本：`0.2.100`；Android `versionCode=365`。
- Android Debug：`testDebugUnitTest`、`lintDebug`、`assembleDebug` 均成功。
- APK：`android-client/app/build/outputs/apk/debug/app-debug.apk`
- APK SHA-256：`B94271F17D05D5B5ABBF993CD43C03252FDD3E46E201A8820B28575EAA55F405`
- 包名：`com.fnaudio.client`。
- 代码内置网页资源由 `verifyFnaudioUiSource` 校验。
- 根 `SOURCE_MANIFEST.sha256`：780 条，逐条校验通过。
- 已删除 36 份停用的 `fnAudio-RNNN-修改审查对照.md`；没有删除 Git 历史。
- 发布候选 staged 内容完成凭据扫描：未发现已知密码、访问码、令牌或私钥；`.gitignore` 未加入 staged。
- 未纳入：FPK/APK 成品、设备日志、部署脚本、SDK/Gradle 缓存、外部参考仓库。
