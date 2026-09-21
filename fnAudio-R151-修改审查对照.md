# fnAudio R151 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮为**深读＋当轮修复轮**：读完 `src/app/ui/app.js`「当前播放曲目的封面与进度」簇 31 个函数，簇内读到 1 处真缺陷并当轮修掉、当轮证伪 4 处疑点。**净关闭 0 条既有代码待办、新立 0 条**（0 ≤ 0，口径见 `docs/REVIEW_ROUND_DISCIPLINE.md` 第二节），收益记在浅读面条的深读分子 31 → 48 与这一处缺陷上。

## 文件净增（`git diff --numstat`，HEAD = `e566306` R150 packet）

| 文件 | + | − |
|---|---|---|
| `CHANGELOG_AI.md` | 2 | 0 |
| `PROJECT_CONTEXT.md` | 1 | 0 |
| `SOURCE_MANIFEST.sha256` | 2 | 1 |
| `TODO.md` | 3 | 2 |
| `src/app/ui/app.js` | 12 | 2 |
| `src/tests/test_ui_cover_source_rejection.js` | 87 | 0（本轮新增文件） |

## 一、开工取证（磁盘实测，不采信交接快照）

- 分支 `main`、HEAD `e566306 docs(round-review): carry the R150 review packet`。`MERGE_HEAD`／`rebase-merge`／`rebase-apply`／`CHERRY_PICK_HEAD`／`REVERT_HEAD`／`BISECT_LOG` 六探针全部不存在；`git ls-files -u` 0 行；`git stash list` 空；`git remote -v` 空（本仓库无远端）。
- 本轮改动文件全量实测（bytes／LF／CR／sha256 前 16 位大写）：

| 文件 | 现盘 | HEAD |
|---|---|---|
| `TODO.md` | 664,711／2,172／CR 0／`2500B001E8416CB4` | 660,720／2,171／CR 0／`202C17CF82CFBC8F` |
| `CHANGELOG_AI.md` | 1,269,861／6,772／CR 0／`1194C77C82B3AD81` | 1,265,954／6,770／CR 0／`8CF506F2B4E172CA` |
| `PROJECT_CONTEXT.md` | 810,112／6,190／CR 0／`FEF1B05E95845BE9` | 808,650／6,189／CR 0／`99A2707CF62A4C22` |
| `SOURCE_MANIFEST.sha256` | 77,065／711／CR 711／`B1676357809470C1` | 76,244／710／CR 0／`D8CA05A2104D6D53` |
| `src/app/ui/app.js` | 408,924／8,405／CR 0／`5B6158A44C18911D` | 408,345／8,395／CR 0／`1C952E065668A981` |
| `src/tests/test_ui_cover_source_rejection.js` | 4,370／86／CR 0／`7CFDD15045C64D12` | 不在 HEAD（本轮新增） |

- 计数现状（磁盘复算）：`TODO.md` 行首 `- [ ]` **15** 条＝桶归属声明行之后 13 条长期观察＋声明之前 2 条代码桶深读债；`docs/external-acceptance.md` 设备段开放 **28**／已收口 **17**；需决策桶 **0**。`SOURCE_MANIFEST.sha256` **711 行**且 711 行互不重复（本轮 +1＝新增测试文件）。
- 一条清单外的真实差异：清单**盘上副本是 CRLF**（711 CR／711 LF），而 HEAD 版本是 LF（710 行、CR 0）。`.gitattributes` 的 `* text=auto  eol=lf` 让 git 在入库时归一，所以 `git diff` 只看内容；本轮不擅自改动刷新器，只把它记为已知现象（第六节说明它如何一度把抽查误导成 100% 失效）。
- 运行时：`v24.19.0`；门禁 Python `Python 3.14.7`。

## 二、缺陷与修法（逐 hunk）

### hunk 1 · `src/app/ui/app.js:1120-1141` `coverUrl`

改前（HEAD）：

```javascript
  if (typeof source !== "string" || !source.trim() || source.length > 4096) return "";
  try {
    const url = new URL(mediaUrl(source), window.location.href);
    if (!["http:", "https:"].includes(url.protocol)) return "";
```

改后（现盘 `:1123-1132`）：

```javascript
  if (typeof source !== "string" || !source.trim() || source.length > 4096) return "";
  // ``mediaUrl`` answers a rejected scheme with "", and ``new URL("", base)`` does
  // not throw: it resolves to the base document. Re-parsing that empty answer
  // would hand the caller the application\'s own URL as if it were usable
  // artwork, so an empty answer has to stop here instead of being resolved.
  const absolute = mediaUrl(source);
  if (!absolute) return "";
  try {
    const url = new URL(absolute, window.location.href);
    if (!["http:", "https:"].includes(url.protocol)) return "";
```

**机理**：`mediaUrl`（`:1109`）对不在允许名单内的 scheme 回答空字符串＝「这张图不可用」；`new URL("", base)` 按 WHATWG 规则**不抛**，而是解析成基址自身。把前者当作后者的输入，等于把「不可用」反转成「一个指向应用自己的页面的真值地址」，随后 `url.protocol` 变成 `http:`、`size` 参数被追加、`url.href` 返回给调用方。

**危害为何不是「显示降级」**：`item.cover_url` 的写点实测 **5 处**（`hydrateVisibleTrackCovers` 等 metadata 回投档），每处前两行都带 `!item.cover_url` 守卫。一个真值垃圾因此会同时做两件事：把该行钉成坏图，以及永久压制后续任何合法封面。

**取舍**：只在这两个 helper 里终止被拒答案，**不改** `mediaUrl` 本体的返回契约（它另有调用点，把「空」换成 `null` 或改抛异常都是扩大改动面），**不新增**第二份 scheme 名单（名单已有单一权威）。

### hunk 2 · `src/app/ui/app.js:1142-1154` `usableCoverSource`

同一处缺陷的第二例（现盘 `:1144-1149`）：新增两行解释注释＋`const absolute = mediaUrl(value.trim());`＋`if (!absolute) return "";`，并把 `new URL(mediaUrl(value.trim()), window.location.href)` 换成 `new URL(absolute, window.location.href)`。该 helper 是 metadata 回投档写 `item.cover_url`/`item.cover_thumbnail_url` 前的最后一道判定，因此它与 `coverUrl` 必须同形；两例分开修、分开被变异格 M1/M2 判别。

## 三、判别测试（新增文件逐段）

`src/tests/test_ui_cover_source_rejection.js`（4,370 B／87 行），三段结构：

1. **夹具**：用 `region()` 从 `app.js` 里切出 `mediaUrl`／`coverUrl`／`usableCoverSource` 三段函数体，`vm.runInNewContext` 装载，并**显式注入宿主 `URL`** 与一个固定文档地址。不注入 `URL` 时每次解析都掉进 catch，10 组拒绝断言会以完全错误的理由通过——这是本轮唯一一处「测试本身能造假」的地方，故写进注释。
2. **断言**：5 种被拒 scheme（`file:`／`javascript:`／`data:`／`ftp:`／`blob:`）× 2 条字段路径（`cover_url` 与 `cover_thumbnail_url`）＝10 组等值断言；另有 2 组反向断言钉住「拒绝结果不得等于文档地址」；6 组正向对照保证拒绝没有扩大到可用路径（相对路径补全成 `http://nas.local:8000/...`、首尾空白被吃掉、`size>0` 追加参数、`size=0` 不追加、空串、空对象）。
3. **源码级接线断言**：逐行扫 `item.cover_url = ` 赋值，要求前两行内出现 `!item.cover_url`，并要求此类写点数 **≥ 5**（实测恰为 5）。「守卫在不在」与「helper 返回值对不对」是两件事，只断言后者会漏掉整条压制路径。

## 四、变异证明（仓库外副本，控制组先绿）

副本口径：`git clone --no-hardlinks` 到仓库外，随后 `git remote remove origin`，HEAD `e566306`。控制组＝主仓与副本各跑一遍全量 JS 回归，**76 文件 0 失败先绿**，之后才逐格注入变异。

| 格 | 变异 | 结果 |
|---|---|---|
| M1 | 摘掉 `coverUrl` 的空答早退 | KILLED |
| M2 | 摘掉 `usableCoverSource` 的同款早退 | KILLED |
| M3 | 让 `mediaUrl` 不再拒绝非法 scheme | KILLED |
| M4 | 把 `coverUrl` 的早退条件反向 | KILLED |
| M5 | 让 `usableCoverSource` 恒返回空（拒绝扩大成不可用） | KILLED |
| M6 | 让某个 metadata 写点丢掉 `!item.cover_url` 守卫 | KILLED（新增接线断言的判别力证据） |
| M7 | 让缩略图字段按错的 size 选取 | KILLED |
| M8 | 让 size=512 时不再追加 `size` 参数 | KILLED |

八格全部由新测试判红，跑完还原 pristine（与主仓 `app.js` 逐字节相同后复核）。

## 五、当轮证伪（4 项，一律不得记作发现）

1. **`state.seeking` 不会永久卡 true**：`commitSeek` 的复位分支先于可疑的提前返回执行，拖拽结束后标志必然回落。
2. **`applyGroupArtwork` 不会经 `failed` 分支无限递归**：`failed` 处理先 `removeAttribute`，二次进入即止。
3. **`prepareLocalGroupArtwork` 的帧回调校验不构成缺陷**：`load`/`error` 监听器仍在位，回调路径有终止条件。
4. **封面字段的二次绝对化不构成缺陷**：`absoluteAppUrl` 幂等，二次输入同一值得同一结果。

## 六、逐文件抽查：12/12 MISSING 定性为**抽查脚本缺陷**

- 现象：本轮第一次抽查 12 个文件全部报 MISSING。根因＝清单**盘上是 CRLF**，脚本以 `newline=""` 读原文再按换行切分，回车残留在每行路径尾部，于是每次都在找一个不存在的文件名。
- 处理：改用 `splitlines()` 后 12/12 MATCH；顺手把抽查从 12 条升级为**全表 711 条逐文件复算**：missing=0、hash_mismatch=0、行数与刷新器一致。
- 教训（写进 CHANGELOG）：清单的行结束符与被哈希内容无关，但读清单的手艺必须与它一致，否则一份好清单会被报成 100% 失效，而下一步通常是「重新生成清单」——那才是真正会掩盖问题的动作。

## 七、深读覆盖按磁盘重算（不改写历史登记值）

- 锚定 `^(?:async )?function NAME(` 实测 `app.js` **463** 个命名函数；三份根文档以反引号点名过 **79** 个。
- 播放面簇（`nowplay|cover|artwork|progress|seek|elapsed|duration|transport|playing|thumbnail`，不区分大小写）命中 **31** 个：已点名 14、本轮新读 **17**（`applyGroupArtwork`、`commitSeek`、`coverUrl`、`externalArtworkUrl`、`hydrateVisibleTrackCovers`、`isRecoverableFilenameMetadata`、`loadGroupArtwork`、`localIsPlayingNow`、`needsVisibleTrackCoverHydration`、`prepareLocalGroupArtwork`、`preserveTrackCoverNode`、`previewSeek`、`recoverUnavailablePlaybackTarget`、`resetPlaybackProgress`、`retryCurrentTrackMetadataAfterRecovery`、`scanProgressText`、`usableCoverSource`）。
- 于是浅读面条的分子 **31 → 48**；分母保持该条登记值 **381** 不动（`docs/REVIEW_ROUND_DISCIPLINE.md` 第五节：禁止改写历史数字，实测 463 只作为可复算证据登记）。

## 八、门禁与清单

- 终跑日志 `artifacts/offline-20260922-round230.log`（435,409 B，晚于本轮全部文件写入）：
  Ran 行 `Ran 2555 tests in 124.589s`；结论行 `OK (skipped=2)`；结论行之后的 Node 回归输出 **76** 行（含 `Cover source rejection regression checks passed.`，即新测试已进入发现式跑批）；`git diff --check` 未触发异常；解析 tools 下 9 个 `.ps1` 无语法错；整条命令退出码 **0**。
- 上轮对照：round229 为 `Ran 2555 tests`／`OK (skipped=2)`／Node 输出 76 行——本轮 Node 行数同为 76，因为新测试替换进同一发现式集合（该集合本轮实测 76 个 `test_*.js`）。
- 清单刷新：`tools/update_source_manifest.ps1` 刷新为 711 条并幂等复跑；逐文件抽查见第六节；`src/app/ui/app.js` 现盘 sha256 前 16 位 `5B6158A44C18911D` 与清单逐字相符，新测试 `7CFDD15045C64D12` 同。
- 控制组另测：`node --check src/app/ui/app.js` 退出码 0；主仓 76 个 JS 回归 0 失败；四枚记账守卫（`test_source_manifest`／`test_ledger_evidence_cards`／`test_device_todos_migrated`／`test_change_record`）合并跑 `Ran 44 OK`——三份根文档 prepend 之后再跑一次仍 `Ran 44 OK`。

## 九、记账口径

- **净关闭 0 条、新立 0 条**：本轮改的是 `app.js` 与测试，未使任何既有代码待办满足其关闭判据；按第二节如实记 0，反增长约束读作 0 ≤ 0。
- 浅读面条（app.js 符号计数条）：分子 31 → 48，**仍开放**，判据是 381 个登记符号面全部读完。
- 欠读清单条：本轮**不降反升**，20,982 → **20,992** 行，上升 10 行＝修复给 `app.js` 净增 10 行；无面出局。四分量实测＝`app.css` 1,528＋`cover_cache.py` 1,364＋`app.js` 8,405＋已跟踪 Android `.java` 43 文件 9,695。
- 桶计数一律未改动：代码 2／设备·外部 0（另册 28 开放、17 收口）／需决策 0／长期观察 13。终止条件 (3) 成立，(1)(2)(4) 未成立。

## 十、需要负责人裁定的事项（本 packet 不代答；负责人已授权「按建议执行」者另记）

1. 是否允许在**下一轮**把浅读面条的关闭判据从「381 个登记符号面全部读完」改为「按磁盘实测 463 个命名函数全部点名」——两者差 82 个面，改判据属于放宽终止条件，须负责人明示。建议：**不改**，继续按登记值读，读满 381 即关闭，剩余 82 个作为该条关闭后的新一轮清点。
2. 是否允许 `app.js` 的欠读分量按「修复净增行」上浮登记值（本轮 +10）。建议：**允许**，如实登记为不降反升，禁止为了让曲线好看而抹掉新增行。
3. 设备段 28 条开放项中，第二档真机动词（安装控制点、改设备软件栈）是否需要逐条再批。建议：**需要**，白名单只覆盖第一档只读＋播放＋取日志。
4. `SOURCE_MANIFEST.sha256` 盘上 CRLF 是否要在刷新器里显式归一为 LF。建议：**暂不改**，入库由 `.gitattributes` 归一，改动刷新器会让整表重写、掩盖真实变更；仅把「读清单必须 splitlines()」写进抽查手艺。

## 十一、负责人裁定回填（2026-09-22 · 第十节逐条落定）

负责人本轮明示：「需要我裁定的按你的建议执行」。故第十节四条按其**建议值**登记为已采纳；第十节原文不改一字，以保留裁定前的原始表述。

1. 浅读面条的关闭判据：**不改**。分母仍为该条登记值 **381** 个符号面，读满即关闭；磁盘实测多出的 **82** 个命名函数面不提前并入分母、也不提前放水，留作该条关闭后的新一轮清点。
2. `app.js` 欠读分量按「修复净增行」上浮：**允许**。本轮 8,395 → **8,405** 如实登记为不降反升；禁止为让曲线好看而抹掉修复新增的行。
3. 设备段 28 条开放项中的第二档真机动词（安装控制点、改设备软件栈）：**需要逐条再批**。白名单只覆盖第一档（只读探测＋本机播放＋取日志），第二档在执行前必须单独取得负责人同意。
4. `SOURCE_MANIFEST.sha256` 盘上 CRLF：**暂不改刷新器**。入库归一交给 `.gitattributes`；本轮起把「读清单必须用 `splitlines()`」固定为抽查手艺，防止一份好清单被读成 100% 失效。

以上四条均为**口径裁定**，本轮回填未据此改动任何代码、清单或根文档；记账口径不变：**净关闭 0 条、新立 0 条**。
