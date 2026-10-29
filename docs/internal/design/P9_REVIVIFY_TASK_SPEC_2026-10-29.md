# 切片 P9 任务书：Revivify（复活：dead → 存活）

版本：v1（2026-10-29）
执行侧须知：本任务书是唯一需求来源。只参考本任务书列出的源文件；不要读取 `docs/internal/` 下其他计划文档。仓库根的 `AGENTS.md` 与 `docs/ENGINEERING_RULES.md` 自动适用。
依赖声明：本切片在 P1（invisibility）、P5（stoneskin）、P2（hold_person）、P3（scorching_ray）、P4（false_life）、P6（misty_step）、P8（dispel_magic）、P7（counterspell）之后执行，是 1B 第九个也是最后一个切片。P4 已把 `temp_hp` 加入盟友集合；P6 已加入 `teleport`；P8 已把 `dispel` 加入 hp≤0 拒绝豁免集合。前置切片合入后本任务书引用的行号会偏移，描述以语义位置为准。

---

## 1. 目标

为 D&D 2024 规则集实现 **revivify（回生术，3 环）** 的完整闭环：目录数据 → 施法（触碰死亡的盟友玩家）→ 复活事件 → 状态清理 → 测试。

本切片沉淀一项通用原语：

**复活模式**：新效果模式 `"revive"`——目标必须是**同阵营、已死亡（持有 `dead` condition）的玩家**；结算在 `spell.cast` 之后发 `dnd2024.character.revived` 事件（payload `actor_id` = 目标、`hp` = 1），由**既有** reducer 处理器消化（清 `dead`/`unconscious`/`stable`/`death_saves` 四状态 + hp 置 1 并 clamp max_hp + 仅接受 player）。resolution 不新增任何状态写入逻辑——复活的全部状态语义已在 reducer 存在，本切片只是把"施法"接到这条事件上。

**规则语义（SRD 5.2.1，2024 版，规则书原文已核实）**：

- 回生术：三环死灵（牧师、德鲁伊、圣武士、游侠）。施法时间动作；施法距离触碰；法术成分 V、S、M（一颗价值 300+GP 的钻石，作为法术耗材）；持续时间立即。你接触**在前一分钟内刚刚死亡的一名生物。该生物以 1 点生命值回生**。该法术不能复活老死的生物，也不能恢复失去的身体部位。

出处（引用而非记忆，执行侧可自行核对）：

- `.rulebooks/dnd5r/玩家手册2024/法术详述/3环.htm` L183-184（回生术）。

### 1.1 必须锁定的规则边界

1. **回生 HP 固定为 1**：RAW"以 1 点生命值回生"；事件 payload `hp: 1` 硬编码于 revive 分支，reducer 的 max_hp clamp 兜底。不设数据字段（未来 resurrection 的"恢复全部生命值"届时经事件 payload 扩展，不在本切片预支）。
2. **目标必须 dead**：revive 模式要求目标 `"dead" in conditions`，否则 `CombatIntentError`。dying（0 HP、unconscious、未满 3 失败）**不是**合法目标——那是 healing/stabilize 的职责。`dead` 的 source 不区分（`death_saves` 豁免失败致死与 `damage_at_zero_hp` 伤害致死同等可复活）。
3. **既有 dead 拒绝对其它模式保持不变**：healing/buff/stabilize/temp_hp/teleport 对 dead 目标仍拒绝（"dead targets require a resurrection effect"）——本切片的反转只作用于 revive 模式本身，不得泄漏。
4. **目标必须是 player**：companion 与 player 走同一条 HP 归零→死亡管线（`_apply_hp_change`），**dead companion 状态可达**；但 reducer 的 `character.revived` 契约仅接受 player（"revived actor must be an existing player"）。validation 必须前置 kind 检查（fail fast），否则 dead companion 目标会在 apply 阶段炸 `EventBatchError`。companion 复活记录为已知限制（§1.2）。enemy 侧 0 HP 产生的是 `defeated`（非 `dead`）且敌我校验先行拒绝，双重不可达，无需特判。
5. **复活不是治疗**：revive 分支不发 `resource.changed` hp 事件，不经过 healing 管线——因此不受 `cannot_regain_hp`（颤栗之触）阻断（RAW 上回生不是"恢复生命值"；确需解除的场合由 P8 dispel 先行）。状态清理完全由 reducer 的 revived 处理器完成（`dead`/`unconscious`/`stable`/`death_saves` 四键全 pop），本切片不改 reducer。
6. **无 RNG**：revive 分支零骰（无攻击、无豁免、无伤害/治疗掷骰）。
7. **revivify 是普通施法**：动作 + 3 环法术位 + `slot_spell_cast` 每回合一位上限 + `spell.cast` 事件先行 + Instantaneous 无专注。`slot_level < 3`、三环位耗尽等既有拒绝全部适用。
8. **复活不打断战斗节奏**：当前回合仍是施法者回合；被复活者在其下一个属于他的回合正常行动（turn 推进的 dead 跳过逻辑因 dead 被清而自然失效，无需额外事件）。
9. **施法者不可能是目标**：dead/dying 玩家的意图门只放行 death_save（validation L274-276 既有），"给自己施 revivify"天然不可达，无需特判。

### 1.2 本切片的产品策略与裁剪

- **1 分钟死亡时限**：引擎不追踪死亡时刻——裁剪，如实记录（RAW"前一分钟内"由 GM 叙事把握）。
- **300+GP 钻石耗材**：无组件/货币经济——裁剪。
- **"老死不能复活 / 不恢复失去的身体部位"**：机械不可判的叙事限制——裁剪，GM 层职责。
- **companion / enemy 复活**：不做（§1.1 边界 4）。未来切片若扩展，须同时改 reducer 契约与 validation kind 门，并处理 companion 的 canonical 位置（DND party 状态而非 characters 快照）。
- **raise dead / resurrection 家族**：数据不落（后续切片；复活原语已就位，届时主要是数据 + payload 扩展）。
- **legacy sheet 的 `deceased`/`hp` 标志同步**：法术路径只写 canonical（ruleset_character），legacy 投影走既有 reconciliation（`merge_live_character_projection`），不新增同步代码。GM 命令路径（`apply_revive_commands`）的显式同步是另一条链路，不在本切片。
- **前端**：无新增 intent 选择字段；面板照既有 cast_spell 流程。目标选择器若过滤掉 dead 盟友属已知偏差（照 P2"投影滞后"先例记录，服务端已放行）。

## 2. 现有代码契约（已核实，直接引用不要重造）

| 事实 | 位置 |
|---|---|
| `dnd2024.character.revived` reducer 处理器（本切片的直接消费方，**不改**）：`kind != "player" or raw_id not in snapshot["characters"]` 拒绝；`hp = max(1, int(event.get("hp", 1) or 1))`，max_hp>0 时 clamp；pop `dead`/`unconscious`/`stable`/`death_saves` | `src/rulesets/dnd2024/combat/reducer.py` L70-84 |
| `dnd2024.death_save.resolved`：3 失败 → `conditions["dead"] = {"source": "death_saves"}` 并 pop unconscious | `reducer.py` L287-301 |
| `_apply_hp_change`：player **与 companion** 同管线——hp≤0 → `unconscious` + `death_saves` 初始化；`before == 0 and delta < 0` 时按 critical 加 1/2 失败，满 3 → `dead`（source `damage_at_zero_hp`）并 pop unconscious；enemy 0 HP → `defeated` | `reducer.py` L336-369 |
| `_validate_spell` 目标循环：盟友集合 L449（P8 后为 `{healing, buff, stabilize, temp_hp, teleport}`）+ dead 拒绝 L452-453（"dead targets require a resurrection effect"——本切片的反转钩子）；敌方 elif L454-455；hp≤0 拒绝豁免集合 L461-462（P8 后为 `{healing, buff, stabilize, dispel}`）；射程 L463-464；模式级特判先例（stabilize 的 dying 门 L456-459、P2/P6/P8 模式级检查） | `src/rulesets/dnd2024/combat/validation.py` L396-467 |
| dying/dead actor 意图门：`actor["hp"] <= 0 and intent_type != "death_save"` → 只许 death_save（stable 者可 end_turn） | `validation.py` L274-280 |
| `_spell_events` 主循环：cost/专注 → `spell.cast` → 目标循环 mode 分发；`stabilize` 分支（revive 分支的同级插入参照）；condition 应用尾部与 push 块只对带相应数据的效果生效（revive 无 condition/push 数据，天然跳过） | `src/rulesets/dnd2024/combat/resolution.py` L233-267、L384-411 |
| `SPELL_MODES` frozenset（P8 后含 `dispel`）；from_bundle 逐条校验：mode 合法性 + range [5,600]（覆盖 5） | `src/rulesets/dnd2024/combat/catalog.py` L16-19、L58-83 |
| revivify 法术元数据已存在（level 3 / necromancy / cleric、druid、paladin、ranger / Action / Touch / V,S,M / Instantaneous / 无专注 / `source_ref: srd-5.2.1:p159:revivify`），无需新增 | `templates/rulesets/dnd2024_srd/content/spell_catalogs/srd_spells.json` L3394-3414 |
| 触碰距离数据先例：`cure_wounds`（Touch）`range: 5`、`spare_the_dying` `range: 15`；target_count 缺省 1（引擎 `effect.get("target_count", 1)`） | `templates/rulesets/dnd2024_srd/content/combat_catalogs/srd_combat_core.json` L41-43 |
| GM 复活路径（同一 reducer 事件的另一发送方，事件形态参照）：`revive_player` 构造 `character.revive` intent → batch 内 `dnd2024.character.revived` | `src/rulesets/dnd2024/combat/engine.py` L734-773 |
| turn 推进跳过清单：enemy/companion hp≤0 跳过；`dead`/`stable` 者跳过——复活后自然失效 | `resolution.py` `_end_turn_events` L621-629 |
| available_intents 对 dying/dead 玩家的投影：dead 玩家仅 `combat.message` + `death_save`；复活后 `death_save` 消失、`attack` 出现 | `engine.py` L215、L424-425；断言先例 `tests/rulesets/test_dnd2024_combat.py` L289-303 |
| 测试基建：`_instance`/`_start`（先攻 SequenceRng 控制 + 断言玩家第一）；canonical 直改死亡状态先例（L252-259：hp 0 + conditions 注入）；施法职业卡先例（paladin_sheet 模式 + `class_ref` + `class_spell_choices` + 等级推进拿三环位）；双玩家 = `instance.players` 放第二个玩家 | `tests/rulesets/test_dnd2024_combat.py` L29-78、L252-272；`tests/rulesets/test_dnd2024_smite.py` L15-56；`tests/rulesets/dnd2024_monk_common.py` |

## 3. 改动清单（白名单，逐文件）

只允许改动以下文件。除 §8 的执行报告豁免外，`git status` 出现白名单外任何变更即为失败。

### 3.1 `templates/rulesets/dnd2024_srd/content/combat_catalogs/srd_combat_core.json`

`spell_effects` 追加一条：

```json
"revivify": {"mode": "revive", "range": 5}
```

target_count 缺省 1（与 cure_wounds/spare_the_dying 一致）。conditions 注册表无需新增。

### 3.2 `src/rulesets/dnd2024/combat/catalog.py`

`SPELL_MODES` 追加 `"revive"`。无新增逐字段校验（range [5,600] 既有检查覆盖 5）。

### 3.3 `src/rulesets/dnd2024/combat/validation.py`（`_validate_spell` 目标循环）

1. 盟友集合追加 `"revive"`，并把 dead 检查改为模式分支（反转只作用于 revive，其它模式拒绝语义原样）：

```python
if effect["mode"] in {"healing", "buff", "stabilize", "temp_hp", "teleport", "revive"}:
    if target_side != actor_side:
        raise CombatIntentError("healing and beneficial spells require an allied target")
    if effect["mode"] == "revive":
        if target["kind"] != "player":
            raise CombatIntentError("revive spells target players only")
        if "dead" not in target.get("conditions", {}):
            raise CombatIntentError("revive spells require a dead target")
    elif "dead" in target.get("conditions", {}):
        raise CombatIntentError("dead targets require a resurrection effect")
```

2. hp≤0 拒绝豁免集合追加 `"revive"`（dead 目标 hp 为 0，必须放行）。

### 3.4 `src/rulesets/dnd2024/combat/resolution.py`（`_spell_events` 目标循环）

新增 `revive` 分支（与 stabilize 分支同级）：

```python
elif mode == "revive":
    events.append({
        "type": "dnd2024.character.revived",
        "actor_id": target_id, "hp": 1,
    })
    succeeded = True
```

不设 RNG 调用、不经过 healing 管线、不发 `resource.changed`；effect 数据无 `condition`/`push`，后续通用块天然跳过。`hp: 1` 是 RAW 固定值（§1.1 边界 1）。

### 3.5 测试

- 新文件 `tests/rulesets/test_dnd2024_revivify.py`：施法者照 paladin_sheet 模式换 `class:cleric` + `class_spell_choices` 含 `spell:revivify`，推进到 5 级拿三环位；受害者在 `instance.players` 放第二个玩家，其 canonical 直接注入死亡状态（照 `test_dnd2024_combat.py` L252-259 先例）：`resources["hp"] = 0`、`conditions = {"dead": {"source": "death_saves"}, "death_saves": {"successes": 0, "failures": 3}}`（与 reducer L287-301 产物一致，不含 unconscious）。combat.start 用 SequenceRng 保证施法者先攻第一并断言。测试矩阵见 §4。
- 回归：`test_dnd2024_combat.py`、`test_dnd2024_spells.py`、`test_dnd2024_smite.py`、`test_dnd2024_uncanny_dodge.py`、`test_dnd2024_monk_combat.py` 及 P1-P8 产物测试文件全部通过（`test_dnd2024_character_builder.py` 上游豁免失败不计）。

## 4. 测试矩阵

| # | 场景 | 断言 |
|---|---|---|
| 1 | 目录校验：mode 不在 SPELL_MODES 的效果照拒；`revive` 条目通过加载 | `CombatCatalogError` / 正常 |
| 2 | 完整闭环：施法者先攻第一，cast_spell revivify（slot_level 3）于 dead 盟友 | 事件序 `action.spent` → `slot_spent` → `spell.cast` → `character.revived`（hp=1）；盟友 canonical `hp == 1`、conditions 不含 `dead`/`unconscious`/`stable`/`death_saves`；施法者 `slots_current["3"]` 减 1；economy action 归零；**SequenceRng 零消耗**（cast 后无掷骰） |
| 3 | dying 非 dead：目标 0 HP + `unconscious` + `death_saves`（未满 3 失败）、无 `dead` | `CombatIntentError`（revive spells require a dead target） |
| 4 | dead 拒绝不泄漏：对同一 dead 盟友施 cure_wounds（healing） | `CombatIntentError`（dead targets require a resurrection effect） |
| 5 | 敌方目标：revivify 打 goblin | `CombatIntentError`（allied target 分支） |
| 6 | companion 目标：dead companion（canonical/规则状态注入同款死亡态） | `CombatIntentError`（players only） |
| 7 | 射程：combat.start 的 player_positions 把盟友放到与施法者距离 > 5 尺 | `CombatIntentError`（out of range） |
| 8 | 复活后意图恢复：dead 盟友 `available_intents` 仅 `combat.message` + `death_save`；复活后 `death_save` 消失、`attack` 出现 | 照 `test_dnd2024_combat.py` L289-303 断言模式 |
| 9 | 环阶与法术位门槛：`slot_level: 2` 被拒；三环位耗尽后再施被拒 | `CombatIntentError`（既有拒绝语义） |
| 10 | dead source 无关：注入 `{"dead": {"source": "damage_at_zero_hp"}, ...}` 重跑 #2 核心断言 | `character.revived` hp=1、状态清理同 #2 |
| 11 | 回归：healing / stabilize / temp_hp / teleport / dispel 既有行为不变 | 回归套件全绿 |

## 5. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/rulesets/test_dnd2024_revivify.py -q
.venv\Scripts\python.exe -m pytest tests/rulesets/test_dnd2024_combat.py tests/rulesets/test_dnd2024_spells.py tests/rulesets/test_dnd2024_smite.py tests/rulesets/test_dnd2024_uncanny_dodge.py tests/rulesets/test_dnd2024_monk_combat.py tests/rulesets/test_dnd2024_invisibility.py tests/rulesets/test_dnd2024_hold_person.py tests/rulesets/test_dnd2024_misty_step.py tests/rulesets/test_dnd2024_dispel_magic.py -q
.venv\Scripts\python.exe -m pytest tests/rulesets -q --deselect tests/rulesets/test_dnd2024_character_builder.py
```

（第二行按执行时实际存在的 P3/P4/P5/P7 测试文件名补充，以各任务书测试节为准。）

## 6. 禁止事项

1. 禁止改动 reducer 的 `dnd2024.character.revived` 处理器（GM 复活路径共用的既有契约；本切片只发事件）。
2. 禁止给 companion/enemy 开复活（§1.1 边界 4；validation 的 player kind 门必须存在，防 apply 阶段 EventBatchError）。
3. 禁止把 revive 做成 healing 分支变体：不发 `resource.changed`、不受 `cannot_regain_hp` 阻断（§1.1 边界 5）。
4. 禁止在 resolution / validation 新增具体法术名分支——revivify 只允许目录数据 + revive 模式。
5. 禁止实现 1 分钟时限、钻石耗材、老死/肢体叙事限制（§1.2 已裁剪）。
6. 禁止顺手落 raise dead / resurrection 数据（后续切片）。
7. 禁止把 dead 检查的反转泄漏到其它有益模式（healing/buff/stabilize/temp_hp/teleport 对 dead 仍拒绝，§1.1 边界 3）。
8. 禁止新增 legacy sheet（`deceased`/`hp`）同步代码（走既有投影，§1.2）。
9. 禁止给 `hp: 1` 加数据字段或可配置性（RAW 固定；resurrection 届时另行扩展）。

## 7. 停止条件

遇到以下情况立即停止并报告，不要自行发明语义：

1. dead 玩家在 combat.start / readiness / 先攻构造上有本任务书未记录的额外门，导致 §4 场景无法构造；
2. reducer `character.revived` 的实际行为与 §2 契约不符（如 clamp 或四状态清理语义变化）；
3. available_intents 对 dead 玩家的投影与 L289-303 断言模式不符；
4. revive 分支需要 RNG 或 `resource.changed` 事件才能通过既有消费方（投影/前端契约测试）；
5. 发现 dead companion 经某条路径可绕过 validation 的 kind 门直达 reducer（EventBatchError 面）；
6. 任何白名单外文件必须修改才能通过验收。

## 8. 执行报告模板

执行完成后在 `docs/internal/design/P9_REVIVIFY_TASK_SPEC_2026-10-29.md` 追加"执行报告"节：变更文件清单、每个测试矩阵项的通过情况、§3 语义与实现的偏差（若有，尤其 companion 复活限制与裁剪项）、遗留问题。同规则：除本任务书文件的执行报告追加外，不产生其他文档。

## 9. 修订记录

- v1（2026-10-29）：初版。
