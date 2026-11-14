# S0-F19 停工报告：Hunter 子职的两个模型缺口

日期：2026-11-14
分支：`feat/dnd2024-s0f19-hunter`（叠在 `feat/dnd2024-s0f18-hunters-mark@8830bdd6` 之上）
基线：`8830bdd6`（F18 链头，尚未推送）
范围：`hunters_lore`、`hunters_prey`（Colossus Slayer / Horde Breaker）、`defensive_tactics`（Escape the Horde / Multiattack Defense）、`superior_hunters_prey`、`superior_hunters_defense`

---

## 1. 结论

**整切片停工，零代码改动。**

五项特性里有两项的前提在代码里没有任何权威来源，且各自单独触发任务书的停止条件：

| 缺的东西 | 被卡住的特性 | 停止条件 |
| --- | --- | --- |
| 怪物/敌人档案没有 Immunities / Resistances / Vulnerabilities | `hunters_lore`（3 级） | §7.2.2 明确写"没有真实…或无法做席位级私有投影"即停止 |
| 休息时替换特性选项没有通用入口 | `hunters_prey`、`defensive_tactics` 的"每次短休或长休可替换" | §5 末句"需要修改休息通用服务…时停止" |

关键点：**这不是"少两个载体"**。`hunters_lore` 是 3 级同时授予的两项之一，`hunters_prey` / `defensive_tactics` 的选项替换是 SRD 原文写进特性描述里的行为（"Whenever you finish a Short or Long Rest, you can replace the chosen option with the other one"）。§9.4 要求"不得把非目标或 guided 情报描述写成已自动化"，§7.2.5 又禁止"省略任一子效果才能交付"，因此本切片没有"先做能做的部分再补"这条路——那样交付的是一份以特性名注册、但行为与 SRD 不符的 Hunter。

这与 F16（法术修饰）、F17（Cunning Strike）停工的成因相同：任务书假设的祖先基线 `integration/dnd2024-srd@35653f81` 比当前 main 多出若干前置层，而切片顺序把"模型前置"排在了消费者之后。三份任务书都没有写错，缺的是被消费的模型。

---

## 2. 停止项一：Hunter's Lore 没有权威防御数据

SRD p61 原文要求向标记拥有者揭示目标真实的 Immunities / Resistances / Vulnerabilities，§4.2.2 要求"三组具体 canonical 类型列表，并区分 damage 与 condition 条目"，§4.2.3 要求"数据来自服务端 enemy stat block，不从客户端 payload 或公开名称推断"。

### 2.1 事实

**（一）契约层不接受防御字段。**

`src/rulesets/dnd2024/content/contracts.py:108` 的 `_monster_mechanics` 是怪物与 NPC 唯一共用的机制装配函数，返回的键是固定的：

```python
return {
    **({"creature_type": creature_type} if creature_type else {}),
    "hp": ..., "armor_class": ..., "speed": ...,
    "abilities": ..., "attacks": ...,
}
```

`validate_monster_profile`（`contracts.py:122`）与 `validate_npc_statblock`（`:156`）各自声明 `allowed` 字段集，均不含任何防御键；未知字段在 `contracts.py:133` 直接抛 `CatalogContractError("monster profile has unknown field: …")`，`content/catalog.py` 只是把这个校验按 kind 分发。也就是说：**即便有人往模块 JSON 里手写 `resistances`，加载期就会被拒绝**，不存在"数据其实存在只是没人读"的可能。

**（二）数据层一个防御字段都没有。**

全仓 `templates/` 下带 `profile_id` 的文件只有两份，字段整齐划一：

- `templates/rulesets/dnd2024_srd/presets/encounters/srd_training_encounters.json`：`goblin_warrior`、`skeleton`、`wolf`
- `templates/adventures/lanterns_of_greymoor/content/encounters/greymoor_encounters.json`：`goblin_minion`

两者的 profile 键全是 `{profile_id, id, name, hp, armor_class, attacks, abilities, saving_throws, initiative_modifier, position, speed}`。`grep -rln "damage_resistances\|resistances\|immunities" templates/` 只命中 `srd_class_features.json` 里玩家特性自己的 `resist_damage_types` 声明。

值得单独写一笔：预设里的 `skeleton` 在 SRD 里是 Bludgeoning 易伤，但它在这份数据里连一个能放易伤的字段都没有。这不是数据填得粗，是模型里没有这一维。

**（三）view 层不投影，也无法投影。**

`combat/view.py:96` 装配敌人视图时读的是 `hp`、`max_hp`、`armor_class`、`speed`、`abilities`、`saving_throws`、`creature_type`；没有防御组。`combat/visibility.py` 的模块注释写明"monster stat blocks are GM-only"，即已有的私有化只做到"整份档案对玩家隐藏"，没有做到"某一组字段对某一个席位公开"。

**（四）敌人 intent 是客户端提交的，不能当权威。**

`combat/validation.py:68` 的 `validate_enemy_profiles` 只校验身份、hp/ac/speed/位置/先攻与攻击档案，**不拒绝未知键**。所以 `{"id": "skeleton", "resistances": {...}}` 这样的 payload 会被原样接受——这恰恰是 §4.2.3 与 §6.23 禁止的来源：由发起战斗的一方决定"目标抗什么"。

### 2.2 三种绕法都不成立

- **给 `contracts.py` 加字段**：`content/contracts.py` 不在 §5 白名单（白名单只有 class feature catalog、locale、`features/resolver.py`、六个 combat 模块、`runtime.py`、新建测试与本文件）。§7.2.5 直接写"需要修改白名单外文件…时停止"。
- **从 enemy dict 读**：这就是客户端伪造。§4.2.3 明说不得从客户端 payload 推断，§6.23 明说客户端伪造防御情报必须被拒绝或忽略。
- **按名称或 `creature_type` 推断**（skeleton → Bludgeoning）：§7.1 非目标禁止"从公开名称推断"，而且 `creature_type` 只有类型（undead），推不出易伤。

### 2.3 影响面

§4.2.2 的最后一句是"缺真实防御字段时停止，不把空列表当作'目标没有'"。当前状态正是"缺真实防御字段"，所以 Hunter's Lore 不是"部分可用"，而是**在数据补齐前永远不可用**：任何返回都会是空列表或猜测，两者都被任务书点名禁止。

对应矩阵项：**4、5、25**（以及 §4.2.4 的 `dnd2024.hunter_lore.revealed` 事件、席位级投影、feed 防泄漏三件事）。

---

## 3. 停止项二：休息时替换选项没有通用入口

§4.1.3 要求："每次完成短休或长休可分别替换当前选项，未提交替换则保持不变。每次休息每组最多替换一次，不接受非法 id、越权 owner 或战斗中替换。"

### 3.1 事实

**（一）选项本身已经有主干。**

`features/models.py:46` 的 `FEATURE_CHOICE_KINDS` 已含 `feature_option`，`features/resolver.py:1296` 有 `feature_option_choice()`，内容侧有现成先例——Cleric 的 `blessed_strikes`（`srd_class_features.json:1386`）用 `choice.kind = "feature_option"` + `enabled_options: ["feature:divine_strike", "feature:potent_spellcasting"]` 声明，两个子选项用 `option_of: "blessed_strikes"` 挂回。所以"建卡/升级时选一个选项"这条路是通的，Hunter 的两组选项可以照抄形状。

**（二）但"休息时替换"没有接入口。**

休息的两个入口签名是封闭的：

- `src/rulesets/dnd2024/resting/engine.py:268` `complete_short_rest(payload, hit_die_rolls, attunement, free_cast, recovery, fiendish_resilience)`
- `src/rulesets/dnd2024/runtime.py:845` `complete_rest(rule, character, rest, hit_die_rolls, attunement, land_terrain, free_cast, recovery)`

除 `fiendish_resilience`（Warlock 的抗性改选，写在 `character.conditions` 之外的一处专用状态）外，其余都是**为某一个特性单独开的专线**，没有"按 `(owner, feature_id, choice_id)` 重写一条 `feature_choices`"的通用操作。`grep -rn "rest_choice\|replace_on_rest\|reselect" src/` 为空。

`features.feature_choices` 只有两个写入点：建卡（`character/derivation.py` 的 `plan_skill_choices` 路径）与升级（`runtime.apply_advancement` → `_sync_class_resources` 附近的答案合并）。休息侧没有任何一处会碰它。

### 3.2 为什么不能将就

- **只在建卡时选一次**：等于删掉 SRD 写在该特性描述里的那一句。§4.3 的 Colossus Slayer 与 Horde Breaker 是互斥选项，选错一次就永久锁死，这已经不是"行为近似"，是"少一条规则"。
- **把替换塞进 `runtime.complete_rest`**：`runtime.py` 在白名单内，但只授权"私有情报及 feed 防泄漏"。休息语义（谁能替换、每段休息每组一次、战斗中拒绝）属于"休息通用服务"，§5 末句点名那类文件需要停工时即停。

### 3.3 影响面

对应矩阵项：**3**（短休替换 Prey 而不改 Tactics、长休替换后者、不提交则保持、战斗中请求被拒绝）。同时 §4.1.4 的"战斗投影只读休息后的有效选项"也依赖它——没有替换就没有"休息后的有效选项"这个新状态。

---

## 4. 逐项可行性核对（§6 的 26 条）

即使停工，26 条也已逐项核到落点。**"可行"只代表在白名单内做得出来，不代表本次做了**；本次零改动。

### 4.1 授予与选项

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 1 | 2 级无特性；3 级 Lore/Prey；7/11/15 依次；非 Hunter 不获得 | 可行 | 子职表已按 3/7/11/15 列好（`srd_subclasses.json:54`）；`features/resolver.py:353` 的 `_owned_feature_definitions` 只在 `features.subclass_ref` 指向该子职时授予。缺的只是 catalog 里那 5 条声明本身 |
| 2 | 两组选项非法值/跨 owner/伪造 fail closed；中英文 source_ref 一致 | 可行 | `_choice_ref_is_valid`（`resolver.py:1096`）逐 ref 对照 `enabled_options`；`blessed_strikes` 是可直接照抄的先例；locale 结构同 F18 已处理过的 `class_feature_catalogs` |
| 3 | 短休替换 Prey / 长休替换 Tactics / 不提交则保持 / 战斗中拒绝 | **停止** | 见 §3 |

### 4.2 Lore

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 4 | 三组具体类型而非布尔；未标记与标记结束后不可见 | **停止** | 见 §2：无数据即无三组列表可返回 |
| 5 | 转移后旧目标撤回、新目标出现；公共 feed 不含列表 | **停止** | 撤回逻辑本身可读 `concentration.mark_target_id`（F18 已落），但没有列表可撤 |
| 25 | 公共 feed 无 Lore 列表；save/load 后权限不扩张 | **停止** | `runtime.py::_recent_combat_events` 的字段白名单在内，但没有字段可过滤 |

### 4.3 Colossus Slayer（7 级前 3 级选项 A）

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 6 | 受伤目标 +1d8，满血不触发；类型、rolls、来源正确 | 可行 | `_hit_rider_declarations`（`resolution.py:1326`）是所有命中 rider 的集中装配点——虽然每条 rider 各有分支（`radiant_strikes`/`divine_strike`/`primal_strike`/`_attack_state_riders`），"声明挂到 `damage_event["hit_riders"]`、提交时才掷"的形状是共用的；`hp < max_hp` 两侧都可读（敌人 `view.py:96` 有 `max_hp`，无预设时 `resolution.py:270` 用 `max_hp = hp`）；伤害类型取本次武器的 `damage_type`，作为独立实例与 F14/F18 同形（抗性只作用于这一份） |
| 7 | 同回合第二次命中不再加；下回合恢复；未命中/被改判不消耗 | 可行 | `_feature_used_this_turn`（`resolution.py:3137`）按 `(actor, round, turn_index)` 记账；声明阶段先挂 `damage_event["hit_riders"]`、提交时才掷（`resolution.py:1282`），Shield/Uncanny Dodge 改判时骰子不会被白掷 |

### 4.4 Horde Breaker（3 级选项 B）

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 8 | 同一武器、不另扣动作、完整管线只走一次 | 可行但需新账本 | `_attack_events(..., spend_attack_action=False)` 已存在（`resolution.py:3389` 的 Flurry 先例）；**但不能走 `class_capability` 通道**：`ACTION_COST_KINDS`（`models.py:35`）只有 `bonus_action/action`，无法表达"不额外支付动作"，而 `ACTION_KINDS`（`:28`）也没有"武器攻击"这一类，两者都在白名单外的 `features/models.py`。可行路径是把第二目标挂在同一个 `attack` 意图的字段上 |
| 9 | 同目标/距原目标 6 尺/超射程/本回合已攻击过 → 不可选 | 可行但需新账本 | 距离与射程可算；**"本回合已攻击过"完全没有账本**：`grep -rn "attacked\|attack_targets"` 在 `combat/*.py` 为空，`combat["feature_usage"]` 只记特性名不记目标。需要新增一个按 `(actor, round, turn_index)` 记录目标集的键（`engine.py:141` 的 `initialize_state` 在白名单内，可行） |
| 10 | 每回合一次，下回合重置；他人回合的借机攻击不能触发 | 可行 | 借机攻击由 `resolution.py:4214` 自行拼 `attack_intent`，不带 Horde 字段即天然触发不了；账本按 `(round, turn_index)` 隔离 |

### 4.5 Defensive Tactics

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 11 | 借机攻击劣势；普通攻击与 RNG 不变；多来源不增骰 | 可行 | 借机攻击走 `_attack_events`（`resolution.py:4224`），攻击模式由 `check_modes.attack_mode`（`check_modes.py:281`）聚合来源；需给 `_attack_events` 加一个"这是借机攻击"的参数并透传，两文件都在白名单；`mode_from_sources` 本来就把多来源压成单次劣势 |
| 12 | 第一击不追溯；第二击起劣势；其他攻击者/下回合不受影响 | 可行但需来源化条件 | 没有"某攻击者本回合命中过你"的账本。可行做法是给防守者挂一条带 `source_actor_id + round + turn_index` 元数据的条件（`reducer.py:568` 的 `condition.applied` 接受任意 id 与元数据），再由 `check_modes` 读元数据；时限可落在 `_TURN_SCOPED_DURATIONS`（`reducer.py:49`）已有取值上。**未决**：哪一档时长精确对应"该攻击者的本回合结束"，需在实现时对照 `engine.py:1973-2006` 的移除时机逐档核对 |

### 4.6 Superior Hunter's Prey（11 级）

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 13 | 30 尺内可见第二目标独立结算一枚标记骰（1d6 或 Foe Slayer 1d10），不含武器与其他 rider | 可行 | 骰面由 F18 的 `_mark_damage_die()` 回答（读 `foe_slayer.mark_damage_die` 覆盖印刷的 d6），伤害实例由 `_rider_damage_event()` 装配，两者都不碰武器骰；可见性用 F18 的 `observer_senses(distance=...)` |
| 14 | 31 尺/不可见/同一目标/无有效标记/第一目标未受伤 → 不结算 | 可行 | 距离、可见性、`concentration.mark_target_id`、目标 `hp` 都可读；拒绝发生在 validation |
| 15 | 每回合一次；两目标分别算抗性/HP/专注/击败；RNG 顺序稳定 | 可行 | `_feature_used_this_turn` 记账；两个伤害实例各自过 `_resist_damage`（`resolution.py:576`）；RNG 顺序 = 第一目标既有结算之后追加一枚 |

### 4.7 Superior Hunter's Defense（15 级）

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 16 | 支付反应后触发伤害减半一次，后续同类型也减半 | 可行 | F11 的反应窗在伤害落地前拿到 `damage_event`（`reaction_spells.py:111` 的 `_reaction_feature_choices`）；`_resist_damage` 已支持从条件元数据读 `resist_damage_types`（`resolution.py:578-588`），所以"持续到回合结束的同类型抗性"可以是一条带元数据的条件，不需要动条件注册表 |
| 17 | 不同类型不减免；回合结束恢复；下回合可再反应 | 可行 | 元数据按类型匹配；`_TURN_SCOPED_DURATIONS` 提供回合级移除 |
| 18 | 反应不足/放弃/无正数伤害 → 不扣不写；多来源不叠加成四分之一 | 可行 | `_reaction_eligible` 与 `REACTION_FEATURE_EFFECTS`（`reaction_spells.py:27`）的守卫形状可复用；`_resist_damage` 的"第一个匹配即返回"保证只减半一次 |
| 19 | 多类型伤害未拆分且无明确选择时 fail closed | **无适用情形** | 引擎里每个伤害实例只有一个 `damage_type`（见 `damage_event["damage_type"]` 的全部构造点），多类型本来就拆成多条实例。§4.4.6 假设的情形在当前模型里不存在，实现时应断言"类型唯一"而不是造一条拆分逻辑 |

### 4.8 通用项

| # | 内容 | 判定 | 落点与依据 |
| --- | --- | --- | --- |
| 20 | 低等级/非 Hunter/已替换掉的旧选项不产生 rider 或反应窗 | 可行 | `has_feature` 按 owner+等级判定；旧选项不残留取决于 §3 的替换是否独占写入 |
| 21 | resolve_intent → apply_batch 后重放一致 | 可行 | 与 F18 矩阵 21/22 同形，已有写法 |
| 22 | 存档后 Lore 权限/选项/每回合使用/持续抗性保持 | 部分停止 | 选项与账本可存；Lore 权限无对象可存（§2） |
| 23 | 客户端伪造第二目标/情报/额外骰/反应类型均被拒 | 可行 | validation 已有的"服务端权威"边界；情报这一项随 Lore 停 |
| 24 | 既有 Hunter's Mark / Sneak Attack / Uncanny Dodge / Divine Smite 无回归 | 可行 | 无改动即无回归，但按 §8 仍需跑 |
| 26 | 既有 combat / class features / resting / rage / monk / F11 通过 | 可行 | 同上 |

统计：**26 条里 20 条可行、4 条停止（3、4、5、25，分属两处停止项）、1 条无适用情形（19）、1 条部分停止（22）**。

---

## 5. 为后续切片留下的核实结果

1. **`feature_option` 主干已存在，Hunter 的选项不必新建机制**：`models.py:46`、`resolver.py:1296`、`blessed_strikes` 先例（`srd_class_features.json:1386` + `option_of` 子项）。这是 F19 里唯一"看起来要造轮子其实不用"的部分。
2. **特性能力通道（`class_capability`）不适合表达"不花动作的攻击"**：`ACTION_COST_KINDS = ("bonus_action", "action")`（`models.py:35`），`ACTION_KINDS` 也没有武器攻击类（`:28`），且 `features/models.py` 与 `combat/primitives.py` 都不在白名单。Horde Breaker 与 Superior Prey 只能搭 `attack` 意图的附加字段。
3. **`INTENT_TYPES` 是闭集**（`primitives.py:30`，含 `class_capability`），新增意图类型需要白名单外的文件；这决定了"第二目标"必须作为既有意图的一个字段出现，而不是一个新意图。
4. **敌人没有防御维度，且契约层不接受**：`contracts.py:108/127`。补这一维要同时改契约、两份预设/冒险包数据、`view`/`visibility` 的席位私有化，属于独立前置切片。
5. **休息侧只有四条专线**（`land_terrain`/`free_cast`/`recovery`/`fiendish_resilience`），`feature_choices` 只在建卡与升级写入。通用替换入口是独立前置。
6. **条件自带元数据通道已经够用**：`condition.applied` 接受任意 id 与附加键（`reducer.py:568`），`_resist_damage` 会读元数据里的 `resist_damage_types`（`resolution.py:578`），`_TURN_SCOPED_DURATIONS` 提供六档回合级移除（`reducer.py:49`）。Multiattack Defense 与 Superior Defense 的持续状态因此不需要动条件注册表（`srd_combat_core.json` 虽然也在白名单外，但不必动）。
7. **每回合账本的形状是 `combat["feature_usage"][actor_id] = {round, turn_index, features}`**（`resolution.py:3137`），只记特性不记目标。凡是"本回合还没打过这只生物"这类判定，都需要先扩这个账本。

---

## 6. 白名单文件对照

| §5 条目 | 是否改动 |
| --- | --- |
| `class_feature_catalogs/srd_class_features.json` | 未改 |
| `locales/en`、`locales/zh-CN` 的 class feature catalog | 未改 |
| `features/resolver.py` | 未改 |
| `combat/resolution.py`、`check_modes.py`、`reaction_spells.py`、`reducer.py`、`validation.py`、`view.py` | 未改 |
| `runtime.py` | 未改 |
| 新建 `tests/rulesets/test_dnd2024_hunter.py` | 未建 |
| 本任务书 / 执行报告 | 只新增本文件 |
| 白名单外文件 | 未改 |

`git diff --check` 无输出；本分支相对 `8830bdd6` 只有本文件。

---

## 7. 门禁

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 新增用例 | `pytest tests/rulesets/test_dnd2024_hunter.py -q` | 未执行（文件未建） |
| 聚焦回归 | `damage_reactions / uncanny_dodge / smite / combat / resting` | 未执行（无改动可回归） |
| 全量 | `pytest tests/rulesets -q` | 未执行 |
| ruff | `ruff check ...` | 未执行 |
| `git diff --check` | — | 干净 |

零改动的切片跑回归没有归因价值。基线状态见 F18 报告 §6：`tests/rulesets` **2019 passed / 11 failed**，11 条全部是 `test_dnd2024_character_builder.py` 的 `unresolved reference 'ability:con' in background:soldier`（已用 `git stash` 证明与本切片无关）。

顺带一条：§8 指定的 `tests/rulesets/test_dnd2024_damage_reactions.py` 在仓库里不存在——F11 的伤害反应测试实际分散在 `test_dnd2024_uncanny_dodge.py` 与 `test_dnd2024_smite.py`。解除停工时应按真实文件名跑，而不是照抄任务书里那个路径。

---

## 8. 建议的解除路径

三步，每一步都能独立验收，且都不与 F19 的验收载体重叠：

**第一步（前置切片，建议编号 F19-pre）**：给 monster / npc_statblock 增加 `immunities` / `resistances` / `vulnerabilities` 三组字段（damage 与 condition 分开），把预设与冒险包里的怪物补上真实数据，并给出"某一组字段只对一个席位可见"的投影。停止条件：SRD 原文与数据无法一一对应时停止，不拿空列表冒充"没有"。

**第二步（F19a）**：`hunters_prey` / `defensive_tactics` 的选择（建卡与升级）+ Colossus Slayer + Horde Breaker + Escape the Horde + Multiattack Defense + Superior Hunter's Prey + Superior Hunter's Defense。这一批全部落在现有白名单内，唯一的新状态是"本回合攻击过哪些目标"的账本。

**第三步（F19b）**：在休息通用服务里加通用的 `feature_option` 替换入口（按 `(owner, feature_id, choice_id)` 独占重写，每组每段休息一次，战斗中拒绝），然后把 Hunter's Lore 接上第一步的投影。

这样 F19 的 5 项特性、26 条矩阵会分别落在三个可评审的切片上，而不是一份"看起来完成、实际少两条规则"的交付。

---

## 9. 偏差与未决

1. **偏差**：无。零代码改动。
2. **未决（一）**：`combat["feature_usage"]` 目前只按 `(actor, round, turn_index)` 记特性名。Horde Breaker 需要"本回合攻击过哪些目标"，Multiattack Defense 需要"某攻击者本回合是否命中过我"。两者都能扩这个账本，但扩法不同（一为目标集、一为攻击者集），应在 F19a 开工前统一定形状，避免两份平行账本。
3. **未决（二）**：Multiattack Defense 的时限要落在 `_TURN_SCOPED_DURATIONS` 的哪一档尚未确定。六档（`actor_turn_start`、`target_turn_start`、`caster_turn_end`、`caster_next_turn_end`、`after_next_attack`、`attacker_next_turn_start`）里没有字面上的"当前回合结束"，`engine.py:1973-2006` 的移除时机需要逐档对照后才能选，不能凭名字猜。
4. **未决（三）**：`hunters_prey` 的选项若在建卡时未作答，`feature_option_choice` 返回空串、任何 rider 都不授予（fail closed）。这是可接受的安全默认，但需要在 F19a 里明确"未作答的 Hunter 在 3 级既没有 Colossus 也没有 Horde"这一可观测行为，并让建卡预览要求作答，否则玩家会得到一只两个选项都没有的 Hunter。
5. **系统性观察**：F16、F17、F19 连续停工同源——被消费的模型（区域几何、物品/尺寸/掩蔽、怪物防御、休息选项替换）没有对应的前置切片。建议在 F20 之后先做一次"前置模型盘点"，把 F21–F37 各自依赖的模型缺口列出来，否则后续切片会继续在同一个位置停下。
