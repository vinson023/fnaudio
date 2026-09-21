# fnAudio · R126 修改审核对照（接管取证 + 逐 hunk）

生成时间：2026-09-20（Asia/Shanghai）。仓库 `C:\path\to\fnAudio`，分支 `main`。
本文件是**给人逐 hunk 审核的交付物**，不是文件清单；每个 hunk 都带磁盘证据、具名杀手测试与变异编号。
本文件本身不入库（与 `artifacts/`、`music/`、`_external/` 同批未跟踪件）。

---

## 0 接管取证（当场实测，不引用任何历史快照）

| 项 | 磁盘读数 |
| --- | --- |
| 起始 HEAD（接管时） | `a295d08` chore: record R125 closure |
| 未完成 Git 状态 | 无 merge / rebase / cherry-pick；无 remote；分支 `main` |
| 接管时已跟踪改动 | 8 个（`TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md`、`SOURCE_MANIFEST.sha256`、`src/app/server/dlna/{profiles,control_point,media_server}.py`、`src/app/server/playback_targets_presentation.py`）+ 1 个未跟踪新文件 `src/tests/test_dlna_dsd_capability.py` |
| 本轮终跑门禁 | `artifacts/offline-20260920-round192.log`（417975 字节／2603 行／纯 ASCII 无 BOM，mtime 23:00:27 晚于全部文档编辑）⇒ Python `Ran 2461 tests in 111.717s`／`OK (skipped=2)`，门禁退出码 0 |
| 清单 | `SOURCE_MANIFEST.sha256` **706 条**；`tools/takeover_forensics.py --full` ⇒ `lists 706 / drift 0 / stale 0 / unlisted 0`。清单口径只覆盖 `src/`（626 条）与 `android-client/`（80 条），三份根文档按既有口径**不在**清单内，所以抽查对象一律是这两个前缀下的文件 |
| 定向复跑（提交前） | 仓库内 `test_dlna*.py` **224 项 OK**；`test_change_record test_source_hygiene test_source_manifest test_takeover_forensics` **24 项 OK**；JS 74 文件 0 失败（必须在 `src` 目录下按 FullName 跑，在仓库根或 `src\tests` 跑会假失败 48 条） |
| 提交后仓库外复验 | clone 副本（HEAD `972f733`，5 文件与仓库逐文件 sha 全等）控制组 `Ran 224 OK`；V1～V11 **全灭／0 存活／0 坏锚点**，逐条杀手名单见 §6；副本还原后 `git status --porcelain -uno` 空并已删除 |
| `git status --porcelain -uno` | 两笔提交之后**空** |
| 半截文件 | `.new` / `.orig` / `.rej` 递归扫描命中 **2** 处，均在未跟踪的 `_external/` 外部 Go 依赖内（`modernc.org/libc@v1.67.6/surface.new` 与 `gomodcache-clean` 同名件），**非本轮产物** |

本轮落地的两笔提交（逐文件显式 pathspec，未用 `git add -A`，未碰 `.gitignore`）：

1. `8ad5221` feat(dlna): make a failed DSD capability probe read as silence, not refusal
   ⇒ 6 files，+350 / -24：`SOURCE_MANIFEST.sha256`、`src/app/server/dlna/{profiles,control_point,media_server}.py`、`src/app/server/playback_targets_presentation.py`、新增 `src/tests/test_dlna_dsd_capability.py`
   清单增量与本轮代码改动**精确自洽**：新增 1 条（新测试）、重算 4 条（4 个被改源文件）、删除 0 条。
2. `972f733` chore: record R126 closure ⇒ `TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md`（3 files，+8 / -1）

`autocrlf=true` 使 `git add` 时对 `SOURCE_MANIFEST.sha256` 打印 CRLF→LF 提示；实测 HEAD 与暂存 blob 的 CRLF 计数均为 **0**，与历史各轮一致，非本轮新增异常。

### 0.1 四桶复算（按行首勾选标记 + 节标题文本锚定；行号只是当轮线索）

`TODO.md` 盘上 **2214** 内容行（末换行不另计），`- [ ] ` 行首前缀 **73** 条，零缩进 `- [x] ` **1468** 条，CRLF **0**。73 条的真实归属：

| 桶 | 条数 | 锚定方式（节标题 + 当轮行号） |
| --- | --- | --- |
| 可离线代码项 | **15** | 主表 13（L40、L41、L91、L103、L105、L107、L114、L118、L121、L142、L152、L156、L160）+ L548（持续审查未完成范围）+ L796（外部验收伞） |
| 设备/外部验收项 | **44** | L813..L845（宿主 MediaSession 10）+ L976..L1176（Android 等价 MediaSession 6）+ L1828..L1830（P2 部署与外部系统验收 3）+ L1839（P3 可维护性清理 1）+ L1844..L1868（P0 外部验收 24） |
| 需项目负责人决策 | **1** | L1880（R73 `allow_disk=False` 的取舍，负责人已提供含无标签音频的样本条件） |
| 台账/历史叙述项 | **13** | L2073..L2155（`# 2026-09-01 飞牛 APP 私有播放会话（研究结论）` 起的**文件尾部连续流水段**，含其后 `# 2026-09-04 持续目标追加` 等节） |

=> **73 = 15 + 44 + 1 + 13**。

本轮把复算规则从"硬编码行号"换成"节标题锚定"，并登记两条取证口径，防止后人再算歪：

1. **台账区是粘性尾部区**：一旦命中 `# 2026-09-01 飞牛 APP 私有播放会话（研究结论）` 这个一级标题，其后**所有**节（含 `# 2026-09-04 持续目标追加`）都属台账。把它当单个一级区段闭合会让 L2155 掉进代码桶，得出 `16 + 44 + 1 + 12`。
2. **已关闭计数只统计零缩进 `- [x] `**：允许前导空白会多吞 1 条既有的缩进子项（编辑前后都各 1 条，与本轮无关），得 1467／1469；仓库口径是 1466／1468。开放项两种口径同为 74／73，所以只有"已关闭"数会漂移。

历史计数快照**并存、不合并、不覆盖**：`155=64+82+9`、`115=51+43+8+13`、`77=18+44+2+13`、`76=18+44+1+13`、`74=16+44+1+13`、`73=15+44+1+13`。差异来源是逐轮关闭与桶重划，不是同一时刻的两个口径。

设备段核对：本轮把 `git show HEAD:TODO.md` 与工作树做 `difflib` 逐行比对，差异**只有 2 处**（插入本轮记录、原 L176 行翻转为已关闭），P0/P2/P3/宿主 MediaSession/Android 五段正文**一字未改**；新立开放项 **0** 条。

---

## T1 `src/app/server/dlna/profiles.py` —— 三态与唯一谓词（99 内容行／3865 字节）

### T1.1 L12-14：给"未知"一个合法名字

```python
# The native-DSD fact has exactly three states.  Collapsing "we never managed to
# ask" into "the renderer refused" is what made the push gate and the transport
# target list disagree, so the collapse is now impossible by construction.
DSD_CAPABILITY_SUPPORTED = "supported"
DSD_CAPABILITY_UNSUPPORTED = "unsupported"
DSD_CAPABILITY_UNKNOWN = "unknown"
```

审核要点：注释把**病因**写在常量旁边，而不是写在调用点。此前没有 unknown 这个取值，所以每个调用点各自发明一种"未知"（缺键、False、非 bool），三处互不兼容。

### T1.2 L26-41：`_dsd_state_from()` —— 键的存在与否就是语义

```python
def _dsd_state_from(record: Dict[str, Any]) -> str:
    """Read one capability record without inventing a claim it does not make.

    A present value is a claim, and only ``True`` claims support; a malformed
    value therefore counts as "not supported" rather than as silence, which is
    the conservative reading the push gate needs.  An absent key is silence.
    """
    try:
        has_claim = "supports_dsd" in record
        value = record.get("supports_dsd")
    except Exception:
        return DSD_CAPABILITY_UNKNOWN
    if not has_claim:
        return DSD_CAPABILITY_UNKNOWN
    return DSD_CAPABILITY_SUPPORTED if value is True else DSD_CAPABILITY_UNSUPPORTED
```

审核要点：判据是**键是否存在**，不是取值真值。`"supports_dsd": None` 这类"写了但没表态"仍然是 unsupported——因为它是一次明确写入；只有整键缺席才是 unknown。这条区分是 V8（静默当拒绝）与 V9（真值替代三态比较）的靶子。

### T1.3 L43-69：`dsd_capability_state()` —— 一个事实一个形状优先级

```python
def dsd_capability_state(source: Any) -> str:
    """The single predicate for "does this device do source DSD".

    ``source`` is either a device mapping, whose authoritative record is the
    discovery probe nested in ``capabilities.protocol_info``, or a bare
    ``protocol_info`` mapping as produced by `device_protocol_info()`.  The
    probe record wins over the flat device field whenever both are present, so
    the derived display field can never outvote the evidence it came from.
    """
    if not isinstance(source, dict):
        return DSD_CAPABILITY_UNKNOWN
    try:
        capabilities = source.get("capabilities")
    except Exception:
        return DSD_CAPABILITY_UNKNOWN
    if isinstance(capabilities, dict):
        try:
            probed = "protocol_info" in capabilities
            protocol = capabilities.get("protocol_info")
        except Exception:
            return DSD_CAPABILITY_UNKNOWN
        if probed:
            if not isinstance(protocol, dict):
                return DSD_CAPABILITY_UNKNOWN
            return _dsd_state_from(protocol)
    return _dsd_state_from(source)
```

审核要点：`capabilities` 是 dict 且**含** `protocol_info` 键时，以嵌套探测记录为准，扁平派生字段**不参与投票**；这就是杀手测试 `test_the_probe_record_outranks_the_derived_display_field` 的锚点（V4 扁平压过嵌套即在此处翻车）。

### T1.4 L71-79：`device_supports_native_dsd()` 降级为纯显示视图

```python
def device_supports_native_dsd(device: Any) -> bool:
    """Conservative bool view of :func:`dsd_capability_state`.

    Only a probe that confirmed support lights this up.  Unknown and refused
    both render as False, which is what a display surface needs; the push gate
    reads the three-state predicate instead so a missing probe cannot be turned
    into a refusal.
    """
    return dsd_capability_state(device) == DSD_CAPABILITY_SUPPORTED
```

审核要点：签名从 `Dict[str, Any]` 放宽为 `Any`——因为它现在只是委托，非 dict 由谓词兜成 unknown，不再在这里 `except` 出一个 False。

---

## T2 `src/app/server/dlna/control_point.py` —— 失败壳不再谎报（699 行／29046 字节）

### T2.1 L290-295：无 control 时不再写 `supports_dsd`

```python
def device_protocol_info(control):
    # A missing or failing ConnectionManager is silence, not a refusal: the
    # record deliberately carries no `supports_dsd` key so `unknown` cannot be
    # read back as "this renderer does not do DSD".
    if not control:
        return {"source": [], "sink": [], "mime_types": []}
```

改前：`return {"source": [], "sink": [], "mime_types": [], "supports_dsd": False}`。
这是本轮唯一的**真 bug**：一次"没问到"被写成"设备回答说不支持"。

### T2.2 L317：`GetProtocolInfo` 抛异常时同样不再写该键

```python
    except Exception:
        return {"source": [], "sink": [], "mime_types": []}
```

改前同上带 `"supports_dsd": False`。两处失败壳合起来构成 V2/V3 的靶面（任一处恢复写 False 即被杀）。

### T2.3 L320-321：`device_supports_dsd()` 交棒谓词

```python
def device_supports_dsd(control):
    return device_supports_native_dsd(device_protocol_info(control))
```

改前是本地手搓 `value if isinstance(value, bool) else False`。删掉后本文件对该键的读取路径为 0，由 `test_the_predicate_is_the_only_reader_in_the_package` 守住（V7 拆委托即死）。

### T2.4 L494-500：扁平字段变成"派生缓存"

```python
            device["capabilities"] = probe_device_capabilities(device)
            # The flat field is a display cache derived from the probe through the
            # same predicate the push gate uses, so it can never outvote or drift
            # from the record it was computed from.
            device["supports_dsd"] = device_supports_native_dsd(device)
```

改前两行：`raw_supports_dsd = (...protocol_info or {}).get("supports_dsd")` + `isinstance(..., bool)` 兜 False——即第三种口径（派生而非委托）。

### T2.5 L502-505：发现异常路径删掉一行写 False

```python
        except Exception:
            device["name"] = "UPnP 播放器"
            device["online"] = False
            devices.append(device)
```

改前此处还有 `device["supports_dsd"] = False`。删掉后该设备记录里没有 DSD 主张，谓词读回 unknown ⇒ 推流放行、显示为 False。V6 的靶点。

---

## T3 `src/app/server/dlna/media_server.py` —— 门读三态（231 行／8540 字节）

### T3.1 L10：import 三态与谓词

```python
from .profiles import DSD_CAPABILITY_UNSUPPORTED, dsd_capability_state, protocol_info
```

### T3.2 L175-185：等值比较取代真值判断

```python
    # ... An unknown probe stays permissive so older
    # renderers can still be tried and diagnosed by the transport layer, which
    # is why the gate reads the three-state predicate instead of testing the
    # probe record for truthiness: a failed ConnectionManager request carries no
    # DSD claim at all, and silence must not be reported as a refusal.
    if item.get("is_dsd"):
        if dsd_capability_state(device) == DSD_CAPABILITY_UNSUPPORTED:
            return False, "设备不支持源码 DSD，已阻止 PCM 转码"
```

改前三行手工展开 `capabilities`/`protocol_info`/`isinstance bool`，门写作 `if protocol and not supports_dsd`。
审核要点：
- 旧门的 `protocol` 真值判断意味着"**只要有协议记录且没确认支持就拦**"，与紧邻注释承诺的"空/未知探测保持放行"直接矛盾——本轮把代码改成与注释一致，而不是把注释改成与代码一致。
- **拦截文案逐字未改**（`设备不支持源码 DSD，已阻止 PCM 转码`），所以任何按文案断言的既有测试语义不变。
- 门只读谓词，本文件不再出现 `"supports_dsd"` 字面量，由 `test_only_the_predicate_reads_the_capability_key` 强制。

---

## T4 `src/app/server/playback_targets_presentation.py` —— 目标列表同源于谓词（157 行／5569 字节）

### T4.1 L9：跨包 import

```python
from dlna.profiles import device_supports_native_dsd
```

### T4.2 L141-143：`native_dsd` 不再读裸字段

```python
        # One predicate for one fact: the transport list lights native DSD only on
        # the same probe record the push gate refuses on.
        target_caps["native_dsd"] = device_supports_native_dsd(device)
```

改前 `device.get("supports_dsd") is True`。这一处是"同一事实第三种形状"的最后一个消费者；V5 的靶点。

---

## T5 新增 `src/tests/test_dlna_dsd_capability.py`（263 内容行／11427 字节／13 项）

### T5.1 L52-109：`TRUTH_TABLE` —— 八行形状 × 三列结论同断言

每行同时钉住 **state / 推流是否放行 / 显示布尔**，例如：

```python
    (
        "空设备：什么都没探测过",
        {},
        DSD_CAPABILITY_UNKNOWN,
        True,
        False,
    ),
    (
        "扁平字段确认不支持",
        {"supports_dsd": False},
        DSD_CAPABILITY_UNSUPPORTED,
        False,
        False,
    ),
```

`_push()`（L37-48）注入 `control_url` 后用 `mock.patch` **真实调用 `soap_push()`**，只 mock 网络出口 `soap_request`；因此"放行"断言的是 `result[0] is True` **且** `request.called`，"拦截"断言的是 `result[0] is False`、文案含"不支持源码 DSD" **且** `request.called is False`。拦截路径必须证明请求**没发出去**，否则门形同虚设。

具名杀手测试（`NativeDsdTruthTableTests` 8 项）：
`test_every_shape_maps_to_one_state_one_gate_and_one_display`、`test_non_dsd_sources_never_reach_the_gate`、`test_a_failed_probe_is_silence_and_not_a_refusal`、`test_a_raising_probe_also_reports_silence`、`test_a_refusal_claimed_as_none_is_still_a_refusal`、`test_the_probe_record_outranks_the_derived_display_field`、`test_the_push_gate_and_the_target_list_share_one_predicate`、`test_garbage_inputs_cannot_be_read_as_support`。

### T5.2 L204-264：源级接线守卫 —— 按行白名单，不是整文件 substring 黑名单

`test_control_point_only_writes_the_field_never_reads_it_back` 只放行四类行：唯一派生写（`device["supports_dsd"] = device_supports_native_dsd(device)`）、探测记录里的真写入（`"supports_dsd": bool(...)` 成功路径）、`def device_supports_dsd` 定义行、以及注释行。任何新增的**读取**该键的行都会被判违规。

审核要点（本轮立的新规则，已写进 `PROJECT_CONTEXT.md`）：整文件 substring 黑名单会误杀合法写入，逼人放宽守卫；按行白名单则默认拒绝新读取者，同时允许成功路径继续生产该事实。`test_only_the_predicate_reads_the_capability_key` 与 `test_the_predicate_is_the_only_reader_in_the_package` 从两端夹住：消费侧 0 次出现键名，包内读取者只有谓词。

---

## 6 仓库外变异矩阵（提交后重跑，逐条实录）

副本 `%TEMP%\fnaudio-r126-reverify`：由 `git clone` 自 `C:\path\to\fnAudio`，移除 origin，HEAD `972f733`（**本轮两笔提交之后**的状态），5 个相关文件与仓库**逐文件 sha256 全等（0 不一致）**后才开跑。每个变异跑完立刻按 pristine 文本还原，全部跑完后副本 `git status --porcelain -uno` 为**空**，随后删除。

- 控制组：`python -B -m unittest discover -s tests -p "test_dlna*.py"` ⇒ `Ran 224 tests in 3.090s` / `OK`。
- **V1～V11 全部被杀：0 存活、0 坏锚点**（施加前先断言锚点字符串在目标文件中恰好出现 1 次，避免"变异没生效"式假绿）。

| 编号 | 变异内容（施加于已提交代码） | 套件计数 | 指名杀手用例 |
| --- | --- | --- | --- |
| V1 | `device_supports_native_dsd()` 退回本地布尔强制、不再委托谓词 | 4 failures | `test_every_shape_maps_to_one_state_one_gate_and_one_display`、`test_the_bool_view_delegates_instead_of_coercing_on_its_own`、`test_the_probe_record_outranks_the_derived_display_field`、`test_the_push_gate_and_the_target_list_share_one_predicate` |
| V2 | 无 control 失败壳恢复写 `"supports_dsd": False` | 3 failures | `test_a_failed_probe_is_silence_and_not_a_refusal`、`test_control_point_only_writes_the_field_never_reads_it_back`、`test_the_probe_shells_stop_reporting_a_refusal_they_never_observed` |
| V3 | `GetProtocolInfo` 异常失败壳恢复写 `"supports_dsd": False` | 3 failures | `test_a_raising_probe_also_reports_silence`、`test_control_point_only_writes_the_field_never_reads_it_back`、`test_the_probe_shells_stop_reporting_a_refusal_they_never_observed` |
| V4 | 扁平派生字段压过嵌套探测记录 | 1 failure | `test_the_probe_record_outranks_the_derived_display_field` |
| V5 | 目标列表读回裸 `device["supports_dsd"]` | 2 failures | `test_only_the_predicate_reads_the_capability_key`、`test_the_push_gate_and_the_target_list_share_one_predicate` |
| V6 | 发现异常路径恢复 `device["supports_dsd"] = False` | 2 failures | `test_control_point_only_writes_the_field_never_reads_it_back`、`test_the_probe_shells_stop_reporting_a_refusal_they_never_observed` |
| V7 | `device_supports_dsd()` 拆掉委托、本地手搓布尔兜底 | 1 failure | `test_control_point_only_writes_the_field_never_reads_it_back` |
| V8 | 把「键不存在」读成拒绝（unknown 改判 unsupported） | 8 failures（4 用例乘 subTest 逐形状） | `test_every_shape_maps_to_one_state_one_gate_and_one_display`、`test_a_failed_probe_is_silence_and_not_a_refusal`、`test_a_raising_probe_also_reports_silence`、`test_the_push_gate_and_the_target_list_share_one_predicate` |
| V9 | 推流门退回真值判断（有协议记录且未确认支持即拦） | 10 failures + 2 errors | `test_every_shape_maps_to_one_state_one_gate_and_one_display`、`test_a_failed_probe_is_silence_and_not_a_refusal`、`test_a_raising_probe_also_reports_silence`、`test_a_refusal_claimed_as_none_is_still_a_refusal`、`test_only_the_predicate_reads_the_capability_key`、`test_the_push_gate_and_the_target_list_share_one_predicate` |
| V10 | 发现期派生写退化为独立布尔兜底（绕过谓词） | 2 failures | `test_control_point_only_writes_the_field_never_reads_it_back` |
| V11 | 把 `"supports_dsd": None` 当未知放行（而非拒绝） | 2 failures | `test_a_refusal_claimed_as_none_is_still_a_refusal` |

对照说明：交接口径里的上一次矩阵跑在**编辑前的工作树副本**（`fnaudio-r126-copy`）上，结论同为 V1～V11 全灭；本次是在**已提交代码**上重跑，并首次把逐条杀手用例名留档。两次结论一致，且本次基线更强（变异对象即入库结果）。V9 的 2 个 error 来自源级守卫：门一旦不再调用谓词，`media_server.py` 重新出现裸键读取，接线测试直接报错而非仅断言失败。

---
## 7 行为不变性与"不需要真机证据"的理由

| 输入形状 | 改前（放行／显示） | 改后（放行／显示） |
| --- | --- | --- |
| `{"supports_dsd": True}` | 放行／True | 放行／True |
| `{"supports_dsd": False}` | 拦／False | 拦／False |
| 嵌套探测记录 True／False | 放行·拦／True·False | 同上 |
| `{"supports_dsd": "true"}` 等非布尔 | 拦／False | 拦／False |
| `{}`（设备完全没有 `capabilities`） | 放行／False | 放行／False（不变） |
| 探测失败空壳 | **拦** | 放行／False |

唯一变化就是最后一行：把一次网络静默从"误拦"改回"放行"。这是**放宽误拦、不收窄能力语义**，没有新增任何"设备支持 DSD"的断言，因此本轮**不需要真机证据**；"哪些真实渲染器会落 unknown"属既有 P0 外部验收段，**并入不新立**。

---

## 8 剩余量（提交后磁盘实测）

- 开放 **73** ＝ 可离线代码 **15** ＋ 设备/外部 **44** ＋ 需产品决策 **1** ＋ 台账 **13**；已关闭 **1468**。
- 距旧目标四项终止条件还差 **16** 条（代码 15 ＋ 决策 L1880）。
- 代码桶 15 条的可离线空间已极小：L40／L41 需真机；L91 是范围读数；L103／L118 已判不做或需配置决策；L105／L107 歌词缓存需配置面决策；L114／L142 需真机或性能取证；L121 CUE 语义需样本；L152／L156／L160 需真机；L548 范围伞；L796 外部验收伞。
- 决策 L1880：负责人已给出样本条件（`C:\path\to\fnAudio\music` 内一首无标签样本歌曲），下一轮可在测试机取证后收口。
- 已完成 36 轮（R126）；`maxGoalRounds = 72` 不构成终止理由。
