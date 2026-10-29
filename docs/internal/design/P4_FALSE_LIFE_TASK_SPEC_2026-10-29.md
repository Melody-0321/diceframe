# 切片 P4 任务书：False Life（临时生命值）

版本：v1（2026-10-29）
执行侧须知：本任务书是唯一需求来源。只参考本任务书列出的源文件；不要读取 `docs/internal/` 下其他计划文档。仓库根的 `AGENTS.md` 与 `docs/ENGINEERING_RULES.md` 自动适用。
依赖声明：本切片在 P1、P5、P2、P3 之后执行。无强机制依赖（不用 upcast_target_count / repeat_targets），但 P1-P3 已改 `catalog.py` / `validation.py` / `resolution.py`，行号会偏移，描述以语义位置为准。

---

## 1. 目标

为 D&D 2024 规则集实现 **false_life（虚假生命，1 环）** 的完整闭环：目录数据 → 自我施放（含升环固定加值）→ 临时生命值授予（keep-max）→ 受伤时优先吸收 → 测试。

本切片沉淀一项通用原语：

- **临时生命值（temp HP）资源**：新效果模式 `temp_hp` 授予；reducer 端 keep-max 语义 + 伤害优先吸收。后续 heroism、armor of agathys 等只需目录数据化。

**规则语义（SRD 5.2.1，2024 版，规则书原文已核实）**：

- 虚假生命：一环死灵（术士、法师）。施法时间动作；施法距离自身；成分 V、S、M；持续时间立即。**你获得 2d4+4 点临时生命值。** 升环施法：使用的法术位每比一环高一环，其给予的临时生命值就增加 5。
- 临时生命值通则：
  - **优先失去临时生命值**：如果你在有临时生命值时受到伤害，会优先扣除这些值，余下的伤害才会扣到你的生命值上（有 5 临时生命值受到 7 伤害 → 失去全部临时生命值再失去 2 生命值）；
  - **持续时间**：持续直至它们被消耗或你完成一次长休；
  - **不叠加**：已有临时生命值时获得更多，你决定保留原有值或获得新值（10 与 12 二选一，不能是 22）；
  - **既不是治疗也不是生命值**：不能加在生命值上；治疗效果不能恢复它们；获得临时生命值不视为被治疗；满生命值的生物也可以获得；生命值为 0 时获得临时生命值不能令你恢复意识，只有真正的治疗能救你。

出处（引用而非记忆，执行侧可自行核对）：

- `.rulebooks/dnd5r/玩家手册2024/法术详述/1环.htm` L113-114（虚假生命）；
- `.rulebooks/dnd5r/玩家手册2024/进行游戏/临时生命值.htm` L7-21（通则四条）。

### 1.1 必须锁定的规则边界

1. **keep-max 简化，如实记录偏差**：规则书原文是"你决定保留原有值或获得新值"（玩家二选一）。引擎确定性原则下简化为**保留较高者**——两者中较高者永远是理性选择，偏差只存在于玩家故意保留较低值的无意义场景。执行报告必须记录此偏差。
2. **优先吸收发生在 reducer**：伤害事件（`resource.changed`，负 delta）应用时先扣 `temp_hp` 再扣 `hp`；事件本身的 `amount`（打出的伤害）不变，吸收反映在状态上。
3. **temp HP 不是治疗**：授予不清除 `unconscious` / `stable`、不重置死亡豁免、不被 `cannot_regain_hp`（颤栗之触）阻挡、`hp` 与 `max_hp` 不因授予改变。
4. **0 HP 目标拒绝**：`temp_hp` 模式不进"0 HP 目标豁免集合"（healing/buff/stabilize）——引擎一贯拒绝无意义操作（RAW 允许给 0 HP 目标赋 temp 但不恢复意识，引擎直接拒绝，记录偏差）。0 HP 者自我施法本就被意图门挡死（只许 death_save），此边界只影响未来对他人赋 temp 的法术。
5. **升环是固定值**：每级 +5（`2d4+4` → 3 环 `2d4+9`、4 环 `2d4+14`）。`spell_formula_node` 的 `upcast` 参数要求同面骰公式，**不得**用它表达 flat 加值——用本切片的 `upcast_flat` 字段在分支内自行加常数节点。
6. **满血可授予**：`hp == max_hp` 时授予照常（temp 不受 max_hp clamp）。
7. **死亡豁免失败累积看吸收后伤害**：`_apply_hp_change` 现有"`before == 0 and delta < 0` 时累积失败"逻辑使用**吸收后**的 delta——temp 吸收了全部伤害（delta 变 0）就不加失败。

### 1.2 本切片的产品策略与裁剪

- **长休清理推迟**：规则书规定 temp 持续至长休；战斗引擎没有长休钩子，temp 持续存在直至被消耗或被更高的新值覆盖。遗留记录，不在本切片。
- **敌人无 temp HP**：敌方无任何 temp 来源（enemy 分支 fail closed），不实现敌人侧 temp。GM 注入敌人 `resources.temp_hp` 不被支持（敌人档案没有 resources 投影路径）。
- **其它 temp 来源不做**：heroism（专注光环持续赋 temp）、armor of agathys（temp + 反伤）、瞬发 temp 的战斗外授予（aid 的 max_hp 提升是另一机制）——全部推迟，本切片只做 false_life 所需的最小原语。
- **战斗结束不清 temp**：combat.ended 不触碰角色资源（现状行为保持）。
- **不做 temp 的 UI 投影改造**：`_player_view` 暴露 `temp_hp` 字段即完成服务端契约；前端如何展示不在本切片。

## 2. 现有代码契约（已核实，直接引用不要重造）

| 事实 | 位置 |
|---|---|
| `resource.changed` 事件无条件分发到 `_apply_hp_change`（`event["delta"]` 必须存在） | `src/rulesets/dnd2024/combat/reducer.py` L205-207 |
| `_apply_hp_change`：player/companion 走 `character["resources"]`，`hp = max(0, min(max_hp, before + delta))`；hp≤0 → `unconscious` condition + 移除 `rage` + `death_saves`（`before == 0 and delta < 0` 时按 critical 加 1/2 失败，满 3 → `dead`）；delta>0 → 弹出 `unconscious`/`stable`、重置 `death_saves`；enemy 走 `combat["enemies"][raw_id]`，`defeated` condition | `reducer.py` L332-369 |
| `spell_formula_node(base, upcast, spell, slot_level, actor)`：base 必须匹配骰公式正则；upcast 必须是**同面骰**且按级加骰/加值；戏法按等级乘骰数 | `src/rulesets/dnd2024/combat/action_adapter.py` L89-118 |
| `_spell_events` 模式分支与尾部：healing 分支（公式 → `roll_damage_node` → `resource.changed` 带 `healing: True`、`cannot_regain_hp` 阻挡）、condition 应用尾部、`succeeded` 语义 | `src/rulesets/dnd2024/combat/resolution.py` L366-405（P2/P3 后以语义为准） |
| `_validate_spell`：有益目标集合 `{healing, buff, stabilize}` 要求盟友 + 非 dead；其余模式要求敌对；`hp <= 0 and mode not in {healing, buff, stabilize}` → "spell target is not active" | `src/rulesets/dnd2024/combat/validation.py` L449-462 |
| `SPELL_MODES` 白名单与 `spell_effects` 逐字段 fail closed 校验 | `src/rulesets/dnd2024/combat/catalog.py` L16-19、L26-93 |
| `_player_view` 投影 `hp` / `max_hp`（resources dict，缺省 0 容错模式） | `src/rulesets/dnd2024/combat/view.py` L123-126 |
| false_life 法术元数据已存在（level 1、necromancy、sorcerer/wizard、Action、Self、V/S/M、Instantaneous），无需新增 | `templates/rulesets/dnd2024_srd/content/spell_catalogs/srd_spells.json` L993-1012 |
| 测试基建：`SequenceRng` / `goblin()` / `start_combat`；施法职业卡构造先例（`class:wizard` + `class_spell_choices` + `equipment_package:wizard_a`） | `tests/rulesets/dnd2024_monk_common.py`；`tests/rulesets/test_dnd2024_smite.py` L15-56 |

## 3. 改动清单（白名单，逐文件）

只允许改动以下文件。除 §8 的执行报告豁免外，`git status` 出现白名单外任何变更即为失败。

### 3.1 `templates/rulesets/dnd2024_srd/content/combat_catalogs/srd_combat_core.json`

`spell_effects` 新增一条：

```json
"false_life": {"mode": "temp_hp", "range": 5, "target_count": 1, "temp_hp": "2d4+4", "upcast_flat": 5}
```

语义约定：`mode: "temp_hp"` = 授予临时生命值；`temp_hp` = 基础骰公式；`upcast_flat` = 每升一环的固定加值。`target_count: 1` + 盟友校验覆盖"自身"（客户端传自己的 actor_id）。

### 3.2 `src/rulesets/dnd2024/combat/catalog.py`

1. `SPELL_MODES` 追加 `"temp_hp"`；
2. `spell_effects` 校验追加：`mode == "temp_hp"` 时 `temp_hp` 字段必填且必须是字符串（公式合法性由 `spell_formula_node` 在结算时 fail closed）；`upcast_flat` 若存在必须是 `0 < int <= 50`。

### 3.3 `src/rulesets/dnd2024/combat/validation.py`

有益目标集合追加 `temp_hp`：`if effect["mode"] in {"healing", "buff", "stabilize", "temp_hp"}:`（盟友 + 非 dead）。**不**加入 0 HP 豁免集合（L461 的 `not in {"healing", "buff", "stabilize"}` 保持不含 temp_hp）。

### 3.4 `src/rulesets/dnd2024/combat/resolution.py`

`_spell_events` 模式分支追加（healing 分支旁）：

```python
elif mode == "temp_hp":
    node = spell_formula_node(str(effect["temp_hp"]), None, spell, slot_level, actor)
    levels = slot_level - int(spell["level"])
    flat = int(effect.get("upcast_flat", 0) or 0)
    if flat and levels > 0:
        node = {"op": "add", "args": [node, {"op": "constant", "value": flat * levels}]}
    amount, rolls = roll_damage_node(node, rng)
    events.append({
        "type": "resource.changed", "resource": "temp_hp", "target_id": target_id,
        "delta": amount, "amount": amount, "rolls": rolls,
    })
    succeeded = True
```

condition 应用尾部不含 `temp_hp` 模式（false_life 无 condition），天然不应用。

### 3.5 `src/rulesets/dnd2024/combat/reducer.py`

1. `resource.changed` 分发按 resource 键分流：

```python
if event_type == "resource.changed":
    if str(event.get("resource") or "hp") == "temp_hp":
        self._apply_temp_hp_change(snapshot, event)
    else:
        self._apply_hp_change(snapshot, event)
    return
```

2. 新增 `_apply_temp_hp_change`：仅 player/companion——`resources["temp_hp"] = max(int(resources.get("temp_hp", 0) or 0), int(event["amount"]))`（keep-max）；enemy 或其他 kind → `EventBatchError("temp HP target actor is invalid")`（fail closed）。不触碰 `unconscious`/`stable`/`death_saves`/`hp`。
3. `_apply_hp_change` 的 player/companion 分支，负 delta 在 clamp 之前先吸收：

```python
temp = int(resources.get("temp_hp", 0) or 0)
if delta < 0 and temp > 0:
    absorbed = min(temp, -delta)
    resources["temp_hp"] = temp - absorbed
    delta += absorbed
```

死亡豁免失败累积（`before == 0 and delta < 0`）与 hp clamp 使用吸收后的 delta。enemy 分支不动。

### 3.6 `src/rulesets/dnd2024/combat/view.py`

`_player_view` 投影追加 `"temp_hp": int(resources.get("temp_hp", 0) or 0)`（`max_hp` 旁，同款缺省容错）。

### 3.7 测试（新文件）

新文件 `tests/rulesets/test_dnd2024_false_life.py`：职业卡照抄 `test_dnd2024_smite.py` 模式换 `class:wizard`（`class_spell_choices` 选 false_life，`equipment_package:wizard_a`，1 级即可）。测试矩阵见 §4。

回归：`tests/rulesets/test_dnd2024_combat.py`、`test_dnd2024_spells.py`、`test_dnd2024_smite.py`、`test_dnd2024_uncanny_dodge.py`、`test_dnd2024_monk_combat.py`、`test_dnd2024_invisibility.py`、P2/P3/P5 测试文件全部通过。

## 4. 测试矩阵

| # | 场景 | 断言 |
|---|---|---|
| 1 | 目录校验：`temp_hp` 模式缺 `temp_hp` 字段 / `upcast_flat: "5"`（非 int）/ 超 50 | `CombatCatalogError` |
| 2 | 1 级法师自我施放 false_life（SequenceRng 两骰 2,3 → 2d4=5+4=9） | `resource.changed`（`resource: "temp_hp"`, amount=9, rolls=[2,3]）；apply 后 state `temp_hp == 9`；`hp` 与 `max_hp` 不变 |
| 3 | keep-max：已注入 temp 10 再获 9 → 仍 10；temp 8 再获 12 → 12 | state 断言（用两次施放或注入首次 temp） |
| 4 | 优先吸收：hp 20 + temp 5，受 7 伤害 | state：`temp_hp == 0`、`hp == 18` |
| 5 | 全吸收：hp 20 + temp 7，受 5 伤害 | state：`temp_hp == 2`、`hp == 20`；无 `unconscious` |
| 6 | 满血授予：hp == max_hp 时施放 | `temp_hp` 照常增加，`hp` 不变（不受 max_hp clamp） |
| 7 | 升环：3 环位施放（2d4+4+5） | SequenceRng 两骰 1,1 → amount=11；4 环位 → +10 |
| 8 | 敌我校验：对 goblin 施 false_life | `CombatIntentError`（temp_hp 属有益集合，需盟友） |
| 9 | 非治疗：自挂 `cannot_regain_hp`（注入或颤栗之触）后施 false_life | 授予照常（对照 healing 被挡的既有行为不回归） |
| 10 | 死亡豁免不受吸收外伤害：0 HP + 注入 temp 5 的玩家受 3 伤害 | `death_saves.failures` 不增加（吸收后 delta=0）、hp 仍 0 |

## 5. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/rulesets/test_dnd2024_false_life.py -q
.venv\Scripts\python.exe -m pytest tests/rulesets/test_dnd2024_combat.py tests/rulesets/test_dnd2024_spells.py tests/rulesets/test_dnd2024_smite.py tests/rulesets/test_dnd2024_uncanny_dodge.py tests/rulesets/test_dnd2024_monk_combat.py tests/rulesets/test_dnd2024_invisibility.py tests/rulesets/test_dnd2024_hold_person.py tests/rulesets/test_dnd2024_scorching_ray.py -q
.venv\Scripts\python.exe -m pytest tests/rulesets -q --deselect tests/rulesets/test_dnd2024_character_builder.py
```

（已执行切片的测试文件名按实际存在清单补充。）

## 6. 禁止事项

1. 禁止 temp 叠加（必须 keep-max）；禁止把 keep-max 改成玩家可选。
2. 禁止把 temp HP 当治疗处理：不清 `unconscious`/`stable`、不重置 `death_saves`、不受 `cannot_regain_hp` 影响、不走 `_apply_hp_change` 的 `delta > 0` 分支。
3. 禁止用 `spell_formula_node` 的 `upcast` 参数表达 flat 加值（同面骰限制）；flat 用 `upcast_flat`。
4. 禁止给 enemy 侧实现 temp HP（fail closed）。
5. 禁止实现长休清理、战斗结束清理（§1.2 已裁剪）。
6. 禁止 heroism / armor of agathys / aid 等其它 temp 或 max_hp 机制。
7. 禁止在 resolution / validation 写具体法术名分支——false_life 只允许目录数据 + `temp_hp` 模式。

## 7. 停止条件

遇到以下情况立即停止并报告，不要自行发明语义：

1. `resource.changed` 事件的既有消费方（投影/审计/前端契约测试）假设 `resource` 恒为 `"hp"` 且无法容忍 `"temp_hp"`；
2. `character["resources"]` 结构在既有写入路径上没有缺省容错（`temp_hp` 键不存在导致 KeyError 而非按 0 处理）；
3. 0 HP + temp 吸收与死亡豁免累积的交互无法同时满足 §1.1 边界 7 与既有死亡豁免测试；
4. 任何白名单外文件必须修改才能通过验收。

## 8. 执行报告模板

执行完成后在 `docs/internal/design/P4_FALSE_LIFE_TASK_SPEC_2026-10-29.md` 追加"执行报告"节：变更文件清单、每个测试矩阵项的通过情况、§3 语义与实现的偏差（尤其 keep-max 与 0 HP 拒绝两条）、遗留问题。同规则：除本任务书文件的执行报告追加外，不产生其他文档。

## 9. 修订记录

- v1（2026-10-29）：初版。
