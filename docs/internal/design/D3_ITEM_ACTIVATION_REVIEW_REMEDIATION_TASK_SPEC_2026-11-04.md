# D3 充能与激活动作：Review 修复任务书

| 字段 | 值 |
|---|---|
| 任务编号 | D3-R（post-review remediation；不是 D3b/D4 新切片） |
| 编写日期 | 2026-11-04 |
| 状态 | 待执行 |
| Review 候选 | `3366aebfba67da737c121d2800e8d1c0f0b4a476` |
| D2 对照基线 | `531a853943e792f29b1fa988221aa277d1c4f7b8` |
| Review 结论 | Request changes；六项阻塞问题及原始 T1–T20 覆盖缺口必须闭环 |
| 执行方式 | 后续执行模型实施；本任务书本身不代表任何修复已完成 |
| 提交纪律 | 可以修改本任务书白名单内的代码、测试和执行报告；不得自行 push、创建 PR 或扩大范围，commit 由外层指令决定 |

---

## §0 目标、完成定义与开工纪律

### 0.1 目标

在不扩大 D3 既定规则范围、不破坏 canonical/live 权威、EventBatch 原子性、replay、既有存档和多人权限的前提下，修复 review 已复现的六项问题，并把原任务书 T1–T20 从“部分或直接 validator 覆盖”补成真实行为验收。

本任务不是重新实现 D3。已验证正确的原子结算、精确 `item_ref` 扣件和 duplicate no-op 不得被重写或回归。

### 0.2 完成定义

以下全部为必要条件：

1. §3 的 R1–R6 全部修复，原有错误行为均有先失败、后通过的回归测试。
2. 战斗与探索都有服务端声明、现有动作区可提交的激活入口；不得再把 D3-9 仅登记为债务就宣称 D3 完成。
3. 非法物品声明在明确的 D&D 装载边界 fail closed；直接调用 validator 的单元测试不能替代装载集成测试。
4. §5 的修复矩阵及原任务书 T1–T20 均有实际测试名和结果；不得以“代码明显如此”代替覆盖。
5. 后端 rulesets 全量、前端类型/组件/P2P/真实 UI 验证和最终 diff 检查全部完成并记录。
6. D3-10（治疗药水仅有测试 fixture）和 D3-11（companion 弹药/背包权威）保持既有边界，不为消除债务而伪造内容或扩张实现。
7. 最终 changed-file list 只含本任务，不串入 D3b、D4、其它切片、生成缓存、日志或无关格式化。
8. 完成后仍需独立 review；执行模型不得自行把“实现完成”等同于“审核通过”。

### 0.3 开工纪律

1. 开工前阅读：
   - `docs/ARCHITECTURE_CN.md`；
   - `docs/ENGINEERING_RULES.md`，尤其高风险持久化、权限、ruleset 与 fail-closed 测试要求；
   - `docs/adr/0007-runtime-state-ownership.md`；
   - `docs/adr/0012-resource-recovery-authority.md`；
   - `docs/internal/design/D3_ITEM_ACTIVATION_TASK_SPEC_2026-11-03.md`；
   - `docs/internal/design/D3_ITEM_ACTIVATION_EXECUTION_REPORT_2026-11-04.md`；
   - 本任务书全文。
2. 记录实际 HEAD、上游 main、merge-base 和工作区状态。上述 commit 是 review 锚点，不要求回退或重写历史。
3. 工作区必须干净，或已由用户明确确认哪些既有改动可保留。不得丢弃、reset、clean 或覆盖其它会话改动。
4. 行号只用于定位 review 证据；执行时必须重读当前文件，核对语义漂移。
5. 先补能复现原错误的测试，再修实现。保留修复前/后结果；不得删除断言、放宽契约、改随机种子或只测 helper 来规避失败。
6. 若必须修改 §4 之外的文件，先停止并报告“文件、最小改动、owning contract、无法在白名单内完成的原因”。

---

## §1 不可破坏的既有契约

1. **充能唯一权威**：运行时 mutable charge 只能写入 `canonical.equipment.item_state[item_ref].charges.current`；bundle `charges.max` 是静态上限，不得复制为第二份运行时权威。
2. **数量唯一权威**：live backpack 数量继续由既有 character/economy 路径提交，当前通过 `take_from_inventory` 按 canonical `item_ref` 精确扣减。不得让 reducer 持有完整 live sheet，也不得按 display name 扣件。
3. **原子性**：动作经济、charge/consumed、治疗和审计事件仍属同一 EventBatch；snapshot、sheet 副本、ledger 全部成功后才提交。任何失败不得留下部分充能、HP、动作或数量变化。
4. **replay**：相同 stable batch id 必须 duplicate no-op；不重掷、不重复扣充能、不重复扣数量。不得通过删除 ledger 或更换 batch id 修复重复结算。
5. **动作经济**：战斗只支持 `action` / `bonus_action`；探索无动作经济。激活不是施法，不耗法术位、不要求准备、不开反制窗口。
6. **治疗语义**：本任务只修物品激活治疗，不顺手重构或扩张既有探索施法治疗。物品激活在战斗/探索必须对 `cannot_regain_hp` 产生同构治疗事件。
7. **声明与身份**：locale/display name 只用于展示；机械身份始终是 canonical `item:<id>`。非法声明和损坏状态 fail closed，不猜测、不静默修复。
8. **内容边界**：继续使用测试内 wand/potion fixture；不得伪造 SRD `source_ref`，不得借本任务批量填充魔法物品。
9. **保留的 D3 边界**：同 charged ref `owned > 1` 继续拒绝；companion 弹药保持 D3-11；敌方/多段攻击不因本任务扩张。
10. **generic 边界**：不得修改 engine `ACTION_KINDS` 的 `consumable` 空壳，不得在 generic bundle/engine 中加入 D&D 物品分支。

---

## §2 Review 证据摘要

以下结果已在 review 候选上实际复现，不是理论建议：

| ID | 已复现行为 | 主要证据位置 |
|---|---|---|
| R1 | 战斗 `available_intents` 无 `activate_item`；探索返回空动作；前端无激活提交路径 | `combat/engine.py`、`exploration/engine.py`、`Dnd2024CombatPanel.vue` |
| R2 | `recharge.on="sunrise"` 被 catalog 接受，直到长休才抛 `RestError` | `combat/catalog.py`、`resting/engine.py`、`items/charges.py` |
| R3 | 同一 `cannot_regain_hp` 状态下，战斗治疗 delta=0，探索治疗 delta=6、HP 5→11 | `combat/resolution.py`、`exploration/engine.py` |
| R4 | 探索接受 `consumable="false"`，生成 consumed 并删除背包行 | `exploration/engine.py`、`items/activation.py` |
| R5 | `max=3,current=9` 时长休成功并静默写成 3 | `items/charges.py` |
| R6 | `qty=0` 仍初始化 `current=max`，已有 current=0 时长休仍回充 | `character/reconciliation.py`、`resting/engine.py`、`character/attunement.py` |

详细行号见 review 记录；执行时以当前代码为准。

---

## §3 工作包与逐项修复规格

### 3.1 R1 — 补齐战斗/探索的服务端声明与真实激活入口

#### 必须实现的语义

1. 战斗 `available_intents` 必须提供当前 actor 可发现的 `activate_item` 能力；探索对应提供 `exploration.activate_item`。
2. 能力投影来自服务端 bundle 与权威持有状态，至少携带 UI 提交所需的 canonical `item_ref`、本地化显示名、activation cost/target，以及合法目标选择所需信息。不得让前端读取隐藏 canonical sheet 或自行推断规则。
3. 非法、未持有、数量不足、充能不足、未同调、同 charged ref 多件等条目不得被投影为可正常提交的可用能力；如保留 disabled/blocked 展示，原因也必须来自服务端。
4. 在既有 `Dnd2024CombatPanel.vue` 动作区加入物品选择与提交，不新增独立库存面板：
   - 战斗提交 `type="activate_item"`、`actor_id`、`item_ref`，按声明提交合法 `target_id`；
   - 探索提交 `type="exploration.activate_item"`、`actor_id`、`item_ref`，目标语义保持服务端既有 self 约束；
   - 不提交 HP、治疗量、charge 当前值、数量或消耗结果。
5. P2P `ruleset.intent` 白名单必须允许 `item_ref`；`target_id` 已有则复用，不得加入其它客户端权威字段。
6. 前端只按 projection 展示和选择，不硬编码 wand/potion canonical id，不按中文/英文显示名识别物品。
7. D3-10 继续存在：可用测试 bundle/fixture 证明完整 UI 链，不得为做演示而向 SRD 添加无来源物品。

#### 最低测试

1. 战斗和探索服务端 projection 均能发现合法物品，非法/不可用物品按契约不显示或显示服务端 blocked 状态。
2. 组件测试覆盖战斗物品、ally/self 目标和探索物品的按钮、选择及准确 intent payload。
3. P2P 测试证明 `item_ref` 不被剥离，伪造数量/charge/HP 字段仍不被接受。
4. 至少一条真实 UI/e2e 链从动作区提交到服务端事件与 live/canonical 状态更新；不能只断言按钮存在。
5. 原有无激活物角色的动作区、施法、攻击和探索施法入口不回归。

### 3.2 R2 — 在 D&D 装载边界校验物品声明

#### 必须实现的语义

1. 在 ruleset-owned 装载/catalog 边界对每个相关 item 校验本切片声明，至少包括：
   - `activation` 存在时调用 activation validator；
   - `consumable` 存在时必须为 bool；
   - `charges` / `recharge` 存在时调用对应 validator，并拒绝无法形成合法充能语义的组合。
2. 未知 `recharge.on`、未知键、非法 amount/dice 等必须在装载时失败，不得等到激活或休息。
3. 在执行报告中指出唯一或共同的装载校验入口，并证明 combat、exploration、rest 都不能绕过它。只修一个可被其它消费者绕过的 catalog constructor 不算完成。
4. 优先复用现有 `Dnd2024CombatCatalog.from_bundle` 或 D&D runtime 装载边界。不得把 D&D 特判塞进 generic `src/rulesets/bundle.py`。
5. 若必须新增通用 plugin/registry 才能形成共同装载入口，触发 §7 停止条件；不得在本任务顺手设计通用框架。

#### 最低测试

1. 通过真实装载入口加载含 `recharge.on="sunrise"` 的临时 bundle，装载即失败。
2. 非法 activation、非 bool consumable、非法 charges/recharge 各有装载集成用例，不只直接调用 validator。
3. 合法 `dawn`、`short_rest`、`none` 和既有 SRD bundle 正常加载。
4. 修复前“catalog 接受、长休才失败”的复现用例修复后不再能进入休息结算。

### 3.3 R3 — 统一物品激活治疗的阻断事件语义

#### 必须实现的语义

1. 战斗和探索使用相同的物品治疗事件构造语义，至少统一：`healing`、`target_id`、`delta`、`amount`、`heal_before`、`heal_after`、`rolls`，以及 `blocked_by="cannot_regain_hp"`。
2. 有 `cannot_regain_hp` 时仍按既有战斗契约结算激活成本与物品消耗，但治疗 delta/amount 为 0、HP 不变，并保留 blocked 证据。
3. 无阻断时继续使用既有骰式管线，HP 封顶 max；探索不新增动作经济事件。
4. 可提取本切片共享的 item-healing helper，但不要求重构无关施法治疗；禁止复制出第三套 HP 计算。

#### 最低测试

1. 相同 RNG、相同 HP、相同条件分别跑战斗/探索，治疗事件字段同构；允许的差异仅是明确不属于治疗事件的 action/actor 上下文。
2. 有阻断：两边均 delta=0、HP 不变、blocked_by 正确，数量/charge 按原契约只扣一次。
3. 无阻断：两边均正常治疗和封顶，rolls 保留。

### 3.4 R4 — 探索拒绝非 bool `consumable`

#### 必须实现的语义

1. 探索 activation validation 必须调用既有 `validate_consumable_declaration`，即使装载层已校验，消费者仍保持 fail-closed 防线。
2. 只有严格的 `True` 表示消耗品；缺省/严格 `False` 不消耗。禁止用 truthiness 把字符串、数字或容器解释为消耗品。
3. 战斗既有行为保持不变。

#### 最低测试

- `"false"`、`"true"`、`0`、`1`、列表/dict 等非法值在探索 resolve 或装载边界被拒绝，HP、charge、背包、动作和 ledger 均无变化。
- 严格 `True` 消耗一次；严格 `False` 不消耗。

### 3.5 R5 — 回充拒绝 `current > max` 的损坏状态

#### 必须实现的语义

1. `recharge_for_rest` 与 `spend_charges` 一样，在读取阶段拒绝 bool、非 int、`current < 0` 和 `current > max`。
2. `min(max, ...)` 只用于合法恢复结果封顶，不得用于修复输入时已经越界的 current。
3. 失败时不得返回部分休息结果或修改输入 sheet；其它物品不得形成可见的部分回充事件。

#### 最低测试

1. `max=3,current=9` 的短休/长休按声明触发时抛既有领域错误，输入 payload 深度不变。
2. `current=max-1` 正常封顶到 max；负数、bool、非 int 既有拒绝不回归。
3. 多件物品中存在损坏项时无部分状态落账。

### 3.6 R6 — 零数量不属于持有，不参与初始化或回充

#### 必须实现的语义

1. reconciliation 和 rest 的 held-ref 集合只包含聚合数量严格大于 0 的 canonical item_ref。
2. `qty=0` 且 item_state 缺失时不得初始化；若旧状态已存在，不得借本任务删除或重写它，但不得回充。
3. 数量从 0 恢复为正数后，缺失的 item_state 可按既有“首次持有”规则幂等初始化；既有 current 不被重置。
4. 不改变 `owned_ref_counts` 对其它调用方的既有聚合语义；如需要过滤，在持有判定的 owning consumer 做最小处理。

#### 最低测试

1. 零数量、无 item_state：reconcile 后仍无充能状态。
2. 零数量、已有 current=0：长休/短休均不按声明回充，无 `recharge_item` 事件。
3. 正数量对照正常初始化/回充；重复 reconcile 不重置 current。
4. 激活对零数量继续拒绝，不能因残留 item_state 而使用物品。

---

## §4 文件白名单

### 4.1 后端生产代码

仅允许按对应工作包修改：

- `src/rulesets/dnd2024/items/activation.py`
- `src/rulesets/dnd2024/items/charges.py`
- `src/rulesets/dnd2024/items/__init__.py`（仅在共享 helper 需要导出时）
- `src/rulesets/dnd2024/combat/catalog.py`
- `src/rulesets/dnd2024/combat/engine.py`
- `src/rulesets/dnd2024/combat/validation.py`
- `src/rulesets/dnd2024/combat/resolution.py`（仅在统一物品治疗构造需要时）
- `src/rulesets/dnd2024/exploration/engine.py`
- `src/rulesets/dnd2024/resting/engine.py`
- `src/rulesets/dnd2024/character/reconciliation.py`
- `src/rulesets/dnd2024/runtime.py`（仅用于接入 ruleset-owned 共同装载校验；不得改变公开运行时契约）

明确不允许修改：

- `src/rulesets/bundle.py`、generic combat engine/contracts；
- `src/engine/combat_contracts.py`；
- `src/commands/state_items.py` 和旧叙事 `_use_inventory_item` 路径；
- D2 同调状态结构、`character/attunement.py` 的全局聚合语义；
- 其它 ruleset、AI 配置、存档迁移、route/service locator。

### 4.2 前端生产代码

- `frontend-v2/src/features/rulesets/dnd2024/combat/Dnd2024CombatPanel.vue`
- `frontend-v2/src/api/types.ts`（仅补服务端动作 projection 的只读类型）
- `frontend-v2/src/peer/game/bridge.ts`（仅加入 `item_ref` 及必要的测试证明）

不得新增专用物品面板、第二套提交 API 或客户端机械结算。

### 4.3 测试

允许修改：

- `tests/rulesets/test_dnd2024_item_activation.py`
- `frontend-v2/tests/Dnd2024CombatPanel.test.ts`
- `frontend-v2/tests/peerGameBridge.test.ts`
- `frontend-v2/e2e/dnd2024-workspace.spec.ts`

允许新增：

- `tests/rulesets/test_dnd2024_item_review_remediation.py`（仅用于真实装载、跨路径和损坏状态集成测试；普通用例优先放既有 activation 测试）

除既有断言因错误行为修复而必须加强外，不得放宽或删除测试。无需再修改 D3 已调整的 `test_bundle_loader.py`、`test_dnd2024_hold_person.py`、`test_dnd2024_monk_equipment.py`；若执行时发现必须改，先停止上报。

### 4.4 文档

允许修改：

- 本任务书：追写执行报告；
- `docs/internal/design/D3_ITEM_ACTIVATION_EXECUTION_REPORT_2026-11-04.md`：追加 remediation 结果、修正 T1–T20 覆盖声明、登记原白名单偏差，不改写历史执行结果。

公开文档不得链接本任务书或其它 `docs/internal/` 文件。

---

## §5 验收矩阵

执行报告必须逐项引用真实测试名；不允许只写“已覆盖”。

| ID | 必须证明的结果 |
|---|---|
| M1 | R1 战斗/探索 available_intents、组件、P2P 和至少一条真实 UI 提交链闭环；D3-9 只有在此完成后才能关闭 |
| M2 | R2 非法声明经真实装载入口即失败，combat/exploration/rest 无绕过路径 |
| M3 | R3 战斗/探索物品治疗在阻断与非阻断情况下同构，HP、rolls、消耗正确 |
| M4 | R4 非 bool consumable fail closed，严格 bool 行为正确且无部分落账 |
| M5 | R5 current>max 回充拒绝，合法封顶与输入原子性保持 |
| M6 | R6 qty=0 不初始化、不回充，正数量与幂等行为不回归 |
| M7 | 原 T1 增加 HP 接近 max 的封顶断言；T7 增加同调后成功；T8 同时覆盖 action/bonus_action 耗尽 |
| M8 | 原 T9 在 dawn 同时覆盖固定值和骰式；T10 显式证明 short_rest 项在长休不触发、短休触发 |
| M9 | 原 T11 使用真实装载入口；T12 至少覆盖战斗与探索 charged/consumable replay，充能和数量均不重复扣 |
| M10 | 原 T13 逐一覆盖 shortbow、longbow、hand/light/heavy crossbow 及零弹药 validation 拒绝 |
| M11 | 原 T20 通过实际 item.consumed 链证明同名不同 ref 只扣目标 ref；重复 reconcile/换装不重置 current |
| M12 | 原子故障注入仍保证 sheet、ruleset state、ledger 不变；duplicate 不重掷、不重复扣减 |
| M13 | 原 T1–T20 其余项目继续有明确测试名和通过结果，不因修复矩阵而省略 |

原任务书 T1–T20 全部仍是验收条件。M7–M13 是对其覆盖方式的补强，不是替代。

---

## §6 验证命令与证据要求

### 6.1 后端

使用项目要求的 Python 环境，记录实际命令、通过/失败数量和警告分类：

```bash
python -m pytest -q tests/rulesets/test_dnd2024_item_activation.py tests/rulesets/test_dnd2024_item_review_remediation.py
python -m pytest -q tests/rulesets
python -m ruff check src/rulesets/dnd2024 tests/rulesets/test_dnd2024_item_activation.py tests/rulesets/test_dnd2024_item_review_remediation.py
```

若未创建新的 remediation 测试文件，相应命令改为实际测试文件，不得保留失效命令作为完成证据。

Review 基线结果为：新增测试 `17 passed`，rulesets 全量 `1105 passed, 37 warnings`。执行时必须重新运行，不得照抄。

### 6.2 前端与真实 UI

在 `frontend-v2/` 使用仓库要求的 Node/npm 和 lockfile 环境：

```bash
npm run typecheck
npm test -- --maxWorkers=1 Dnd2024CombatPanel.test.ts peerGameBridge.test.ts
npm run lint
npm run build
npm run test:e2e -- e2e/dnd2024-workspace.spec.ts
```

如实际测试 runner 参数不同，使用仓库既有等价命令并记录。必须提供激活真实 UI 链的结果；环境缺依赖导致未运行时，本任务保持未完成，不得写成通过。

### 6.3 最终差异检查

```bash
git diff --check
git status --short
git diff --stat
```

核对 changed-file list、无白名单外改动、无生成物/日志、无公开文档链接 `docs/internal/`。

---

## §7 停止条件

出现以下任一情况，停止并上报，不得自行扩张：

1. 共同装载校验必须修改 generic bundle loader、增加通用 registry 或改变公开 bundle contract。
2. UI 所需信息无法通过 ruleset projection 最小扩展获得，必须读取私有 `api._*`、完整 canonical sheet 或新增平行提交 API。
3. 修复数量持有语义需要改变 live backpack 权威、引入实例 ID/slot map，或修改 companion 背包权威。
4. 治疗同构需要重构通用施法/HP 体系，或发现动作成本、消耗和治疗无法继续保持同一原子批次。
5. 需要新增卷轴、耗尽销毁、伤害/豁免/区域激活、反应激活、随机损毁、真实黎明世界时钟或 D3b/D4 字段。
6. 必须修改白名单外文件或放宽既有测试才能通过。

停止时提供：具体阻塞、已确认代码事实、最小契约决策和未提交改动列表；不得用未经批准的“迁移债”替代任务要求。

---

## §8 执行报告模板

执行完成后追写，不得预先标记通过：

1. 实际 HEAD、merge-base、工作区闸门和行号漂移。
2. R1–R6：根因、修改文件、修复前失败证据、修复后测试名与结果。
3. M1–M13：逐项测试名与结果。
4. 原 T1–T20：逐项映射到实际测试；对间接覆盖必须写明完整调用链。
5. 装载校验入口及 combat/exploration/rest 不可绕过的证明。
6. 战斗与探索 UI 提交 payload、P2P 字段和真实 UI/e2e 结果。
7. 原子性、replay、canonical/live 权威回归证据。
8. 后端、前端、lint/typecheck/build/e2e 和最终 diff 的完整命令与结果。
9. 白名单符合性及原 D3 未登记偏差：`test_bundle_loader.py` 数量断言、两个既有远程攻击测试 fixture 修改。
10. 债务状态：D3-9 是否真正关闭；D3-10/D3-11 保持不变；不得新增未裁决范围缩减。
11. 最终 changed-file list 和仍需独立 review 的声明。
