# S0-F39 统一选目标入口（Task Spec）

切片编号：S0-F39
日期：2026-11-17
状态：待执行
配套：`S0F22_CHANNEL_HEALING_TASK_SPEC`（引导神力）、`S0F23_CHANNEL_CONTROL_TASK_SPEC`（镇服敌人）、
`S0F20_COMBAT_START_TASK_SPEC`（回合与先攻）

## 1. 执行纪律与范围锁定

1. 本切片只做**选目标**这一件事：谁可以被选、可以选几个、选完怎么提交。
   不碰伤害、不碰豁免、不碰条件结算。
2. 本切片**不引入几何范围**。场地仍是 1D 剧场模式（`position_mode: "theater"`，位置为标量、
   距离为差值）；按位置圈人的区域效应留到战术地图切片。
3. 本切片**不改前端渲染**。前端只按新的投影字段调整“要不要选、选几个、哪些不能选”，
   多选控件本身复用既有法术多选的结构。
4. 术语：
   - **目标形状**：一条能力/法术允许选什么、选几个的声明。
   - **候选集**：服务端按当前战场算出的“可以选”的目标列表。
   - **上界**：可以选的最大数量，可能由属性算出。
5. **裁决（2026-11-17，本切片的硬前提）**：数量是**上界而非必须选满**。玩家可以少选，
   但至少要选一个。理由：战斗里经常凑不齐那么多合法目标，强制选满会让能力在多数场合
   直接不可用。
   - 这条覆盖 `S0F23` 中“恰好等于魅力调整值”的原文口径，该任务书 §4 需同步修订，
     实现侧 `_validate_abjure_foes` 的 `!=` 判断改为上界判断。
   - 一切“恰好 N”的历史表述按“最多 N、至少 1”执行。

## 2. 官方英文关键原文与页码

> **Abjure Foes.** As a Magic action, you can expend one use of your Channel Divinity to
> target a number of creatures equal to your Charisma modifier (minimum of one) that you
> can see within 60 feet. Each target must succeed on a Wisdom saving throw or have the
> Frightened condition for 1 minute or until it takes any damage.
> （SRD 5.2.1 p55）

> **Bardic Inspiration.** As a Bonus Action, you can inspire another creature within 60 feet
> of yourself that can see or hear you.
> （SRD 5.2.1 p35）

> **Preserve Life.** ... Choose Bloodied creatures within 30 feet of yourself (which can
> include you), and divide those Hit Points among them.
> （SRD 5.2.1 p56）

规则书上确实是“等于”。本切片按 §1.5 的裁决收为“至多 N、至少 1”，这是产品决定，
不是对规则的误解：规则假定你总能凑齐目标，而自动化战斗里不一定。

## 3. 已核实的定点代码事实（2026-11-17 实测）

1. **能力投影只有四个字段**：`features/models.py:930-942` 的 `to_dict()` 输出
   `capability_id`、`feature_id`、`label`、`available`、`blocked_reason`、
   `requires_target`、`target_kind`、`costs`。没有数量、射程、可见性、候选集。
2. **`requires_target` 取错了字段**：`features/models.py:938` 写的是
   `self.requires_hostile_target`。目标是“任意生物”的能力（`target_kind: "creature"`）
   该值为假，投影于是告诉前端“不需要选目标”。
3. **前端只按单目标提交**：`Dnd2024CombatPanel.vue:939-949` 的 `stageCapability`
   在 `requires_target` 为真时读取单个 `capabilityTargetId` 并写 `payload.target_id`；
   为假时**不写任何目标字段**。
4. **服务端对同一件事有两套读法**：`validation.py:1591-1594`（法术）同时接受
   `target_ids` 与 `target_id`；`validation.py:804-806`（镇服敌人）只认 `target_ids` 列表；
   `validation.py:628-636`（诗人激励）只认单个 `target_id`。
5. **数量当前是“恰好”**：`validation.py:824-826` 用 `len(targets) != count` 拒绝，
   `count = max(target_count_minimum, 魅力调整值)`。
6. **诗人激励的声明缺目标类型**：`srd_class_features.json` 的 `bardic_inspiration`
   能力块没有 `target_kind`，因此按第 2 条判定为“不需要选目标”，而它的校验要求
   一个合法盟友——**该能力在界面上不可用**。
7. **法术侧已有可用的一半**：`combat/view.py:593-594` 投影 `target_count` 与
   `upcast_target_count`；前端 `selectedSpellTargets` 已支持多选并在 `ids.length > 1`
   时改发数组（`Dnd2024CombatPanel.vue:865-866`）。
8. **预算分配是另一套特判**：`_validate_preserve_life` 读 `intent["allocations"]`
   （`validation.py:839-880`），与目标数组无关。
9. 上述缺口全部由“直接构造意图”的用例绕过：`test_dnd2024_channel_control.py`
   等用例手工传 `target_ids`，没有一条走前端会发出的形状。

## 4. 精确行为与数据契约

### 4.1 目标形状声明（服务端数据）

每条能力与每个法术效果额外声明四项，缺一即视为未声明并按 §4.5 fail closed：

1. `target_mode`：`self` / `single` / `up_to` / `all_in_range`。缺省 `self`。
2. `target_cap`：上界。整数，或由属性算出的引用（能力侧沿用
   `target_count_ability` + `target_count_minimum`；法术侧沿用 `target_count`，
   升级加量用 `upcast_target_count`）。
3. `target_filter`：`side`（`self` / `ally` / `enemy` / `any`）、`must_see`（布尔）、
   `allow_zero_hp`（布尔）、`allow_dead`（布尔）、`required_condition`（可选，例如
   Preserve Life 的 `bloodied`）。
4. `budget_split`：布尔。为真时该能力还需要在目标之间分配一份预算。

### 4.2 数量语义（本切片的裁决点）

1. `up_to` 只约束上界：提交数量 `1 <= n <= cap` 合法，`n > cap` 或 `n == 0` 拒绝。
2. `all_in_range` 不接受玩家挑选：候选集即提交集，`n` 由服务端算出，至少为 1 才可提交。
3. `single` 等价于 `up_to` 且 `cap == 1`。
4. 上界为 0（属性调整值算出 0 且没有最小值）时，`up_to` 能力不可用，`available` 为假，
   `blocked_reason` 说明原因。
5. 少选不补偿：选择 2 个而不是 3 个时，不返还资源、不折算伤害，事件按实际目标数各落一条。

### 4.3 服务端投影（前端不做规则判断）

每条形如 `capabilities[]` 的项新增字段：

- `target_mode`、`target_cap`（**已解析成整数**，前端不得自己算属性调整值）
- `requires_target`：`target_mode != "self"`
- `candidates`：`{actor_id, name, legal, reason}` 的列表，`reason` 为人类可读原因
  （`out_of_range` / `cannot_see` / `wrong_side` / `dead` / `zero_hp` /
  `not_bloodied` / `already_affected`）
- `budget`：`budget_split` 为真时给出可分配总额与每个目标的剩余可接收量，否则省略

投影必须是纯读：同一次请求里连续取两次结果一致，且不推进任何时钟。

### 4.4 提交形状

1. 目标一律走 `target_ids` 数组，**单目标也用数组**。服务端保留对旧 `target_id`
   的兼容读取（法术路径已有），但新代码只写数组。
2. 数组内不得重复；出现重复整条意图拒绝。
3. 目标不在候选集内（超距、不可见、阵营不符、已死、0 HP 且不允许）时整条拒绝，
   不做“部分成功”。
4. `budget_split` 的能力仍用 `allocations`，但其中出现的 `target_id` 必须同时出现在
   `target_ids` 里；两处不一致时拒绝。

### 4.5 fail closed

1. 声明缺 `target_mode` 却带着目标相关参数（`target_range_ft`、`target_count_ability` 等）
   时，装载期报错，不允许“猜一个默认值”。
2. `target_mode` 不在四个枚举内、`target_cap` 为负、`budget_split` 为真但
   `target_mode` 是 `self` 时，装载期报错。
3. 候选集为空时能力 `available` 为假，而不是允许提交一个空数组。

## 5. 改动文件白名单

1. `templates/rulesets/dnd2024_srd/content/class_feature_catalogs/srd_class_features.json`
2. `templates/rulesets/dnd2024_srd/content/combat_catalogs/srd_combat_core.json`
   （仅 `spell_effects` 的目标形状字段）
3. `src/rulesets/dnd2024/features/models.py`（`to_dict` 与声明校验）
4. `src/rulesets/dnd2024/features/combat.py`（候选集与上界解析）
5. `src/rulesets/dnd2024/combat/validation.py`（统一读法与数量上界）
6. `src/rulesets/dnd2024/combat/view.py`（法术侧目标形状对齐）
7. `frontend-v2/src/features/rulesets/dnd2024/combat/Dnd2024CombatPanel.vue`
   （只改“要不要选/选几个/发数组”，不新建控件）
8. `frontend-v2/src/api/types.ts`
9. `tests/rulesets/test_dnd2024_target_selection.py`（新建）

## 6. 编号测试矩阵

1. 每条 `up_to` 能力在 `n == cap` 时成功。
2. 每条 `up_to` 能力在 `1 <= n < cap` 时成功，且事件条数等于 `n`。
3. `n == 0` 与 `n > cap` 都被拒绝，且拒绝后状态未变（版本号、资源、条件全等）。
4. `n == cap` 与 `n == 1` 对同一目标的结算结果一致（少选不改变单目标结果）。
5. 镇服敌人在魅力 16（上界 3）时选 1 个合法——这是本切片裁决的回归点。
6. `single` 能力提交两个目标被拒。
7. `all_in_range` 能力不接受玩家挑选：提交少于候选集的列表被拒。
8. 候选集为空时 `available` 为假且带 `blocked_reason`。
9. 候选集里的 `legal == false` 项逐条有 `reason`，且与其成因对应（超距/不可见/阵营/死亡）。
10. 重复目标被拒。
11. `budget_split` 能力中 `allocations` 出现未在 `target_ids` 里的目标被拒。
12. 声明缺失或非法时装载期报错（三个反例各一条）。
13. 诗人激励补上目标类型后可被前端提交（候选集非空、单目标、射程内）。
14. 投影是纯读：连续两次投影结果相等且不推进时钟。
15. 单目标能力用数组提交成功（旧 `target_id` 读取路径仍可用，但不再由前端产生）。

## 7. 非目标与停止条件

1. **几何范围**（按位置圈人、锥形/球形/线形）：留到战术地图切片，本切片一律不做。
2. **召唤落点选择**：需要“位置”而不是“目标”，同属几何。
3. **前端多选控件重做**：复用既有结构；若发现必须重做，停止并回报，不在本切片内扩。
4. **2D 渲染与地图高亮**：不做。
5. **AI 座位的目标选择策略**：本切片只保证投影里有候选集与原因，AI 如何挑目标另行切片。
6. 停止条件：若发现某条能力的目标语义无法用 §4.1 四项表达（例如“目标是正在掷骰的生物”），
   停止并把该能力列为后续切片，不允许为它单独加字段。

## 8. 验收命令

```bash
ruff check src/
mypy
pytest tests/rulesets -q -n 6 --dist loadfile
```

## 9. 交付要求

1. 事件流可变，但**状态形状不变**：不新增角色/战斗状态键，本切片只改投影与校验。
2. 旧存档与重放必须照常工作：`target_id` 兼容读取保留一个版本，并在代码注释里写明为何保留。
3. §4.2 的“上界”语义要在实现处留注释，说明这是产品裁决而非规则原文，避免后来者改回“恰好”。

## 10. 执行报告模板（执行侧填写）

- §1 结论：三条命令结果
- §2 逐条对照 §4，标注落点与用例编号
- §3 偏差与未决
- §4 只看门禁才现形的缺陷
- §5 白名单外改动逐条理由

## 11. 执行报告

（待执行）
