# fnAudio AI 修改记录

## 2026-08-07：`0.1.169` 歌曲右键/长按四项菜单

- 目标：歌曲列表在桌面右键和移动端长按时，只显示“从当前开始播放所有歌曲、加入当前队列、收藏歌曲、加入播放列表”四项，并保持指定顺序。
- 交互：桌面继续使用 `contextmenu`；移动端新增 550ms Pointer Events 长按。手指移动超过 10px、触点取消或列表滚动会取消长按，触发成功后拦截随后生成的点击，避免松手时误播放。
- 菜单边界：新增独立 `trackContextActionButtons()`，不再把播放、插播、歌曲信息、打开文件夹、分享或页面移除操作混入右键/长按菜单；旧操作对话框保留原能力。
- 行为语义：“收藏歌曲”使用只添加的 `addSelectedFavorites()`，已收藏歌曲不会因菜单文字固定而被反向取消；“从当前开始播放所有歌曲”仍调用 `allTracksForCurrentContext()`，保持加载当前完整列表而非当前分页。
- 移动样式：菜单宽度限制在视口内，操作行提高到 44px，并关闭歌曲行文字选择和系统触摸呼出，降低 WebView 长按冲突。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。FPK 外层 21 项、内层 110 项且无 Python 字节码；APK manifest 为 `0.1.169 / versionCode 169`，v2 Debug 签名有效；包内 UI 文件哈希与源码一致。
- 产物：FPK `4,884,683` 字节，SHA-256 `E061CA3A761D7BA5E3F6C48604B700E340F938C372A3A90D02C8210C8E2EDD56`；APK `10,083,954` 字节，SHA-256 `EC2A690930E4560D003CBDF048857E3A75945101C57C1FA0BB559338EDBA7F02`。
- 待验证：本轮没有连接 fnOS/Android 真机；需在桌面浏览器和 Android WebView 验证右键/长按、滚动取消、松手不播放、完整列表入队、收藏只添加以及加入队列/歌单。

## 2026-08-07：`0.1.168` Android 多连接历史修复

- 目标：修复历史连接只能显示当前一条、登录第二个 NAS 会覆盖第一条的问题。
- 根因：登录页预填活动连接时保留其 UUID；用户修改服务器后，`ConnectionProfile.create()` 仍使用旧 UUID，`SecureProfileStore.upsert()` 因而删除旧行并写回新地址。
- 飞牛参考：本地 `FN_Media.apk` 的 Flutter 资源包含独立 `fn_connect` 连接模块和“手动添加”入口，说明选择已有设备与新增连接是两个明确动作。fnAudio 采用同样的交互原则，不复制其商业素材。
- 身份规则：规范化 host、端口、HTTP/HTTPS 和账号共同构成连接身份。普通表单改变身份会生成新 UUID；显示名、密码或证书选项变化更新匹配记录；完全相同身份复用已有记录，避免重复项。
- 历史页：新增“新增连接”按钮，返回空白表单；“编辑”显式保留所选 UUID，即使地址发生变化也只更新该记录。选择现有记录登录仍直接恢复对应连接。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。FPK 为 21/110 个条目且无 Python 字节码；APK manifest 为 `0.1.168 / versionCode 168`，v2 Debug 签名有效。
- 产物：FPK `4,883,808` 字节，SHA-256 `F363B6C2E23CE7697ECF08E7C81CF7A296696199E3EECC732B8855FE83F30CD4`；APK `10,083,946` 字节，SHA-256 `A4736CE6F304084B87E9E95BF410051D9BC4E14CB9F649F732D650AD7CD35748`。
- 待验证：没有连接 Android 真机；需实际保存至少两个 NAS、编辑其中一个、重新登录相同连接并删除其中一条，确认记录互不覆盖。

## 2026-08-07：`0.1.167` Android 原生认证 API 与双击返回登录页

- 目标：修复 Android 播放仍提示“播放队列保存失败（HTTP 200）”，并把根页面返回改为第一次提示、第二次进入登录页。
- 真实根因：在测试 fnOS 上复现到 CGI 外层 nginx 返回 `HTTP 200 text/plain`，正文为 `invalid token`，请求没有进入 `cgi_proxy.py`。WebView 的 `shouldInterceptRequest()` 能代理 GET，但拿不到 POST body，因此队列、状态和控制 POST 绕过了已认证的 OkHttp 路径。
- 官方 App 对比：缓存的飞牛媒体 App 使用 Flutter/原生网络、WebSocket 和原生媒体服务持有认证及播放生命周期。fnAudio 沿用“WebView 界面 + 原生认证请求 + Media3 播放”的轻量架构，不复制官方商业素材或私有实现。
- 原生认证桥：`NativePlaybackBridge` 新增 `requestJson()`；`MainActivity` 只允许当前 NAS 的 fnAudio `/api/` 以及 POST/PUT/PATCH/DELETE，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和 token Cookie，通过 OkHttp 异步请求，再把状态、响应头和正文回传给网页。
- 网页 API：新增 `apiFetch()`、请求 ID/Promise 管理和 `fnAudioNativeOnHttpResponse()`。Android 环境的队列、用户状态、播放控制、转码预热、配置、共享目录同步和播放设备切换均走原生认证；普通浏览器继续使用标准 Fetch。
- 返回键：网页内部层级处理保持不变。根页面第一次返回显示“APP 即将退出，再按一次返回登录界面”，2.2 秒内第二次打开登录页并结束主页面；`EXTRA_SKIP_AUTO_RESUME` 阻止登录页立即自动重连。删除原有 `moveTaskToBack(true)` 根页面逻辑。
- 测试：59 个 Python 单元测试、3 个 Node 回归脚本、JavaScript 语法、Android `lintDebug` 与 `assembleDebug` 全部通过。FPK 外层 21 项、`app.tgz` 110 项且无 Python 字节码；APK manifest 为 `com.fnaudio.client / 0.1.167 / versionCode 167 / minSdk 26 / targetSdk 36`，v2 Debug 签名通过。
- 版本与产物：`fnaudio-0.1.167.fpk` 为 `4,884,107` 字节，SHA-256 `A5F5CF912C2477F1597D288201B5386552206B97870C49D1992D72D9741700DD`；`fnaudio-android-0.1.167-debug.apk` 为 `10,111,653` 字节，SHA-256 `5723CDAE06C7D94FCCD1B5D3E705D33AFC3165157996FFB23FE1C7DFB020FC34`。
- 待验证：本轮没有连接 Android 设备，不能宣称手机端播放和返回键已完成真机验证。需配套安装 `0.1.167` FPK/APK，至少播放两首歌曲，并确认第二次返回后登录页不会自动重连。

## 2026-08-07：`0.1.166` CGI 队列路由与 Android 返回修复

- 目标：修复播放时出现“播放队列保存失败（HTTP 200）”，以及 Android 系统返回键进入登录页的问题。
- CGI 路由：`cgi_proxy.py` 新增统一路径恢复，按显式 `X-FnAudio-Path`、`REQUEST_URI`、`PATH_INFO` 的顺序提取 `/index.cgi` 后的真实 API 后缀。播放队列 POST 主动携带 `/api/playback/queue` 路由 Header，即使 fnOS 只提供脚本级 `PATH_INFO`，也不会误代理到 HTML 首页。
- 前端诊断：队列响应先读取文本再解析 JSON；如果 CGI 回退返回 HTML，会显示“播放队列请求返回了错误页面”，不再把 HTTP 200 伪装成普通接口失败。
- Android 返回：登录成功启动 `MainActivity` 后立即结束 `LoginActivity`。系统返回键先调用网页 `fnAudioHandleAndroidBack()`，依次关闭对话框、上下文菜单、移动侧栏、歌词和嵌套分类；根页面只把应用任务移到后台，不调用可能进入 fnOS 登录/系统入口的 `WebView.goBack()`。
- 测试：新增 CGI `REQUEST_URI` 和显式路由 Header 回归；Android bridge 脚本同时检查网页返回入口、`MainActivity` 后台化逻辑与登录 Activity 出栈。59 个 Python 单元测试、3 个 Node 回归脚本、`node --check`、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 版本与产物：统一为 `0.1.166`。`artifacts/0.1.166/fnaudio-0.1.166.fpk` 为 `4,883,638` 字节，SHA-256 `03993A17CA0E87BA063BFBE6764847B0650A0743BA6D5B5827C9913DA95FBD53`；`fnaudio-android-0.1.166-debug.apk` 为 `10,105,834` 字节，SHA-256 `84A476C8F62A68955A52A385A37D4E4DF71103A8FED514452753CF042F8B3909`。
- 包验证：FPK manifest 为 `fnaudio / 0.1.166 / x86`，外层 21 个条目、`app.tgz` 110 个条目且无 Python 字节码缓存；APK 为 `com.fnaudio.client / 0.1.166 / minSdk 26 / targetSdk 36`，Android Debug 证书的 v2 签名通过。
- 待验证：当前未连接 fnOS 或 Android 真机；必须在配套安装 FPK/APK 后确认真实 CGI POST 返回 JSON、队列播放成功、返回键顺序正确、重新打开应用仍保持 fnAudio 页面，以及后台/息屏跨曲不回归。

## 2026-08-07：`0.1.165` Android 刘海安全区、默认端口与大队列播放修复

- 目标：修复登录界面顶部空间不足、fnAudio 主页面与状态栏/前置摄像头区域重叠，以及大音乐库播放时弹出“播放队列保存失败”。
- Android 窗口：新增 `WindowInsetsHelper`，登录页、历史连接页和主 WebView 宿主根据系统状态栏、导航栏与 `displayCutout` 自动增加安全内边距；主页面使用浅色状态栏图标，登录/历史页保持深色状态栏。
- 登录页：端口输入框默认直接显示 `5666`，移除“HTTP 常用 5666、HTTPS 常用 5667”的提示；切换 HTTPS 时仅在当前端口仍为默认值时切换到 `5667`，避免覆盖用户手动输入。
- 播放队列：前端 `/api/playback/queue` 只发送歌曲 ID，不再发送完整歌曲对象；服务端同时兼容 ID 列表和历史对象格式。这样“从当前开始播放所有歌曲”在大曲库/CGI 网关下的请求体显著减小，失败提示也会显示 HTTP 状态或服务端返回消息。
- 测试：新增紧凑队列 ID 的服务端单元测试和 Android bridge 静态回归检查；57 个 Python 单元测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 版本与产物：统一升级为 `0.1.165`。`artifacts/0.1.165/fnaudio-0.1.165.fpk` 为 `4,880,353` 字节，SHA-256 `7D134D517321F6C8A247A1F75D5B2B1FCE2AB3BB897FA5E2AE6651281A6C2E97`；`fnaudio-android-0.1.165-debug.apk` 为 `10,079,754` 字节，SHA-256 `569B0A1F6D6FB21A186B5C477920EE01CE7D94FA0775DDC4B8BF5A6B4EBFBDE5`。
- 待验证：尚未安装到真实 Android/fnOS 设备；需重点确认不同刘海/挖孔机型的登录和主页面顶部位置，以及大队列播放、自动下一曲和后台息屏播放。

## 2026-08-07：`0.1.164` WebView 子资源鉴权与 FPK/Android 图标统一

- 目标：修复 Android 登录后页面只显示无样式 HTML、CSS/JS/封面和 GET API 资源无法携带 fnOS 会话的问题，并处理启动图标中间音符过大被裁剪、Android 图标与 FPK 不一致的问题。
- WebView 资源：`MainActivity` 对同源 GET 子资源通过 OkHttp 重新请求，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和兼容 token Header；响应 `Set-Cookie` 同步回 WebView CookieManager；对 `/cgi/ThirdParty/fnaudio/app.css` 等缺少 `/index.cgi/` 的路径增加兜底重写。
- CGI 入口：`cgi_proxy.py` 在 HTML 入口服务端注入 `<base href="/cgi/ThirdParty/fnaudio/index.cgi/">`，防止不同 WebView 对内联脚本/CSP 的处理差异导致相对资源解析到错误目录。
- 登录与历史页：保留参考 `FN_Media.apk` 的卡片式深色布局、独立历史连接页面、保存密码和删除确认交互；参考 APK 只用于行为和字段设计，没有复制其商业素材。
- 图标：Android 普通图标和 adaptive icon 改为白色圆角底 + 蓝色音符，与 FPK `src/ICON_256.PNG` 保持一致；前景音符缩放到 `0.68`，留出自适应图标安全区域。
- 版本与产物：统一升级为 `0.1.164`。`artifacts/0.1.164/fnaudio-0.1.164.fpk` 为 `4,882,412` 字节，SHA-256 `C114A0F9360F9E6D12C3487D2543F751F958B3E1B8E42362E4273591F66D62F5`；`fnaudio-android-0.1.164-debug.apk` 为 `10,078,542` 字节，SHA-256 `81831D01106DADAB2A2C39DCDA305228F7F809BD7D44FFC7126D16F23500B089`。
- 验证：55 个 Python 单元测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug` 通过；FPK 外层 21 个条目、内层 `app.tgz` 110 个条目可读取；APK manifest 为 `com.fnaudio.client / 0.1.164 / minSdk 26 / targetSdk 36`，v2 Debug 签名验证通过。
- 待验证：尚未安装到真实 fnOS/Android 设备；需重点确认启动器图标显示、登录后 CSS/脚本/封面加载、保存密码与历史切换，以及后台/息屏跨曲播放。

## 2026-08-07：`0.1.163` Android 登录、历史连接、启动图标与 WebView 资源修复

- 目标：按真机截图修复 Android 启动图标白色外框、登录后 fnAudio 只显示无样式 HTML 的问题；允许安全保存密码，并把历史连接从登录页移到独立选择页面。
- WebView 根因与修复：部分入口最终 URL 是不带结尾斜杠的 `/cgi/ThirdParty/fnaudio/index.cgi`，相对的 `app.css`、`app.js` 和 API 路径因此解析到了 CGI 同级目录。`index.html` 现在会在检测到 `/index.cgi` 时、首个样式请求前写入以 `/index.cgi/` 结尾的 `<base>`；直接访问本机 TCP Web 服务时保持原路径。
- Android 登录与存储：`ConnectionProfile` 新增密码字段，与连接地址、账号和 token/longToken 一起进入 Android Keystore AES-GCM 加密载荷；`android:allowBackup=false` 保持不变。令牌恢复失败后会自动使用已保存密码登录，日志和界面不会显示明文。
- 历史连接：登录页只保留“历史连接”按钮；新增独立 `ConnectionHistoryActivity`，可选择连接、进入编辑或删除本机加密资料。
- 图标：launcher 改用 Android adaptive icon，蓝色背景由系统蒙版裁切，白色音符作为前景，避免 legacy 图标被启动器再次套白色圆角底框。
- 版本与产物：统一升级为 `0.1.163`。`artifacts/0.1.163/fnaudio-0.1.163.fpk` 为 `4,882,182` 字节，SHA-256 `DA31F9DFF9974A416CBB088CD30C8530D00D1AAF25BD6AC4DCFC04D0933856C2`；`fnaudio-android-0.1.163-debug.apk` 为 `10,071,583` 字节，SHA-256 `7DD22857DE994B89E8877FE38890A5972733938CA2A989219B8F4E660C4ED053`。
- 验证：53 个 Python 单元测试、3 个 Node 回归脚本、JavaScript 语法、Android `lintDebug` 和 `assembleDebug` 通过；APK manifest 为 `com.fnaudio.client / 0.1.163 / minSdk 26 / targetSdk 36`，v2 Debug 签名验证通过；FPK manifest 为 `fnaudio / 0.1.163 / x86`，外层 21 个条目、内层 `app.tgz` 110 个条目可读取。
- 待验证：尚未安装到真实 fnOS/Android 设备。需重点确认启动器图标显示、保存密码后的切换/删除、令牌失效自动登录、CSS/脚本正常加载，以及后台/息屏跨曲播放。

## 2026-08-06：`0.1.162` Android 混合客户端与原生后台播放

- 执行者：Codex
- 目标：开发轻量 Android 客户端，由 WebView 复用 fnAudio 界面，由 Android 原生服务负责队列和播放；支持输入地址、端口、HTTPS、账号密码以及多连接历史，登录后直接打开 fnAudio。
- Android 工程：新增 `android-client/`，使用 Java 17、AGP 9.3.1、Gradle 9.6.1、Media3 1.10.1、ExoPlayer 和 OkHttp。
- 登录与历史：通过 `ws(s)://<host>:<port>/websocket?type=main` 发送 `user.login`，兼容 `user`/`username`；历史恢复尝试 `user.authToken` 和 `user.tokenLogin`。Android Keystore 加密保存地址、账号和 token/longToken，不保存密码。
- WebView：登录后直接加载 `/cgi/ThirdParty/fnaudio/index.cgi/`，初始请求携带 Authorization/Header，并设置同源 token Cookie；异常跳转到桌面/系统入口时显示重新登录提示。
- 原生播放：新增 `PlaybackService` 和 `NativePlaybackBridge`。Web UI 在 Android 桥存在时把完整队列、当前项、播放/暂停、前后曲、seek、音量、循环和随机交给 MediaController；MediaSessionService 持有 ExoPlayer 队列、自动下一首、通知、媒体键、音频焦点、耳机拔出和唤醒锁。
- fnOS 配套：`app.js` 保留普通浏览器 HTML audio 路径，同时增加原生状态回传和恢复逻辑；`cgi_proxy.py` 增加同源 Cookie token fallback。版本同步更新为 `0.1.162`。
- 构建产物：`artifacts/0.1.162/fnaudio-0.1.162.fpk`，SHA-256 `7253729113AEA07F55B93372EDC78BFE4E04E4EB991D71B3EFADEABD8C17CB9A`；`fnaudio-android-0.1.162-debug.apk`，SHA-256 `17898F32B6824C152AF5AA7DE34CE7F8C160547E1BB82028164D785A619C6EF9`。
- 验证：53 个 Python 单元测试、3 个 Node 回归脚本、JS/Python 语法、Android `lintDebug`、`assembleDebug`、APK v2 签名、APK manifest、FPK 外层/内层结构和关键源文件哈希均通过。
- 未验证：当前无 ADB 设备连接，尚未安装 APK/FPK；fnOS 登录 token 到 CGI 的真机交接、2FA/HMAC 固件、自签名 HTTPS、后台/息屏跨曲、通知/锁屏/蓝牙控制、多连接切换和厂商省电限制均待验证。当前 APK 是 Debug 签名，不是正式发布包。

## 2026-08-06：`0.1.161` 虚拟键盘直接覆盖固定播放器

- 目标：让移动端输入法直接覆盖底部歌曲信息和播放控制区域，避免隐藏恢复逻辑及播放器随键盘移动造成的掉帧。
- 修改：搜索期间播放器始终保持 `position:fixed` 和 `display:grid`；保留 viewport 的 `interactive-widget=overlays-content`，并在 WebView 支持时设置 `navigator.virtualKeyboard.overlaysContent = true`，不支持或拒绝写入时安全降级。
- 性能：搜索聚焦期间暂停歌曲信息跑马灯、阴影和过渡，并跳过跑马灯尺寸及移动分页位置测量；失焦后统一恢复一次，避免键盘动画中的同步布局读取。
- 文件：`src/app/ui/app.css`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.161/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过；包外层 18 个文件、运行时 97 个文件，未包含测试、数据库或 Python 缓存。
- 版本与产物：`0.1.161`；`artifacts/0.1.161/fnaudio-0.1.161.fpk`，4,879,924 字节，SHA-256 `427CA1E87EB6030413B11453AF6D120D6B113C1B2835A54260F4F060342CB875`。
- 设备验证：按用户此前要求不代为安装，由用户自行安装测试；输入法覆盖模式、动画流畅度和不支持 Virtual Keyboard API 时的降级行为仍需真机确认。

## 2026-08-06：`0.1.160` 搜索期间保持移动播放器可用

- 目标：修复搜索时隐藏底部歌曲信息和播放控制区域后，部分移动 WebView 无法再次打开播放器的问题。
- 根因：`0.1.159` 通过输入框 `focus` 隐藏播放器，并依赖 `blur` 恢复；部分 WebView 在收起虚拟键盘后不会可靠触发 `blur`，播放器因此永久保持隐藏状态。
- 修改：播放器在搜索期间始终保持 `display:grid`，只切换为绝对定位；暂停歌曲信息跑马灯，关闭阴影和过渡以降低输入法动画期间的重绘；viewport 增加 `interactive-widget=overlays-content`。保留焦点状态类用于性能样式，不再用于播放器显隐。
- 文件：`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.160/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过；包外层 18 个文件、运行时 97 个文件，未包含测试、数据库或 Python 缓存。
- 版本与产物：`0.1.160`；`artifacts/0.1.160/fnaudio-0.1.160.fpk`，4,880,027 字节，SHA-256 `E224641A09A05F5352BA0A24F02F098CB5E33CE967CA4619E855CE5D740F54CE`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；输入法动画流畅度、键盘覆盖行为和播放器可操作性仍需真机确认。

## 2026-08-06：`0.1.159` 移动分页居中与输入法性能优化

- 目标：移动分页信息和按钮居中显示，并消除搜索输入法弹出时底部播放器上移造成的卡顿。
- 修改：移动分页容器和按钮组改为整行居中，页码摘要取消继承的 `flex:1`；搜索获得焦点时一次性隐藏播放器并扩展内容区，失焦后恢复，不监听键盘动画期间的连续 resize。
- 文件：`src/app/ui/app.css`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.159/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.159`；`artifacts/0.1.159/fnaudio-0.1.159.fpk`，4,879,931 字节，SHA-256 `E20A98721E436D6497C19FD0AA15E3B27AD495E8BB180C9B225E8ED9A467CB43`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；输入法动画流畅度仍需真机确认。

## 2026-08-06：`0.1.158` 移动搜索返回主页面

- 目标：把移动搜索栏恢复到主页面顶部，并移除左上角更多菜单中的返回按钮。
- 修改：主内容列表上方新增独立 `type=search` 输入，提供搜索图标、圆角容器、聚焦高亮和原生清除；侧栏恢复为纯导航结构，删除 `mobileBackBtn`、相关样式和 `handleMobileBack()`。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/app/ui/app.js`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.158/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.158`；`artifacts/0.1.158/fnaudio-0.1.158.fpk`，4,879,685 字节，SHA-256 `973795FCA58069CA66CDFE66FDFA168DE8E4E0C63ADD59ACA2E2842DCA379EF2`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.157` 移动搜索与返回布局重构

- 目标：解决移动侧栏中搜索框被返回按钮挤压、输入空间不足的问题，同时明确返回按钮的位置和视觉。
- 修改：第一行使用 `32px + 1fr` 网格放置返回图标与“音乐库”标题；第二行搜索框横跨两列、占满侧栏宽度；返回按钮改为带边框的 SVG 箭头按钮。桌面端仍保持搜索框在导航标题之前。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.157/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.157`；`artifacts/0.1.157/fnaudio-0.1.157.fpk`，4,880,068 字节，SHA-256 `DE79ED0FD54E147B3EEA7CD746078496F012DBDC3A4F55B89BD55D79AB3B609C`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.156` 移动歌词页顶部布局压缩

- 目标：减少移动端歌词界面顶部空白，使返回、歌曲信息、收藏和歌词首屏布局更紧凑合理。
- 修改：移除歌词页对 `safe-area-inset-top` 的重复网格行高与 padding 计算；标题栏固定为 `48px`，三列宽度改为 `52px / 1fr / 52px`，按钮缩小为 `50x30px`；歌词面板顶部 padding 调整为 `8px`。
- 文件：`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.156/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.156`；`artifacts/0.1.156/fnaudio-0.1.156.fpk`，4,879,848 字节，SHA-256 `978A582966255E14AF0694685697596FB67A2019EC72FA1DA481E2BFE06BD28F`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.155` 移动侧栏顶部压缩

- 目标：按移动端截图缩小侧栏及顶部返回、搜索、“音乐库”区域的占用。
- 修改：移动侧栏最大宽度由 `290px` 收窄到 `268px`；返回按钮和搜索框放入同一行；侧栏顶部改为固定紧凑留白，“音乐库”标题紧随工具行。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.155/` 归档记录和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.155`；`artifacts/0.1.155/fnaudio-0.1.155.fpk`，4,879,937 字节，SHA-256 `D8FA806C30C6B3CA0C80592CAF4C66CBB02A75230FEDBEAF961E059D626C6474`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；浏览器安全策略不允许直接渲染本地 `file://` 页面，因此未宣称完成截图级或真机视觉验收。

## 2026-08-06：`0.1.154` 移动端菜单与分页体验优化

- 目标：压缩移动侧栏返回和搜索占用；从右下角更多菜单移除歌词；歌曲列表分页仅在确有多页且滚动到底部时显示。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.154/` 归档记录。
- 实现：返回改为紧凑图标按钮，侧栏顶部和搜索框高度/间距缩小；移动更多动作不再生成歌词项；分页 `pages <= 1` 时完全不渲染，移动端分页栏默认隐藏，列表滚动到底部后显示。
- 版本与产物：`0.1.154`；`artifacts/0.1.154/fnaudio-0.1.154.fpk`，4,879,719 字节，SHA-256 `81562B56F54490F8C1E84E3D06B76606E2D44AF7B94649C365B364F4B464C2A9`。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归和移动端布局回归均通过；包内 manifest、缓存键和 97 个运行时文件已校验。
- 设备验证：尚未完成。fnOS 应用中心手动安装需要自定义向导参数，官方 `trim-cli app install-fpk` 已连接设备但返回该安装限制，设备仍运行 `0.1.153`。

## 2026-08-06：`0.1.153` 移动端初始化修复与 fnOS 验收

- 目标：完成移动端布局修复后的可安装发布，避免移除移动搜索输入后阻断初始化，并记录真实设备结果。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`、`SOURCE_MANIFEST.sha256`，以及当前恢复/发布文档和 `artifacts/0.1.153/` 验收记录。
- 实现：对可选的 `mobileSearchInput` 增加存在性守卫；移动端使用侧栏搜索和返回入口，移除顶部分类栏，固定分页区域并让歌曲列表独立滚动，歌词页顶部采用不重叠的三列控件布局。
- 版本与产物：`0.1.153`；`artifacts/0.1.153/fnaudio-0.1.153.fpk`，4,879,159 字节，SHA-256 `A2214FD1A07513634229EAF2A91A685EE60AD56FED25F2BF66CDB6AE62BDB3F0`。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列 Node 回归和移动端布局 Node 回归均通过；FPK manifest、缓存键、内容清单和哈希一致。
- 设备验证：已完成 fnOS 应用中心 `0.1.152 -> 0.1.153` 覆盖升级，状态为 `running`，`/api/health` 正常；移动视口烟雾确认菜单搜索/返回、分类移除、列表滚动容器、分页栏和歌词头部不重叠。
- 未验证：设备音乐库为 0 项，真实长列表手势、分页按钮操作、歌词实际播放状态及“从当前开始播放全部歌曲”全流程；全新安装、停止/启动、卸载、硬件和 DLNA 互操作也未覆盖。

## 2026-08-06：`0.1.152` 移动端布局验收包

- 生成 `artifacts/0.1.152/` 作为移动端布局的中间 FPK，保留其本地测试、结构检查和设备升级记录；当前开发基线随后推进到 `0.1.153`。

## 2026-08-06：`0.1.151` 队列当前曲目同步与设备验收

- 目标：让“正在播放”只显示在当前播放队列，并在切换歌曲后立即同步标识、分页和滚动位置。
- 修改文件：`src/app/ui/app.js`、`src/tests/test_ui_queue_columns.js`、`VERSION`、`src/manifest`、`src/app/ui/index.html`、`SOURCE_MANIFEST.sha256`，以及根目录恢复文档和 `artifacts/0.1.151/` 验收记录。
- 实现：当前项样式仅在 `state.view === "queue"` 时显示；新增队列展示同步入口，由播放核心快照、远端播放无当前项和本机 CUE 自动切歌共同调用。索引变化时会重新计算目标页、重渲染，并在下一帧滚动到当前行。
- 版本与产物：`0.1.151`；`artifacts/0.1.151/fnaudio-0.1.151.fpk`，4,878,955 字节，SHA-256 `05CC22B336A9AC821B0166A31D401B0383A425DA88679CA928604F8FCBB6A039`。
- 本地验证：50 个 Python 单元测试、`node --check app/ui/app.js` 和 `node tests/test_ui_queue_columns.js` 通过；外层 FPK 与内层 `app.tgz` 可读取，manifest 和静态资源缓存版本均为 `0.1.151`。
- 设备验证：已通过 fnOS 应用中心完成 `0.1.150 -> 0.1.151` 覆盖升级，设备状态为 `running`，保留 228 首音乐、队列和播放状态。打开当前队列显示一个当前曲目标识；点击下一曲后队列即时跳到新曲目所在页，标识随新曲目移动；非队列视图不显示该标识。
- 未验证：全新安装、端口变更、停止/启动、两种卸载、USB DAC、移动 WebView、DLNA 互操作和“从当前开始播放全部歌曲”完整设备端流程。

> 规则：按时间倒序追加。记录目标、实际文件、行为变化、验证和遗留问题。不要只写“已修改”。

## 2026-08-06：建立 Git `0.1.150` 基线

- 执行者：Codex
- 目标：把 `C:\path\to\fnAudio` 从无版本历史的目录转为可恢复、可审计的 Git 工作树。
- 修改文件：新增 `.git/` 元数据；更新 `.gitignore`、根恢复文档和技术决策。
- 版本控制范围：提交当前源码、文档、完整性清单和必要构建工具；排除 FPK、历史 staging、派生包检查目录、运行时缓存/数据库/凭据，以及嵌套第三方 Git 仓库。
- 结果：创建 `main` 分支的初始 `0.1.150` 基线提交，并标记 `v0.1.150`。
- 后续：本地仓库尚无远程备份；应在确认托管位置与访问控制后推送到私有远程仓库。

## 2026-08-06：构建 `0.1.150` FPK

- 执行者：Codex
- 目标：为已完成的队列定位和专辑序号列功能生成可安装 FPK，并将当前源码版本升级为 `0.1.150`。
- 修改文件：`VERSION`、`src/manifest`、`src/app/ui/index.html`、`SOURCE_MANIFEST.sha256`，以及根目录恢复文档和 `artifacts/0.1.150/` 归档记录。
- 版本行为：FPK manifest、根版本标识和 `app.css`/`app.js` 缓存键均为 `0.1.150`；没有修改播放、音乐库或协议行为。
- 产物：`artifacts/0.1.150/fnaudio-0.1.150.fpk`，4,878,790 字节，SHA-256 `B70EAEE3913AC9AEE8C5CE003C5CC409BC8CF535960B702C19398B593F1A8660`。
- 验证：50 个 Python 单元测试、Node 前端回归和 JavaScript 语法检查均通过；外层 FPK 与内层 `app.tgz` 可读取，manifest 和前端资源版本为 `0.1.150`，运行时负载包含 97 个文件且排除测试、缓存、数据库和 Python 字节码。
- 未验证：未安装到 fnOS 真机。`0.1.149` 设备验证不覆盖本包新增的当前队列定位和专辑详情序号列，需单独真机验收。

## 2026-08-06：当前队列定位与专辑序号列

- 执行者：Codex
- 目标：打开当前播放队列时直接定位正在播放的歌曲并提供清晰标识；在所有专辑详情的曲目列表默认首列显示“序号”。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/tests/test_ui_queue_columns.js`、`SOURCE_MANIFEST.sha256`。
- 队列行为：底部播放器和导航中的当前队列入口都会清除列表筛选；根据当前排序计算当前项所在页，渲染后滚动至行中部。队列行携带原始队列位置，重复曲目只会在真实当前位置显示“正在播放”标签。
- 专辑行为：专辑、歌手专辑和作曲者专辑详情共用 `albums:tracks:*` 列作用域，新的默认列为“序号、标题、歌手、专辑、大小、格式”；保存的旧默认列会自动迁移，明确自定义的列配置不被覆盖。
- 验证：`python -B -m unittest discover -s tests -v` 通过（50 个测试）；`node --check app/ui/app.js` 通过；`node tests/test_ui_queue_columns.js` 通过，覆盖重复 ID 队列项的正确页定位及旧专辑列默认值迁移。
- 未验证：本轮未构建或安装新 FPK，fnOS WebView、实际长队列滚动和专辑详情的真机视觉效果需要在下一个更高测试版本中验收。

## 2026-08-06：评估并缓存第三方 `FNOS-API`

- 执行者：Codex
- 目标：对照 `heijiangangqin/FNOS-API` 与飞牛官方开发/API 文档，判断其是否能帮助 fnAudio 后续开发，并在有价值时保留可恢复本地快照。
- 应用源码修改：无。未修改 `src/`、未安装该第三方应用、未建立 NAS 会话、未写入任何凭据。
- 缓存：以浅克隆方式保存到 `references/FNOS-API-upstream`，固定提交 `33101767e01a7f413cac5e0ed016f6a9483df526`（`main`，2026-07-21），工作树干净。
- 结论：该项目是 Node.js/Express 对 `trim-cli` 的 REST 封装，适合外部验收、应用中心操作对照、日志导出和设备监控参考；它不提供 fnAudio 所需的媒体/播放能力，也不能取代官方 Scope、ACL、JS SDK 和本地 open-gateway 机制。
- 风险：服务监听 `0.0.0.0:9932`、启用全域 CORS、默认 Bearer token、未受 token 保护的登录路由、明文 NAS 凭据，以及大量自动确认的破坏性管理操作。因此明确禁止作为 fnAudio 依赖或内部 HTTP 服务。
- 文档：新增 `references/FNOS_API_EVALUATION.md`，并更新参考索引、项目上下文和技术决策。

## 2026-08-06：`0.1.149` 临时升级包真机验收

- 执行者：Codex
- 目标：在不卸载现有应用、不清除用户音乐库或播放状态的前提下，验证本次优化后的 `0.1.148` 源码能否在真实 fnOS 上完成覆盖升级并启动。
- 应用源码修改：无。`C:\path\to\fnAudio\src`、`src/manifest` 和 `SOURCE_MANIFEST.sha256` 均未改动，正式开发基线仍是 `0.1.148`。
- 构建方式：复制 `src/` 至 `artifacts/0.1.149/stage/`，仅将 `manifest` 中的版本号改为 `0.1.149`，使用 `fnpack 1.2.3` 构建 `fnaudio-0.1.149.fpk`。
- 产物：`artifacts/0.1.149/fnaudio-0.1.149.fpk`，4,876,087 字节，SHA-256 `B7FD239E26D69AC16CE8C1F4B788AE6528F47E2DBA479FCC33B1CD9B0B507AA0`。
- 安装结果：fnOS 应用中心成功把 `fnaudio` 升级为 `0.1.149`，应用状态为 `running`；服务端口维持 `18081`，原音乐库配置和播放队列保留。
- 完成验证：设备端 `app.js`、`index.html`、`server.py`、`transcode.py` 与 `src/` 哈希一致；CGI 页面正常显示全部音乐；`/api/health`、`/api/library/status`、`/api/playback/core`、`/api/playback/targets`、`/api/mpd/status` 冒烟通过，音乐库为 228 首（含 5 首 DSD），MPD `0.23.12` 运行中。
- 专项验证：当前 FLAC 曲目 `d412eb7fd07a94df` 初始转码缓存未就绪，调用 `POST /api/transcode/warm` 后约 6 秒变为就绪；歌词页不再有 `lyricsQueueBtn`，点击底部队列按钮会关闭歌词页并转到当前队列。
- 未完成：未执行会改变现有队列和播放状态的“从当前开始播放全部歌曲”完整 E2E。全新安装、端口变更、停止/启动、卸载、USB DAC、移动 WebView、FFmpeg 压力和 DLNA 互操作也未在本轮覆盖。
- 文档：新增 `artifacts/0.1.149/{SHA256SUMS,PACKAGE_CONTENTS.txt,VALIDATION.md}`，并同步根目录恢复、待办、架构决策和产物索引文档。

## 2026-08-06：fnOS 真机安装尝试与环境冒烟测试

- 执行者：Codex
- 目标：将 `artifacts/0.1.148/fnaudio-0.1.148.fpk` 安装到用户提供的 fnOS 测试设备并进行基础验收。
- 应用源码修改：无。
- 安装结果：应用中心接受 FPK 上传并完成包解析；确认标准未验证第三方应用提示后，因设备已安装相同或更高的 `fnAudio 0.1.148` 而拒绝覆盖。未卸载、未覆盖或重启现有应用，未改动配置或音乐数据。
- 已发现状态：设备运行的同版本 `fnaudio` 核心文件哈希与当前源码不同，属于优化前代码，不能作为本 FPK 的验收实例。
- 环境验证：现有实例服务端口可访问；`/api/health`、`/api/library/status`、`/api/playback/core`、`/api/playback/targets`、`/api/mpd/status` 均返回 `HTTP 200`；CGI 页面正常加载音乐库，MPD 正在运行。
- 未完成：需要用户明确选择“保留数据卸载后重装当前 `0.1.148` FPK”或“创建更高的独立测试版本”后，才能完成本包的真机安装、升级、端口、启动停止和卸载验收。

## 2026-08-06：重建并归档 `0.1.148` FPK

- 执行者：Codex
- 目标：基于 `C:\path\to\fnAudio\src` 的当前 `0.1.148` 源码构建可安装 FPK，并保留可恢复的包身份和验证记录。
- 应用源码修改：无。
- 构建命令：在 `C:\path\to\fnAudio\artifacts` 执行 `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src`，使用 `fnpack 1.2.3`。
- 产物：`artifacts/0.1.148/fnaudio-0.1.148.fpk`，4,878,142 字节，SHA-256 `856088E19DD926F0ACE2F07C0BB0E76526BB129F6A3A807A27EB2E27686EB4E1`。
- 记录更新：`README.md`、`PROJECT_CONTEXT.md`、`RECOVERY.md`、`TODO.md`、`artifacts/README.md` 以及版本产物目录中的校验文件。
- 验证：50 个 Python 单元测试通过；`node --check app/ui/app.js` 通过；`fnpack` 构建成功；外层 FPK 和内层 `app.tgz` 可读取；包内 manifest 是 `fnaudio / 0.1.148 / x86`，运行时负载中包含 server、UI、CGI、MPD 和运行库，未包含测试、历史 builds、缓存或本地数据库。
- 未验证：尚未在真实 fnOS 设备执行全新安装、升级、改端口、进程生命周期和卸载验证。

## 2026-08-06：歌词导航、当前曲目缓存与全量队列修复

- 执行者：Codex
- 目标：修复歌词页队列返回、优先缓存当前播放曲目，以及“从当前开始播放”没有完整装载列表的问题。
- 修改文件：`src/app/ui/index.html`、`src/app/ui/app.js`、`src/app/server/transcode.py`、`src/app/server/server.py`、`src/tests/test_transcode_cache.py`。
- 歌词页：删除顶部重复的队列按钮；底部播放器的队列按钮在歌词页打开时先关闭歌词视图，再切换到当前队列。
- 当前曲目缓存：新增 `POST /api/transcode/warm`。前端在本地 MP3 转码曲目设置媒体 URL 前请求缓存；后端将当前曲目放入优先级 `0` 的单工作线程缓存队列，普通媒体预热使用优先级 `100`。
- 全量队列：从当前曲目开始播放时队列保留完整上下文，服务端通过 `current_id` 定位当前曲目；收藏和歌单场景会补齐未缓存的曲目 ID 后再创建队列。
- 兼容性：原格式播放、DSD/CUE 转码、远程 DLNA 目标及既有 `/api/transcode/status` 行为保持不变。
- 验证：`python -B -m unittest discover -s tests -v` 通过，50 个测试；新增缓存优先级回归测试。`node --check app/ui/app.js` 通过。
- 未验证：尚未在真实 fnOS WebView、真实大歌单和实际 FFmpeg 转码负载下完成端到端验证。

## 2026-08-06：建立 `0.1.148` 可恢复项目目录

- 执行者：Codex
- 目标：把当前项目、文档和恢复上下文整理到 `C:\path\to\fnAudio`，避免依赖历史 AI 会话。
- 源码基线：`E:\Codex\fnaudio-0.1.7`，`manifest` 版本 `0.1.148`。
- 新建根文档：`README.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`TODO.md`、`CHANGELOG_AI.md`、`RECOVERY.md`。
- 新建索引和策略：`docs/INDEX.md`、`docs/history/README.md`、`artifacts/README.md`、`.gitignore`、`VERSION`。
- 复制源码：将当前可继续开发的代码、测试、MPD 二进制和动态库复制到 `src/`。
- 归档文档：旧迁移说明、阶段 TODO、发布片段和原始分析归档到 `docs/history/`。
- 排除内容：根 `builds/`、旧版本源码、FPK 解包目录、参考仓库、旧 FPK、`app.tgz`、陈旧 `transcode/library.json` 未作为当前源码引入。
- 生成内容：`SOURCE_MANIFEST.sha256` 和 `docs/SOURCE_INVENTORY.md` 记录恢复快照身份。
- 产品行为变化：无。没有修改 Python、JavaScript、CSS、fnOS 配置或生命周期脚本内容。
- 原工作区变化：保留不动；此前只在原当前源码中新增过一份 `PROJECT_CONTEXT.md`。
- 验证：在 `C:\path\to\fnAudio\src` 重新运行 49 个 Python 单元测试，全部通过，耗时约 0.9 秒。
- 语法验证：`node --check app/ui/app.js` 通过；39 个 Python 文件 AST 解析通过。
- 一致性验证：136 个源码文件均能在原 `0.1.148` 来源中找到，SHA-256 差异为 0。
- 恢复验证：根目录必需文档无缺失，`VERSION` 与 `src/manifest` 均为 `0.1.148`，源码清单为 136 条，Markdown 代码块完整。

## 记录模板

```markdown
## YYYY-MM-DD：标题

- 执行者：
- 目标：
- 修改文件：
- 行为变化：
- 数据或兼容性影响：
- 验证：
- 未验证：
- 后续事项：
```
