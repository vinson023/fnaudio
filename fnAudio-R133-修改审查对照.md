# fnAudio R133 修改审查对照（Codex 审查视图）

本轮一笔提交：HEAD `41ba071`（父 `9c2e994`）。改动 6 个被跟踪文件，其中源码 2 个、根文档 3 个、清单 1 个。下面逐 hunk 说明改了什么、为什么、判别证据在哪。

## 一、`src/app/ui/response_json_loader.js`（源码修复本体）

### Hunk 1 @@ -15,6 +15,41：新增 `utf8ByteLengthBounded(text, limit)`（现 L26）
- **它解决什么**：text() 分支要在不产生整份 UTF-8 副本的前提下量出字节数，且在没有 `TextEncoder` 的宿主上也要能量。
- **算法**：逐 code unit 累加字节数——`<0x80`→1、`<0x800`→2、高代理 `0xD800..0xDBFF` 看下一个 code unit，成对（`0xDC00..0xDFFF`）计 4 且消耗两 code unit、孤立计 3、其余（含孤立低代理、BMP 常规字符）计 3。
- **与 `TextEncoder` 非 fatal 等价**：孤立代理 → U+FFFD 正好 3 字节；成对代理 → 4 字节。运行期不再引用 `TextEncoder`（仅注释提及）。
- **可早退**：`total > limit` 立即返回 `limit + 1`（现 L48），使热路径在超预算时不做无谓的整串扫描。
- **审查关注点**：代理对分支 `i += 1` 与外层 `i += 1` 叠加，正确跳过第二个 code unit；`next` 取不到时以 0 兜底，落在孤立分支计 3，与 TextEncoder 对末尾孤立高代理的处理一致。

### Hunk 2 @@ -166,11 +201,9：text() 分支改用有界计数（现 L204）
- 旧：`if (text.length * 3 > maximum && typeof TextEncoder === "function") { if (new TextEncoder().encode(text).byteLength > maximum) {...} }`
  - 缺陷①：无 `TextEncoder` 的宿主整段跳过 ⇒ 预算空洞；
  - 缺陷②：`new TextEncoder().encode(text)` 为量长度额外分配整份编码副本。
- 新：`if (text.length * 3 > maximum && utf8ByteLengthBounded(text, maximum) > maximum) { status = "oversize"; return outcome(fallback); }`
  - 去掉 `typeof` 门（补空洞）；`text.length * 3 > maximum` 仍是便宜上界短路（因 UTF-8 每 code unit ≥1 字节，真字节数 ≥ `text.length`，故该上界门与真 TextEncoder 分类一致，不会漏判也不改变 oversize 判定）；`text.length > maximum` 的更早硬短路与末级 `response.json()` 回退均保留、不收紧（回退按「唯一宿主 `nativeHttpResponse()` 同时暴露 text()/json()」以证据保留）。

## 二、`src/tests/test_ui_response_json_loader.js`（判别测试，+约95行）

### Hunk @@ -323,9 +323,10 / @@ -363,7 +364,11 / @@ -376,7 +381,11：修正旧 measured 段
- 原以「进入测量带即调用一次 `TextEncoder`」为证据（断言 `encoderCalls` 相对 `beforeMeasured` 增加 1／3）。
- 契约变了：测量带内现在**不得再分配**编码副本，故把这两条代理断言的期望改为 `beforeMeasured`（零增量）。
- 性质：**收紧回归守卫，不是放宽**——旧行为（分配副本）现在会被这两条判红。

### Hunk @@ -591,6 +600,95：新增判别块
1. **oracle 等价环**：真 `TextEncoder` 作 oracle，`maxBytes` 1..20 × 8 元代理字母表两两组合 × 「有编码器／无编码器」双 loader，逐格断言 oversize 分类相等 ⇒ 预算空洞闭合（无编码器主机也能测得；旧码在此必失败）。
2. **零再分配计数**：`counted.calls() === 0`（现 L667）——测量预算时不得调用编码器。
3. **代理边界**：成对与孤立各测 n-1（oversize）与 n（非 oversize）。
4. **两条源码级正则守卫**：禁现 `new TextEncoder().encode(text)`、必须在文 `utf8ByteLengthBounded(text, maximum)`。

## 三、根文档与清单（记录面）
- `TODO.md`：L2 新增 R133 记录并关闭原 L162；尾 4 LF、0 CR；开放 68＝代码10＋设备44＋决策1＋台账13（本会话按节边界独立复扫确认）。
- `CHANGELOG_AI.md`：R133 三条最新在前（取证与实现／测试与变异矩阵／收口·终跑·清单），尾 9 LF；终跑行仅引用门禁稳定值（`Ran 2483 tests`／`OK (skipped=2)`／JS 73 passed），已剔除易变墙钟秒。
- `PROJECT_CONTEXT.md`：L2 记一条本轮教训，尾 8 LF。
- `SOURCE_MANIFEST.sha256`：PowerShell 5.1 幂等复跑 707 条，仅两个源文件哈希行变动，逐文件 sha MATCH。

## 四、变异证明（仓库外 `clone --no-hardlinks` 副本，已删）
控制组先绿：全量 Python 2483 OK(skipped=3 副本口径)、全量 Node 74/74。M1 还原 `typeof TextEncoder` 门、M2 代理对计 3、M3 孤立高代理计 4、M4 早退 `>`→`>=`，四条分别被「零再分配断言／oracle 环／oracle 环／精确预算仍解析」击杀，4/4 全灭。

## 五、门禁终跑
`artifacts/offline-20260921-round206.log`：exit 0、`Ran 2483 tests`、`OK (skipped=2)`、0 条 `FAILED`、JS 含 `passed` 结果行 73；该 log mtime（07:18:09）晚于本轮全部代码／文档／清单编辑。%TEMP% 本轮 30 个 `r133_*.py` 脚本已全部删除。未 push、未改 `.gitignore`、设备段未动。
