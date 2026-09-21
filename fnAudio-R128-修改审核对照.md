# fnAudio R128 修改审核对照（本文件不入库）

- 轮次：R128（累计已完成 37 轮）
- 基线：`0b6be71 chore: record R127 closure`
- 本轮提交（4 笔，全部逐文件显式 pathspec，未使用 `git add -A`，未触碰 `.gitignore`）：
  1. `1875de5` perf(library): probe cached permissions on drift and make the pooling guard structural — 6 文件 `+329/-25`
  2. `95f3caf` chore: record R128 closure — 4 文件
  3. `873e1c7` style(tests): restore the blank lines the paired-sampling class lost — 1 文件 `+3`
  4. `ca8bcc7` chore: record the R128 review correction — 3 文件 `+4/-4`
- 门禁终跑：`artifacts/offline-20260921-round195.log`（420261 字节）
  `Ran 2473 tests in 112.107s` / `OK (skipped=2)` / JS 段 74 个文件全绿（73 行含 `passed` + 1 行 `ui library metadata merge policy regression ok`）/ 实测 exit 0
- 清单：`SOURCE_MANIFEST.sha256` 刷新后仍 706 条；独立复算 0 缺失 / 0 不符 / 0 未列 / 0 重复；diff 仅 1 行 sha
- 关闭：TODO 原 L161（`- [x]` 已关闭 1470 → 1472）；可离线代码待办 14 → 13

---

## 一、`src/app/server/file_permissions.py`（192 行）

**hunk `@@ -78,8 +78,15 @@`**

```
 def secure_sqlite_files(path: str) -> None:          # :80
+    """Keep a database and its sidecars private.     # :81-87（新增 docstring）
+       Called on every read of a pooled connection ...
+       frequency is the security invariant, a reused handle only proves the pragmas."""
     for suffix in ("", "-wal", "-shm"):              # :88
-        secure_file(path + suffix, PRIVATE_FILE_MODE)
+        secure_file_on_drift(path + suffix, PRIVATE_FILE_MODE)   # :89
```

逐点审核：

- `secure_file_on_drift` 不是新写的，它就在同文件 `:58`，本轮之前已存在并被 `:80` 的调用方替换进来。也就是说本轮只做了「一次 lstat 探测 vs 多次 chmod 系统调用」的替换，没有新增权限判定分支。
- 语义等价性：`secure_file_on_drift` 在权限已经满足时不 chmod，不满足时 chmod 到 `PRIVATE_FILE_MODE`；三件套（主库 / `-wal` / `-shm`）仍然每一件都被访问到，不存在「因为复用句柄就整段跳过」。这一点被 docstring（`:81-87`）显式写死为「刷新频率才是安全不变量」，防止后来者反向优化成「句柄复用即跳过」。
- 副作用半径：`secure_sqlite_files` 全文共 5 处调用（`library.py:2075 / 2079 / 2124 / 2160 / 2479`），本轮一处未删。写路径 `library_db_writer`（`library.py:2447`）→ `:2454` 与 `save_library_cache` → `:3004` 保持原样。故被降代价的只有读侧。
- Windows 上 `chmod` 只影响只读位，实际安全边界由 ACL 承担，这本来就是该模块既有前提；因此「少 chmod」在 Windows 侧不是安全降级，Linux 侧才需要 `test_sqlite_sidecars_are_probed_once_and_chmodded_only_on_drift` 来锁住（见第三节）。

## 二、`src/app/server/library.py`（3126 行）

**hunk 1 `@@ -22,7 +22,7 @@`**：`:25` 的 import 增加 `secure_directory_on_drift`。仅新增符号，未移除任何原有符号，`secure_directory` 仍在同一行 import 内且仍被使用（下节计数）。

**hunk 2 `@@ -2091,7 +2091,11 @@`**：读入口 `library_db_connect`（`def` 在 `:2085`）内，`:2094-2097` 是 4 行注释，`:2098` 为：

```
    secure_directory_on_drift(config["cache_dir"])
```

逐点审核：

- 注释 `:2094` 起明确写了「每一次读仍然加固缓存目录，只是探测变便宜」，并交代 drift 探测只在「目录不存在 / 不是目录」时回落到全量路径；这是本轮唯一的行为改动，且是只降频不降覆盖。
- 目录级和文件级两处降代价都只发生在读入口；写入口 `library_db_writer`（`:2447`）未改。
- 计数级防线在测试里（第五节 `test_only_the_read_entry_uses_the_cheap_directory_probe`），源码级断言 `secure_directory_on_drift(config["cache_dir"])` 恰 1 处、`secure_directory(config["cache_dir"])` 恰 2 处 —— 有人把写侧也顺手改成 drift，测试会红。
- 实测收益：一次池化读的系统调用 16 → 7；ABBA 交替采样 N=301，中位 0.0818ms → 0.0383ms，301/301 全胜（不是个位数样本上的结论）。

## 三、`src/tests/test_file_permissions.py`（221 行）

**hunk 1 `@@ -73,7 +73,7 @@` → `:76`、hunk 2 `@@ -123,7 +123,7 @@` → `:126`**：两处指向已失效行号的注释指针 `file_permissions.py:85` 改为按条件本身表述（`os.name is "nt"`）。旧串在全文出现 0 次，新串 2 次。属纯注释，不影响行为，目的是消掉「注释里的行号比代码跑得更快」这类长期腐化。

**hunk 3 `@@ -168,5 +168,54 @@` → 新增 `:171` `test_sqlite_sidecars_are_probed_once_and_chmodded_only_on_drift`**（本条即该待办的判别性测试）：

- 5 组 `subTest`：① 三件权限本已私有 → 零 chmod；② `-wal` 漂移到 `0o666` → 只对 `-wal` chmod；③ 两个 sidecar `FileNotFoundError` → 只加固主库且不抛；④ `-shm` 是 `S_IFLNK` → 不当目录/文件误处理；⑤ `-wal` 是 `S_IFDIR` → 走异常分支不外溢。
- 判别机制：`fake_lstat` 记录访问顺序，断 `seen == abspathed`（三件都必须被探测到，这是「覆盖没丢」的证据）；`secure_file` 一旦被调用即 `AssertionError("the full multi-syscall probe is back")` —— 这条把「退回全量」变成必红，而不是静默变慢。
- chmod 断言双重：参数集合只含漂移项，且第二参必须是 `PRIVATE_FILE_MODE`（防止用 0o644 之类「看起来也行」的模式蒙过）。
- 沿用该文件既有的平台信任前提注释（`:97`、`:158`），未新设平台假设。

## 四、`src/tests/test_library_sqlite.py`（3704 行）

**hunks（`@@ -166 / -184 / -201 / -336 / -352 / -367 / -381`）**：7 处既有打桩缝隙 `:169 / :188 / :206 / :400 / :417 / :433 / :448` 各补一行 `secure_directory_on_drift`。这些不是新测试，而是「打桩面必须跟上真实调用面」的必要修补 —— 不补的话读入口新增的这次目录探测会直接真打到磁盘上，测试会在 CI 机器上留下真实权限副作用或者干脆报错。

**`@@ -210,6 +213,64 @@` → 新增两条**：

- `:216` `test_a_borrowed_handle_is_still_hardened_on_both_ends`：先断 `reuses + 1`（证明句柄确实被复用了，避免整条测试在「其实没复用」上空转），再断 `refresh.call_count == 2` 且两次入参都是 `library_db_path(config)`。这条锁的是「借来的句柄两端都要重新加固」。
- `:235` `test_only_the_read_entry_uses_the_cheap_directory_probe`：读侧 drift=1 / full=0；写侧 full=1 / drift=0；再加源码级计数（第二节所述）。既有行为计数又有源码接线，是本轮防「后来者改回去」的主承力。

## 五、`tools/benchmark_large_library.py`（954 行）

**hunk 1 `@@ -121,6 +121,63 @@` — 新增三个纯函数**：

- `paired_ab_samples(arms, samples)` `:124-153`：臂数不等于 2 或样本数小于 1 抛 `ValueError`；排布为 `forward if index % 2 == 0 else backward`，即 ABBA 交替，抵消单调漂移（温度、页缓存、后台回收）对「谁快」的影响。
- `median_duration(values)` `:156-161`：空序列抛 `ValueError`；偶数取上中位，避免中位数落在两值之间产生「无法对应任何一次真实采样」的假精度。
- `pooled_reuse_guard(before, after, samples)` `:164-178`：判据是窗口差 —— 只有 `reuses < samples - 1` 或 `creations > 1` 才抛；缺键按 0 处理。

  这是本轮最关键的一处改法。旧实现拿「池化必须更快」当门，而 `artifacts/offline-20260920-round185.log` 记录的是同一份代码两次跑出 108.523s 与 144.808s —— 门是计时器噪声在决定红绿，不是回归。新判据问的是结构问题：整段采样窗口内池子到底有没有被持续复用。计时从此降级为报告项。

**hunk 2/3 `@@ -638,7 +695,10 @@`、`@@ -647,35 +707,51 @@` — first-screen 段 `:702-758`**：

- `cold_first_screen` `:702`、`read_arm` `:712`；guard 调用在 `:738`；两臂中位在 `:739-740`；`pooled_faster_pairs` `:752-754`（纯报告，非门）；`idle_after_drain` `:757`。
- 删除了两处死/害码：「池化必须更快」的 `RuntimeError`（旧串 `not faster than reopening` 全文 0 次）与嵌套的 `median_sample`（0 次），中位数统一走模块级 `median_duration`。

## 六、`src/tests/test_large_library_benchmark.py`（333 行）

**`@@ -1,3 +1,4 @@` / `@@ -7,10 +8,16 @@`**：`:1` 增 `import io`；`:11-13` 增三个 helper 的导入；`:18-19` 增 `TOOLS_ROOT` / `BENCHMARK_SOURCE`（后者供源码级接线断言读取文本）。

**`@@ -175,18 +182,26 @@` — 改造既有大测（`:36`，全文件唯一真正跑 `run_benchmark` 的用例）**：

- `:186-191` 注释重写，说明计时只是证据不是门。
- `:192-204` 断言从性能阈值改为结构/范围：删 `assertGreater(speedup, 1.0)`、`assertGreater(saving_seconds, 0.0)`；改为 `unpooled_seconds` / `pooled_seconds` 均 `> 0`、两字段 `isInstance float`、`pooled_faster_pairs` 必须是 int 且 `0 <= x <= samples`。这样「报告字段存在且类型正确」被锁住，而「今天机器快不快」不再决定红绿。
- `:205-210` 保留原有的数值精度重减断言，未放宽。

**`@@ -223,5 +238,96 @@` — 新增 `FirstScreenPairedSamplingTests`（`:241` 起，8 条）**：ABBA 精确序断言 `["u","p","p","u","u","p","p","u","u","p"]` 及其分臂归属；3 种 `ValueError`；偶数上中位；窗口差判据命中样例 `(4,1)`；3 种失败窗口；缺键按 0；pooled 全输时只报告不抛；`:317-330` 源码接线断言（含两条 `assertNotIn`，把被删的旧门和死码钉住）。

**`873e1c7` 的来历（自查更正）**：`1875de5` 首版把新类直接接在上一方法体之后（0 空行），并吃掉了基线 `if __name__`（`:332`）前两空行之一，文件 333 而非应有的 333=330+3。`873e1c7` 补回 3 个空行，恢复 PEP8 两空行与类前空行；`py_compile` 通过，该模块单跑 `Ran 10 OK`。

**`ca8bcc7` 的来历**：因上述行号位移，根文档里 4 处指针 `:239` 需改为 `:241`（TODO L2 一处、CHANGELOG L3 一处），并在 TODO L2 尾追加 ⑧、CHANGELOG L3/L4 尾追加更正说明与 `round194 → round195` 的终跑日志指向；同笔刷新 `SOURCE_MANIFEST.sha256`。

## 七、记录层（`@@ -1,4 ...`、`@@ -158,7 +159,7 @@`）

TODO `L2` / CHANGELOG `L2-L4` / PROJECT_CONTEXT `L2-L3`，最新在前。本轮关闭的是 TODO 原 `L161`。设备段（1059 行区块）与 `972f733` 逐字节 identical，未动、未盲改。

## 八、变异证明（仓库外副本 `E:\temp\fnaudio-r128copy`，已删除）

- 控制组先绿：`Ran 2473 OK (skipped=3)` + Node 74 项 0 失败。
- V1~V8 全部被杀。其中 V7（把读入口换回全量 `secure_directory`）的杀手是源码接线断言而非行为断言，已在记录中如实登记，不冒充「行为测试抓到了它」。

## 九、格式异常存量说明

以下三处缩进/格式异常系历史存量，非本轮引入，按纪律未顺手改动：
`app/server/state_projection.py:62`、`tests/test_dlna_network.py:51`、`tests/test_metadata_service.py:4043`。
另 `library.py:2085 / :2447` 的装饰器紧邻 def 属正常写法，不计为异常。

## 十、CRLF 说明

`core.autocrlf=true` 下 `update_source_manifest.ps1`（PowerShell 7）产出 CRLF 工作副本，提交时自动归一为 LF（HEAD blob 实测 CR=0）。该现象按警告处理，不算清单失真。

## 十一、剩余量（磁盘实测）

- 距四项终止条件差 **14** 条：可离线验证代码项 **13** ＋ 需产品决策项 **1**（TODO「需要项目负责人决策」节，仍在等含无标签音频样本的真机取证）。
- 设备/外部项 **44** 条：不动、不盲改。台账 13 条不计入终止条件。
- 计数快照并存不合并（保留历史取证原值）：`155=64+82+9`、`115=51+43+8+13`、`76=18+44+1+13`、`72=14+44+1+13`、R128 后 `71=13+44+1+13`。
- 已完成 37 轮；`maxGoalRounds=72` 不构成终止理由，也不为凑数关闭半件事。
