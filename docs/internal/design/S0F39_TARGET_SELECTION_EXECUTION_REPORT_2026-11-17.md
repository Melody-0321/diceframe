# S0-F39 执行报告：统一选目标入口

| 项 | 值 |
|---|---|
| 切片 | S0-F39（原写 F38，因编号冲突改；见 §7.1） |
| 任务书 | `S0F39_TARGET_SELECTION_TASK_SPEC_2026-11-17.md` |
| 执行日期 | 2026-11-17 |
| 改动规模 | 12 个既有文件（+1287 / −97）＋ 新测试文件 464 行 / 18 条用例 |
| 状态 | 实现完成；本切片用例与邻接回归全绿；**全量未取得干净结论**（§6.3） |

## 1. 结论

选目标从「四个特性各一套特判」收敛成**一个声明 + 一个投影 + 一个读法**：

- 声明层新增 `target_mode` / `target_cap` / `target_filter` / `budget_split`，装载期 fail closed；
- 投影层给出 `target_mode`、已算成整数的 `target_cap`、带 `legal` 与 `reason` 的 `candidates`、`budget`；
- 校验层统一读 `target_ids`（单目标也走数组），旧 `target_id` 只保留一版兼容读取；
- 前端不再自己判距离/可见性/敌我，也不自己算魅力调整值。

三条产品口径落到了代码里，并且都写了「不要改回去」的理由：
**数量是上界不是必须选满**（§1.5）、**至少选 1 个**、**`all_in_range` 不接受子集**。

## 2. 先决事实（任务书 §3 核对结果）

九条全部成立。另有两条任务书没写、但影响实现的事实，实现时按它们走：

1. **`requires_target` 取的是 `requires_hostile_target`**（`features/models.py`）。所以「目标是任意生物」的能力在投影里被判成「不需要选目标」——诗人激励、圣疗、神圣火花都属于这一类。
2. **`bardic_inspiration` 的声明里没有 `target_kind`**，于是它同样被判成「不需要选目标」，而它的校验要求一个合法盟友。**该能力在修复前于界面上不可达**，与镇服敌人同因。本切片给它补了 `target_mode: "single"` + `target_filter.side: "ally"` + `must_see`。

## 3. 逐项机械

### 3.1 声明层（`features/models.py`）

- `TARGET_MODES = {self, single, up_to, all_in_range}`、`TARGET_SIDES = {any, ally, enemy}`、`TARGET_CAP_ABILITIES`。
- `FeatureCapability` 增 `target_mode` / `target_cap` / `target_cap_ability` / `target_cap_minimum` / `target_filter` / `budget_split`。
- `_parse_target_shape`：常量上界与能力上界**只能有一个来源**；`all_in_range` 不许声明上界；`single` 的上界只能是 1；`up_to` 无上界且非预算型即报错（§4.5）。
- `_parse_target_filter`：未知键、未知 side、非布尔的三个开关（`must_see` / `allow_zero_hp` / `allow_dead`）、非规范 id 的 `required_condition` 全部拒收。
- 三条 fail closed（§4.5）：声明了目标参数却没说选几个 → 报错，**不替作者猜**；`budget_split` 配 `self` → 报错；`self` 声明上界 → 报错。

### 3.2 投影层（`features/combat.py`、`combat/view.py`、`combat/engine.py`）

- `resolve_target_cap(capability, modifiers)`：把上界算成整数。能力调整值由 `resolver` 传入（角色层算好的修正），**这个模块不 import 角色层**——`character.builder` 反向 import 本包，直接 import 会成环。
- `target_candidates(...)`：唯一回答「能不能选这一个」的函数，返回每行 `legal` + `reason`（`dead` / `wrong_kind` / `wrong_side` / `out_of_range` / `cannot_see` / `zero_hp` / `not_bloodied` / `already_affected`）。
- `view._capability_target_projection`：纯读。距离用剧场模式的标量差，可见性复用 `_spell_target_visible`，诗人激励的「已被激励」复用 `_active_bardic_instance`——**没有第二套判定**。
- `engine` 把 `target_cap` / `candidates` / `targets` 三样一起放进 `class_capability` 动作行。

### 3.3 校验层（`combat/validation.py`）

- `_declared_target_ids(intent)`：全模块唯一的读法（`target_ids` 优先，`target_id` 兼容）。
- `_TARGET_RANGE_BY_ACTION`：action kind → (射程参数键, 兜底值) 的唯一对应表。
- `_validate_abjure_foes`：由「恰好等于魅力调整值」改为「1..上界」；**判据是 `len(targets) != cap` → `not (1 <= len <= cap)`**。
- `_validate_turn_undead`：`all_in_range`，提交集必须等于候选集（拒子集、拒超集）。
- `_validate_lay_on_hands` / `_validate_divine_spark` / `_validate_bardic_grant`：由读 `target_id` 改为读数组。
- `_validate_preserve_life`：`allocations` 与 `target_ids` 必须指向同一批生物（新增一致性检查）。

### 3.4 结算层（`combat/resolution.py`）

五个能力的结算入口统一从 `_declared_target_ids` 取目标，单目标能力取首元素。

### 3.5 前端（`Dnd2024CombatPanel.vue`、`combatCopy.ts`、`api/types.ts`）

- `capabilitySelection` 是**唯一**回答「选了什么、能不能提交」的计算属性：`all_in_range` 直接折算成整组
  合法候选，其余形状是「去重后的 ids + 1..`target_cap`」。
- 目标下拉改为多选列表，来源是 `candidates` 里 `legal` 的行；旧 `targets` 仅作兜底。
- 提交一律发 `target_ids` 数组，不再发 `target_id`。
- `noCapabilityTarget` 文案由「当前没有可指定的敌对目标」改为中性的「当前没有可指定的目标」（目标不再只有敌对）。

## 4. 工作树里不属于本切片的改动（提交时必须排除）

本工作树在开工前就是脏的，下面这些**不是本切片**，不要混进同一个提交：

`character/derivation.py`、`combat/catalog.py`、`combat/check_windows.py`、`combat/reducer.py`、
`exploration/engine.py`、`progression/advancement.py`、`runtime.py`、`webui/services/ruleset_rest.py`、
`templates/.../combat_catalogs/srd_combat_core.json`、`srd_advancement_feats.json`、
`locales/{en,zh-CN}/.../srd_class_features.json`（各加一行 `turn_start` 标签）、
以及 `test_dnd2024_{active_buffs,combat,equipment_data,failed_d20_windows,passive_capstones,rest_decision,save_damage_survival,spell_grants,channel_healing}.py`。

本切片自身的改动恰好是：`features/{models,combat,resolver}.py`、`combat/{validation,view,engine,resolution}.py`、
`content/class_feature_catalogs/srd_class_features.json`、`api/types.ts`、`Dnd2024CombatPanel.vue`、`combatCopy.ts`、
`test_dnd2024_channel_control.py`，加上两个新文件（本报告与 `test_dnd2024_target_selection.py`）。

## 5. 测试矩阵（18 条，任务书要求 15 条）

| # | 用例 | 对应任务书 |
|---|---|---|
| 1 | `test_up_to_accepts_the_full_ceiling` | 选满合法 |
| 2 | `test_up_to_accepts_fewer_targets_and_emits_one_event_each` | **少选合法**（§1.5） |
| 3 | `test_zero_targets_and_over_the_ceiling_are_refused_without_state_change` | 0 个与超上界，且**不改状态** |
| 4 | `test_a_target_resolves_the_same_alone_or_alongside_another` | 事件流不随目标数变形 |
| 5 | `test_a_ceiling_above_one_still_accepts_a_single_target` | **本切片回归点** |
| 6 | `test_single_refuses_two_targets` | `single` 只收 1 个 |
| 7 | `test_all_in_range_refuses_a_subset_of_the_candidates` | 射程内全部，拒子集 |
| 8 | `test_empty_candidate_set_marks_the_capability_unavailable` | 无候选时不可用 |
| 9 | `test_every_illegal_candidate_carries_its_own_reason` | 每条不可选都有原因 |
| 10 | `test_a_dead_creature_is_not_a_legal_target` | 死亡不是候选 |
| 11 | `test_duplicate_targets_are_refused` | 去重 |
| 12 | `test_budget_split_allocations_must_match_the_target_array` | 预算与目标集一致 |
| 13 | `test_broken_target_declarations_fail_closed_at_load` | 四条声明错误（缺 mode / 未知 mode / 负上界 / budget 配 self） |
| 14 | `test_bardic_inspiration_is_reachable_from_the_projection` | **诗人激励从不可达变可达** |
| 15 | `test_the_projection_is_a_pure_read` | 投影两次结果一致 |
| 16 | `test_a_single_target_capability_accepts_an_array` | 单目标也走数组 |
| 17 | `test_legacy_scalar_target_still_resolves` | 旧 `target_id` 兼容 |
| 18 | `test_known_gaps` | 未实现清单显式挂起（§5 纪律） |

## 6. 回归

### 6.1 本切片自带用例

`tests/rulesets/test_dnd2024_target_selection.py`：**18 passed**（串行，单文件）。

### 6.2 邻接回归

`test_dnd2024_{target_selection,channel_control,channel_healing,bardic_inspiration,monk_combat,cutting_words}.py`
一次跑：**213 passed**。（在最后一次「上界只留一处算法」改动之前；改后单独重跑
`target_selection` + `channel_control` 为 **76 passed / 1 failed**，该失败见 §6.4。）

### 6.3 全量（未取得干净结论，如实记录）

两次 `-n 5 --dist loadfile` 全量：**9943 passed / 9 failed / 3 errors**、**9942 passed / 10 failed / 3 errors**。
逐条对照基线工作树 `E:/tmp-s0f38-base` 后，全部落在下列两类，**没有一条由本切片引入**：

| 失败 | 归属 | 证据 |
|---|---|---|
| `test_docker_launcher` / `test_docker_data_generation` / `test_docker_runtime_v1_upgrade`（6+1 failed、3 errors） | 本机常驻基线 | 基线树同样失败 |
| `test_ai_combat_choices::test_human_submission_enters_same_model_automation_boundary` | 既有问题 | 基线树同样失败 |
| `test_launcher_lifecycle`（第一轮无、第二轮 2 条） | 并行端口抢占 | 串行跑**两棵树各 6 passed** |

**最终串行全量没有跑完，主动终止**：跑到 51 分钟时发现同一工作树有第二个进程在跑它自己的全量
（`E:/pytest-tmp/f38-full`、`f38-final`、`f38-final2`，21:00–21:17 创建）。两套全量同机并发既抢 CPU
又抢端口，此时得出的任何数字都不可采信，于是停掉而不是硬报一个结果。

**待办**：等 S0-F38（武器词条）那边收工、工作树只含一条切片时，重跑一次串行全量作为本切片的权威回归。

### 6.4 一条不属于本切片的失败

`test_dnd2024_channel_control.py::test_a_ranged_weapon_cannot_be_imbued` —— 当前树失败、基线树通过，
断言是 `"Melee weapon" in resolved["error"]`，实际拿到
`a shield in the other hand blocks two-handed use`。

这条来自并发推进的武器切片：它新增了「另一只手有盾则不能双手使用」的检查，且该检查先于
「必须是近战武器」抛出，于是这条**旧用例的期望文案**被顶掉了。与本切片无关，归属对方修
（改期望或调整检查顺序）。

## 7. 偏差 / 未决 / 只看门禁才现形的缺陷

### 7.1 编号冲突（偏差）

`S0-F38` 已被 `S0F38_WEAPON_PROPERTIES_AND_HAND_STATE_TASK_SPEC_2026-11-17.md`（武器基本词条与在手状态，未提交）占用，并写明「新分配」。本切片改为 **S0-F39**，同时改了：
本报告与任务书文件名、`S0F23_CHANNEL_CONTROL` §4 第 12 条的引用、以及代码/测试里 20 处 `S0-F38` 注释。

留档说明：`S0_TASK_INDEX_2026-11-07` 在仓库里**并不存在**（武器那份任务书引用了它），所以没有索引行需要补。

### 7.2 只看门禁才现形的缺陷（必须记）

**我把兼容字段 `targets` 收窄成了 `{actor_id, name}` 两项，丢了 `hp` / `max_hp` / `kind`。**
新前端读 `candidates`，所以我自己那 18 条用例全绿；但既有用例
`test_dnd2024_monk_combat.py::test_capability_targets_only_list_hostiles` 直接断言 `targets` 里的血量，
在全量回归里才报出来。已改为「回填完整 actor 行，只按合法集过滤」。

这一条和 S0-F14/F20 的教训同型：**新增用例全绿 ≠ 改动正确**，兼容字段的形状是有既有契约的。

### 7.3 候选集必须按 `target_kind` 再筛一次（任务书未要求）

`target_filter` 只表达「敌我 / 可见 / 活着 / bloodied」，不表达「什么生物」。只按 filter 建候选集，
`turn_undead` 会把射程内的队友一起列进「射程内全部」，而校验只接受亡灵全集 —— 正好又制造一次
「列表里有、提交被拒」。已在候选集里对 `target_kind == "undead"` 单独筛，并有用例
`reasons["enemy:brigand-1"] == "wrong_kind"` 钉住。

### 7.4 只看门禁看不出来、只能人工走查才现形的缺陷：`all_in_range` 在界面上点不动

`canStageDock` 判定「能力可提交」用的是 `capabilitySelection.valid`，而 `all_in_range` 的
`capabilityTargetSlots` 是 0（玩家不挑），槽位里永远是空串 → `valid` 恒为假 → **按钮永远禁用**。
服务端已经能收整组，前端却点不了，正是本切片要消灭的那种「服务端可表达、界面不可达」。

修法不是在 `canStageDock` 里补一个 `|| target_mode === 'all_in_range'`（那是第二条读法），
而是让 `capabilitySelection` 自己把 `all_in_range` 折算成「整组合法候选」，`valid` 与 `ids`
从此只有一处来源；`stageCapability` 里原来的三元分支也一并删掉。

**这条没有任何自动化用例能覆盖**——前端单测只管函数，而它坏在「槽位数量」与「提交判定」两处
各自成立的组合上。记录在此，作为「前端也要手工走一遍每条形状」的证据。

### 7.5 未决：`budget_split` 在界面上显式挂起

`preserve_life` 能投影、能校验、能结算，但面板对 `budget_split` 直接显示
「这项能力需要在目标之间分配点数，当前面板暂不支持提交」，且提交按钮禁用。
这是**显式挂起**（任务书 §1 第 6 条的口径），不是静默近似——但仍是本切片的一处缺口，
需要单独一个「点数分配控件」切片，不该塞回这里。

### 7.6 未决：预算型的人数上界没有权威定义

`preserve_life` 的投影上界取「合法候选数」，没有和池子总量取小。原因不是懒得改，而是
`_validate_preserve_life` **允许某个目标分配 0 点**，所以池子总量并不是人数的权威约束；
若投影改成 `min(len(legal), budget_total)`，投影会比校验更严，玩家看到的可选列表比服务端实际接受的窄
—— 只是把不一致换了个方向。（这条我先真的改成 `min` 了，走查校验代码后回退。）

收紧它需要先在 `_validate_preserve_life` 里要求「每个入选目标至少 1 点」，那是另一条改动。
代码里已留注释指向本节。

### 7.7 白名单偏差（必须单列）

任务书 §5 的白名单与实际改动有出入，逐条说明：

**白名单外、但必须改的（否则功能不成立）**

| 文件 | 为什么非改不可 |
|---|---|
| `combat/resolution.py` | 五个能力的**结算入口**各自 `intent["target_id"]`；不改则校验放行、结算 KeyError |
| `combat/engine.py` | 能力进投影的唯一入口；`target_cap` / `candidates` / `targets` 要在这里挂上动作行 |
| `features/resolver.py` | 唯一能把角色属性修正喂给 `resolve_target_cap` 的地方（`features` 不能 import 角色层，会成环） |
| `combatCopy.ts` | 新增 `capabilityBudgetUnsupported` 文案；并改写 `noCapabilityTarget`（目标不再只有敌对） |
| `tests/rulesets/test_dnd2024_channel_control.py` | 原用例断言「少选即拒」，与新口径直接冲突，必须同步 |

**白名单内、但实际没改的**

- `templates/.../srd_combat_core.json`：法术侧的目标形状字段（`target_count` / `target_scope` /
  `repeat_targets`）**本来就已经存在**，本切片不需要动它。它在工作树里的 38/38 改动来自别的切片。

### 7.8 未决：`all_in_range` 的「进入/离开范围」没做

`turn_undead` 现在只判提交那一刻的集合。光环类（圣武士光环、宿敌印记）需要的「进出范围」是动态的，
本切片按任务书 §2 明确不做，留给战术地图切片。

### 7.9 环境说明：工作树被并发编辑 + 并发跑全量

执行期间同一个工作树有第二个进程在写（`combat/hands.py` 新建、`test_dnd2024_weapon_hands.py`、
`combat/catalog.py`、`reducer.py`、`advancement.py`），并且它也在跑全量
（`E:/pytest-tmp/f38-full` 等）。它与本切片**重叠 4 个文件**：`combat/engine.py`、
`combat/resolution.py`、`features/resolver.py`、`combat/validation.py`。

因此：**本切片的改动与武器切片在 `git diff` 里无法按文件拆分，只能按 hunk 拆**；
在两条切片都落地之前，「全量绿」这个判据对任何一方都不成立。判定「是不是我弄坏的」必须拿
**同一边界**的树对照 —— 只含 HEAD 的基线树会把对面的改动误算成本切片的。

`-n 5 --dist loadfile` 下 `tests/test_launcher_lifecycle.py` 会因端口抢占失败。**已用基线工作树
`E:/tmp-s0f38-base` 逐棵对照**：串行跑两棵树各 `6 passed`，与改动无关。另外
`tests/test_ai_combat_choices.py::test_human_submission_enters_same_model_automation_boundary`
在基线上同样失败，也是既有问题。

## 8. 后续

1. **关闭兼容窗口**：下一版前端稳定后删掉 `target_id` 与 `targets` 两个旧字段（`_declared_target_ids` 与
   `_capability_projection` 里各一处）。
2. **预算型每人至少 1 点**：见 §7.6，改完再把投影上界收紧成 `min(合法数, 池子)`；
   同时补一个点数分配控件，替掉 §7.5 的显式挂起。
3. **迁移剩余特判**：`allocations` 已经能表达，但 `failed`（Cutting Words 之类）还没并进来；等
   「目标是正在掷骰的那个人」出现时按任务书 §2 停下来另开切片，**不允许为单个特性加字段**。
4. **2D 几何**：圈人、锥形、落点仍全部留给战术地图切片。

## 9. 拆分与提交边界

执行期间同一个工作树里躺着**三条**未提交的切片：S0-F38（武器词条与在手状态）、本切片、
以及 F20–F24 审核轮的残余修正。`git status` 显示 8 个文件被两条以上切片同时改过
（`MM`），所以无法按文件拆。为了让本切片能独立提交与评审，把它拆到独立工作树
`E:/w39`（分支 `feat/dnd2024-s0f39-target-selection`），**只带本切片的 hunk**。
拆分时先落在 `869eebf7`（当时唯一可用的栈顶），S0-F38 落地后重挂到 `34bb632b`，
见 §9.2。

| 文件 | 处理 | 说明 |
|---|---|---|
| `features/models.py`、`features/combat.py`、`content`/`en`/`zh-CN` 三个 `srd_class_features.json`、`api/types.ts`、`Dnd2024CombatPanel.vue`、`combatCopy.ts`、`test_dnd2024_target_selection.py`、本任务书与本报告、`S0F23_CHANNEL_CONTROL` §4 第 12 条 | 整文件 | 只为本切片存在 |
| `combat/view.py` | 2 个 hunk 全取 | `_capability_target_projection` / `_capability_budget` |
| `combat/validation.py` | 15 个 hunk 取 14 | 去掉「`move` 距离不再拒绝 0 尺」那一条（属别条切片） |
| `combat/engine.py` | 2 个 hunk 取 1 | 去掉 `_fresh_economy(conditions=...)`（光环抑制条件，属别条切片） |
| `combat/resolution.py` | 17 个 hunk 取 1 | 只留 capability 派发口的 `target_ids`→`target_id` 归一化 |
| `features/resolver.py` | 5 个 hunk 取 2 | 只留 `ability_modifier` import 与 `ability_modifiers` 投影入参；`SAVING_THROW_PROFICIENCY_ABILITIES` 属 F24 审核轮 |
| `test_dnd2024_channel_control.py` | 1 个 hunk | 「少选合法」的新用例 |
| `combat/reducer.py`、`progression/advancement.py`、`combat/hands.py`、`combat/catalog.py`、`srd_combat_core.json`、`srd_advancement_feats.json`、`test_dnd2024_weapon_hands.py`、`test_dnd2024_equipment_data.py` | 整文件排除 | 属 S0-F38 |

做法：对 `git diff`（工作区 vs 暂存区）按 hunk 取子集生成补丁，`git apply --3way` 落到基座树，
六份补丁全部 clean，无冲突。**不能按文件挑**：`engine.py`/`resolution.py`/`resolver.py`/`validation.py`
四个文件两边都有改动，按文件挑会把对面切片整段带进来。

拆分后在独立树上复验（这才是本切片自己的边界）：

- `ruff check src/`、`mypy`：干净（102 个源文件）。
- `tests/rulesets/test_dnd2024_target_selection.py`：**21 passed**。
- 邻接集（本文件 + `channel_control` / `channel_healing` / `class_features` / `bardic_inspiration` /
  `paladin_auras` / `overchannel`）：**302 passed / 0 failed**，776s。
- `tests/rulesets` 全量（`-n 5 --dist loadfile`）：**2426 passed / 0 failed**，1141s。
  这条取代 §6.3 那两次带混合工作树的全量：在只有本切片的树上，ruleset 层没有任何失败。
- §6.4 那条 `test_a_ranged_weapon_cannot_be_imbued` 在本树**通过** —— 反过来证明它确实由 S0-F38
  的「盾牌挡双手」检查引起，与「上界只留一处算法」的改动无关。
- 前端只改了三处注释里的编号（`S0-F38` → `S0-F39`，`types.ts` 两处、`Dnd2024CombatPanel.vue` 一处），
  类型面无变更，`vue-tsc` / `eslint` 结论沿用 §6。

由此更正 §7.9 的一句话：「全量绿对任何一方都不成立」只对**混合工作树**成立；拆出独立树之后，
本切片可以单独跑全量，只是耗时 12 分钟以上（本机 7 个文件就 776s）。

### 9.1 拆分不是复制：共享工作树里已撤出本切片

拆分的是**归属**，不是留一份副本。S0-F38 在拆分后落成 `1d6709c6`（词条与在手状态）与
`34bb632b`（遭遇结束清握持）两提交，此后原件工作树
（`C:/Users/Administrator/WorkBuddy/Worktrees/diceframe/main-2895e7de`）里的本切片内容已按同样
的 hunk 边界**反向撤出**：

- 8 个「只为本切片存在」的文件 `git checkout --` 回 F38 提交态；
- 6 个重叠文件 `git apply -R` 反向应用同一批补丁（六份全部 RECALLED，无冲突）；
- 本任务书、本报告、`test_dnd2024_target_selection.py` 三个未跟踪文件删除（已在分支里）。

撤出后该树 `git diff` 里 `target_cap` / `target_candidates` / `_declared_target_ids` /
`resolve_target_cap` / `budget_split` 的命中数为 **0**，`ruff check src/` 仍通过；剩下的改动只有
F20–F24 审核轮的残余修正，与两条切片都不再重叠。撤销前的完整工作区差异存于
`E:/tmp-split/shared-before-revert.patch`（2734 行），可完整还原。

### 9.2 提交顺序：重挂到 S0-F38 之后

拆分时 F38 还没提交，本切片只能落在 `869eebf7`。F38 落成 `1d6709c6` + `34bb632b` 之后，
栈就变成了「F39 跨在 F38 下面」——语义上是反的：目标选择用到的 `capability` 投影与 F38 的
在手状态没有依赖关系，但 F39 的补丁是在 F38 的工作区上验证过的，两边若各自合入 `main`，
谁先谁后都会让另一条 PR 的 merge-base 乱掉。

因此把 F39 重挂到 F38 之后（`git rebase 34bb632b`）。**这一步可以证明是无冲突的**，不是运气：
六份拆分补丁的 `index` 旧 blob（`498c196a`/`1abe1507`/`5bd9e627`/`59d53019`/`974d9f8d`/`bbcfc67b`）
与 `34bb632b` 里对应文件的 blob **逐一相同**——补丁本来就是对着这份内容生成的，rebase 只是
把它按同一个上下文再应用一次。

rebase 后核对两件事：

1. `git diff --stat 34bb632b HEAD` 仍是 18 个文件 `+1879 / −73`（净差异没变）；
2. `git diff 72fb732f HEAD`（rebase 前后）恰好是 F38 的 15 个文件 `+1595 / −65`，
   即只多了 F38，没多也没少本切片的内容。

### 9.3 重挂之后两棵树都全绿

| 树 | 基座 | `tests/rulesets` 全量 |
|---|---|---|
| F39-only（拆分当时） | `869eebf7` | 2426 passed / 0 failed，1141s |
| F39 重挂后（含 F38） | `34bb632b` | **2459 passed / 0 failed**，1162s |

差的 33 条正是 S0-F38 自带的 `test_dnd2024_weapon_hands.py` 与 `test_dnd2024_equipment_data.py`。
两棵树分别全绿，说明「顺序」只是 commit 图的问题、不是内容耦合：本切片不依赖 F38 的代码，
也不会因为 F38 在场而改变行为。`ruff check src/` 与 `mypy` 在重挂后的树上同样干净。

也就是说：**先合 F38 还是先合 F39 都不影响正确性**；重挂只是为了让栈线性、让两条 PR 的
merge-base 各自干净（也省掉评审时「这条 PR 为什么带着别人的 15 个文件」这一问）。


