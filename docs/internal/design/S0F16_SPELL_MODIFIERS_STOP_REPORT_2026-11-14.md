# S0-F16 停工报告：法术学派、职业与伤害类型修饰

日期：2026-11-14
分支：`feat/dnd2024-s0f16-spell-modifiers`（叠在 `feat/dnd2024-s0f15-attack-state@cfea2e26` 之上）
基线：`cfea2e26`
范围：Evoker `potent_cantrip` / `sculpt_spells` / `empowered_evocation`，Draconic `elemental_affinity`

---

## 1. 结论

**整切片停工，零代码改动。**

四项验收载体里有两项在当前基线上没有可验收的落点，且都属于任务书自己列出的停止条件：

| 载体 | 停止条件 | 缺的东西 |
| --- | --- | --- |
| Sculpt Spells | §4.3.5、§7.2 | 服务端权威的"本次 Evocation 实际影响哪些生物"，需要 Cone/Cube/Sphere 几何 |
| Elemental Affinity | §7.4 | 固定选择的 canonical 持久化边界 |
| Potent Cantrip | 无 | 机制可做（miss 分支目前直接跳过掷骰） |
| Empowered Evocation | 无（但需定义"一次 damage roll"选择器） | 每目标一个伤害事件，缺 roll 级标识 |

按 §1.4「Sculpt Spells 若需要当前不存在的 AoE 几何/区域成员模型，必须停止整个切片验收」与 §9.3「若停止，整个切片不得标为完成」，停工是整切片而不是逐项跳过。剩余两项不是不可行，是随整切片一起停：留下 Potent + Empowered 会让 §9.1「测试 1–22 逐项映射」永久缺 6–10 与 13–16 两组，交付一个自称完成但矩阵残缺的切片，比停工更难对账。

## 2. 停止项一：Sculpt Spells 没有权威受影响集合

### 2.1 事实

`templates/rulesets/dnd2024_srd/content/combat_catalogs/srd_combat_core.json` 共 45 条 `spell_effects`，全部字段的并集为：

```
add_spell_ability, armor_class_bonus, concentration, condition, condition_duration,
damage, damage_type, damage_type_choice, ends_on, extra_damage,
extra_damage_creature_types, half_on_success, healing, mode, push, range,
removes_conditions, repeat_targets, resist_choice, save, save_repeat,
target_count, target_creature_types, target_scope, temp_hp, trigger,
upcast_damage, upcast_flat, upcast_healing, upcast_target_count
```

没有 `area`、`radius`、`cone`、`cube`、`sphere`、`line`、`emanation` 任何一档。`target_scope` 只有 `self` 一个值（`blur` / `false_life` / `fire_shield` / `misty_step` / `see_invisibility`），不表达区域。

目标契约是显式列表，数量来自 `target_count`，缺省为 1（`src/rulesets/dnd2024/combat/validation.py:1126`）：

```python
required_count = int(effect.get("target_count", 1) or 1)
```

于是三个真正的区域法术在目录里都退化成"玩家自选一个目标"：

| 法术 | SRD 区域 | 目录声明 |
| --- | --- | --- |
| `burning_hands` | 15 尺锥 | `mode=saving_throw, save=dex, half_on_success=true, target_count=null` |
| `thunderwave` | 15 尺立方 | `mode=saving_throw, save=con, half_on_success=true, target_count=null` |
| `acid_splash` | 5 尺半径球 | `mode=saving_throw, save=dex, half_on_success=null, target_count=null` |

`combat/view.py:481 _available_spells` 也只投影 `target_count` / `upcast_target_count` / `repeat_targets`，没有区域可投影。

### 2.2 为什么不能将就

§4.3.5 原文禁止"仅按施法 range、target_ids 或敌我列表近似"。当前 `target_ids` 恰好就是这三样：客户端提交、服务端只校验数量/重复/阵营/射程。用它当"受影响集合"，Sculpt 就变成了"玩家提名谁被保护"——而规则里被保护的前提是**已经被区域覆盖**，不是**玩家想保护**。差别在反例上立刻可见：一个不在锥形内的盟友，在近似模型里可以被提名并自动成功豁免。

§4.3.6 留的窗口（"前置已提供显式、可验收的受影响目标集"）在当前基线里没有任何法术满足：能显式枚举目标的法术全是单体，而单体法术的 Sculpt 效果只有"省一颗 d20"，值不起一个切片的验收风险。

## 3. 停止项二：Elemental Affinity 的固定选择没有 canonical 落点

### 3.1 事实

固定选择唯一可用的存储是 `features.feature_choices`（`combat/view.py:449` 透传，`features/resolver.py:1245` 读取）。但写入侧只认两种 kind：

- `features/models.py:46`：`FEATURE_CHOICE_KINDS = {"advancement_feat", "skill_proficiency", "feature_option"}`
- `progression/advancement.py::_plan_feature_choices`：只对 `skill_proficiency` 与 `feature_option` 分支，其余 kind 既不产出 requirement 也不产出 record
- `character/derivation.py::plan_skill_choices`：只收集 `skill_proficiency`，末尾把任何未匹配的提交记录直接判错

第三处是硬约束。`character/derivation.py:370` 起：

```python
for index, record in enumerate(submitted):
    if index in matched:
        continue
    errors.append(
        "feature choice references a slot this character does not have: "
        f"{record['owner']}/{record['feature_id']}/{record['choice_id']}"
    )
```

也就是说，即便升级时设法写进一条 `damage_type` 记录，下一次 `derive` 就会把整张卡判成非法。

### 3.2 需要改的文件与白名单的关系

| 文件 | 需要做的事 | 是否在 §5 白名单 |
| --- | --- | --- |
| `features/models.py` | 新增 `damage_type` kind、category 与 ref 前缀规则 | 在（§5.3） |
| `progression/advancement.py` | 新 kind 的 requirement、record 与合法性校验 | **不在** |
| `character/derivation.py` | `plan_skill_choices` 按 kind 分流，不再把未知 kind 判成"没有这个槽" | **不在** |

三处里两处在白名单外，正是 §7.4 描述的"固定选择缺少 canonical 持久化边界"。绕开的办法只剩让客户端每次提供（违反 §4.4.3"不能每次休息/施法改选"），或用 `feature_option` 造五个假特性代表五种类型（把 damage type 塞进 `feature:` 命名空间，等于让命名承担语义，也违反 AGENTS.md"不要把 display name 当作 canonical identity"）。

## 4. 测试矩阵映射状态（§6 的 22 条）

全部**未执行**，且未执行不等于通过。

| # | 内容 | 状态 | 原因 |
| --- | --- | --- | --- |
| 1 | 四项特性授予等级、子职、source_ref、双语标签 | 未执行 | 特性未落地 |
| 2 | Potent：攻击 miss 半伤向下取整，命中全伤 | 未执行 | 机制可做，随切片停 |
| 3 | Potent：save 成功半伤、失败全伤、非伤害戏法与 1 环不触发 | 未执行 | 同上 |
| 4 | Potent 半伤分支不附加条件/位移/区域 | 未执行 | 同上 |
| 5 | 多目标戏法逐目标判断，抗性/Evasion 不重复减半 | 未执行 | 同上 |
| 6 | Sculpt 只匹配 Evocation，无权威集合不提供 | 未执行 | 停止项一 |
| 7 | 保护数 1+level，超额/重复/自己/不可见拒绝 | 未执行 | 停止项一 |
| 8 | 被选者自动成功且不消耗 d20，未保护者 RNG 不变 | 未执行 | 停止项一 |
| 9 | 原成功豁免的非伤害效果不被擅自移除 | 未执行 | 停止项一 |
| 10 | Sculpt 的 AoE 门槛有明确验收或明确停止 | 已执行 | 本报告 §2 即该项交付物 |
| 11 | Empowered 只对 Wizard+Evocation 加 Int | 未执行 | 随切片停 |
| 12 | 多束/多目标只加一次，负 Int 按真实值 | 未执行 | 随切片停 |
| 13 | Elemental 固定选择仅五类，伪造与改选拒绝 | 未执行 | 停止项二 |
| 14 | 固定抗性跨战斗/升级/休息/存档保持，只减半一次 | 未执行 | 停止项二 |
| 15 | 任意职业 spell 造成所选类型可加 Cha | 未执行 | 停止项二 |
| 16 | 混合类型不串类型，多 roll 仅一次 | 未执行 | 停止项二 |
| 17 | Empowered 与 Elemental 同时命中的结算 | 未执行 | 依赖 11、13 |
| 18 | 客户端伪造加值/保护/自动成功/抗性被拒 | 未执行 | 依赖前置 |
| 19 | 可选加值的 pending、decline、重复 resolve、过期 version | 未执行 | 依赖前置 |
| 20 | apply/replay 的 RNG、豁免、伤害一致；feed 只暴露白名单字段 | 未执行 | 依赖前置 |
| 21 | 非持有者、低等级、既有修饰不回归 | 未执行 | 依赖前置 |
| 22 | 既有法术、Scorching Ray、Overchannel、Hold Person、抗性回归 | 未执行 | 依赖前置 |

第 10 条是本切片唯一"完成"的一项，它就是本报告存在的理由。

## 5. 白名单文件对照

| §5 条目 | 是否改动 |
| --- | --- |
| canonical class feature catalog 及 en / zh-CN locale | 未改 |
| `combat/resolution.py`、`validation.py`、`reducer.py`、`runtime.py` | 未改 |
| `features/resolver.py`、`features/models.py` | 未改 |
| `spells/catalog.py` | 未改 |
| `combat_catalogs/srd_combat_core.json` | 未改 |
| 新建 `tests/rulesets/test_dnd2024_spell_modifiers.py` | 未建 |
| 白名单外文件 | 未改 |

`git diff --check` 无输出；本分支相对 `cfea2e26` 只有本文件。

## 6. 门禁

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 新增用例 | `pytest tests/rulesets/test_dnd2024_spell_modifiers.py` | 未执行（文件未建） |
| 聚焦回归 | `spells / scorching_ray / spell_remediation / hold_person / combat` | 未执行（无改动可回归） |
| 全量 | `pytest tests/rulesets` | 未执行 |
| ruff | `ruff check src/rulesets/dnd2024/combat ...` | 未执行 |
| `git diff --check` | — | 干净 |

零改动的切片不跑回归不是"省略"：没有可归因的变更，跑出来的绿色只反映基线。基线本身见 F15 报告 §6（`tests/rulesets` 1995 passed / 11 failed，11 条全是 `character_builder` 的 `ability:con in background:soldier`）。

## 7. 为后续切片留下的核实结果

停工不等于白读。以下事实已核实，可直接给重启 F16 或拆分前置用：

1. **学派与职业来源是可用的**：`spells/srd_spells.json` 每条法术都带 `school` 与 `class_refs`（如 `acid_splash: school=evocation, class_refs=[class:sorcerer, class:wizard]`）。§4.4.1 的"实际 Wizard spell + school 为 Evocation"双重过滤没有数据缺口。
2. **真实子职已存在**：特性目录里 `subclass:evoker`（现有 `overchannel` 14 级）与 `subclass:draconic_sorcery`（现有 `draconic_spells` / `draconic_resilience` 3 级）都在，四项新特性挂靠不需要新建子职。
3. **`half_on_success` 与抗性的既有顺序可直接复用**：`resolution.py` 的豁免分支是"掷骰 → 加值并入骰式 → Evasion/半伤 → 抗性"，Potent 的半伤只需插在同一个位置，不需要新的伤害流水线。
4. **Potent 的真实缺口只有一处**：`mode == "spell_attack"` 的 miss 分支在 `if succeeded:` 之后整段跳过掷骰，所以"未中仍掷伤害骰"要改的是控制流，不是数值。
5. **Empowered 的语义前提是真缺口**：当前每个目标、每束射线各自 `roll_damage_node`，一个事件一个 roll 集合。§4.1.4 要求的"一次 damage roll"需要先定义 roll 实例标识（事件序号或 `roll_index`），否则多目标法术会按目标复制 Int 加值——这正是 §7.3 的停止条件。它没被列为停止项，是因为可以靠 intent 显式指定 roll 序号解决，但必须先把这个语义写进契约。

## 8. 解除停工需要什么

| 停止项 | 解除入口 |
| --- | --- |
| Sculpt Spells | 一个独立的区域成员切片：施法点/方向 + Cone/Cube/Sphere/Emanation 尺寸 + 可见性 + "哪些生物被覆盖"的权威集合，并让 `spell_effects` 能声明区域。属白名单外的新几何层，也是 §7 非目标里的"新 2D AoE 引擎"。 |
| Elemental Affinity | `feature_choices` 支持第三种 kind（`damage_type`），且 `progression/advancement.py` 与 `character/derivation.py` 都能按 kind 分流；或者把 owner-scoped 固定选择移到独立状态，并让建角、升级、derive 三条路径都认。 |

两者都不属于"法术修饰"这一层的职责。F16 若要完整交付，应排在这两个前置之后。

## 9. 偏差与未决

1. **偏差**：无。本切片没有产生任何代码或内容改动，因此没有偏离白名单的机会。
2. **未决（一）**：`acid_splash` 在 SRD 5.2.1 是 5 尺半径球，目录里 `half_on_success` 缺失。这不是 F16 的发现，但区域前置落地时会一起暴露——届时要单独核对它的豁免成功是否应 0 伤害。
3. **未决（二）**：`burning_hands` / `thunderwave` 目前只能打一个目标，任何依赖"这两个法术命中多个敌人"的既有测试都是在这个近似下绿的。区域前置会改写它们的目标契约，属 breaking change，需要一并评估受影响用例。
4. **未决（三）**：任务书 §1.4 与 §4.3.6 存在字面张力（前者要求停整切片，后者允许只做已提供受影响集合的子集）。本报告按 §1.4 从严执行，并已就"是否只做 Potent + Empowered"征询项目负责人，结论为整切片停工。
