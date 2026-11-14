# S0-F17 停工报告：Cunning Strike 的 Sneak Attack 骰池预算

日期：2026-11-14
分支：`feat/dnd2024-s0f17-cunning-strike`（叠在 `feat/dnd2024-s0f16-spell-modifiers@ac3e2aa6` 之上）
基线：`ac3e2aa6`
范围：`cunning_strike`（盗贼 5）、`improved_cunning_strike`（11/14/18）、`devious_strikes`、Thief `supreme_sneak`（9）、`elusive`（18）

---

## 1. 结论

**整切片停工，零代码改动。**

七种效果的三种前提在代码里没有任何权威来源，且每一项都单独触发任务书的停止条件：

| 缺的东西 | 影响的效果 | 停止条件 |
| --- | --- | --- |
| Poisoner's Kit 不存在于任何目录 | Poison | §5.6（需要新增物品时停止） |
| 目标生物尺寸无权威来源 | Trip | §1.4 + §6.21 |
| Three-Quarters / Total Cover 无模型 | Stealth Attack、Supreme Sneak | §5.6 + §7 非目标 |

§9.4 已经写死处理方式：「模型缺失必须停止，不得将七项中的部分实现称为切片完成」。所以这次没有"只做可做的几项"这个选项，与 F16 不同的是，本切片的残缺部分不是"少两个载体"，而是七种效果里有三种无法通过，且其中一种（Stealth Attack）是 Thief 子职的验收载体。

## 2. 停止项一：Poisoner's Kit 不存在

### 2.1 事实

`templates/rulesets/dnd2024_srd/content/items/` 有 82 个文件、`content/tools/` 有 32 个文件，完整清单如下（按目录原样）：

- items：`arcane_focus_crystal/orb/staff`、`arrows`、`artisans_tools`、`battleaxe`、`blowgun`、`bolts`、`breastplate`、`burglar_pack`、`calligraphers_supplies`、`chain_mail`、`chain_shirt`、`club`、`crossbow_*`、`crowbar`、`dagger`、`dart`、`druidic_focus_*`、`dungeoneer_pack`、`entertainer_pack`、`explorer_pack`、`flail`、`gaming_set`、`glaive`、`greataxe`、`greatclub`、`greatsword`、`halberd`、`half_plate`、`handaxe`、`healers_kit`、`herbalism_kit`、`hide`、`history_book`、`holy_symbol`、`javelin`、`lance`、`leather_armor`、`light_hammer`、`longbow`、`longsword`、`mace`、`maul`、`morningstar`、`musical_instrument`、`musket`、`occult_book`、`padded`、`parchment`、`pike`、`pistol`、`plate`、`pouch`、`prayer_book`、`priest_pack`、`quarterstaff`、`quiver`、`rapier`、`ring_mail`、`robe`、`scale_mail`、`scholar_pack`、`scimitar`、`shield`、`shortbow`、`shortsword`、`sickle`、`sling`、`spear`、`spellbook`、`splint`、`studded_leather_armor`、`thieves_tools`、`travelers_clothes`、`trident`、`war_pick`、`warhammer`、`whip`
- tools：`alchemists_supplies`、`artisans_tools`、`bagpipes`、`brewers_supplies`、`calligraphers_supplies`、`carpenters_tools`、`cartographers_tools`、`cobblers_tools`、`cooks_utensils`、`drum`、`dulcimer`、`flute`、`gaming_set`、`glassblowers_tools`、`herbalism_kit`、`horn`、`jewelers_tools`、`leatherworkers_tools`、`lute`、`lyre`、`masons_tools`、`musical_instrument`、`painters_supplies`、`pan_flute`、`potters_tools`、`shawm`、`smiths_tools`、`thieves_tools`、`tinkers_tools`、`viol`、`weavers_tools`、`woodcarvers_tools`

没有 Poisoner's Kit。全仓 `grep -i poisoner` 对 `src/`、`templates/`、`tests/` 均无结果。

### 2.2 为什么不能将就

§4.2.1 的要求是「必须实际随身携带 Poisoner's Kit（不要求虚构熟练）」。两个可绕的方向都不成立：

- 新增 `content/tools/poisoners_kit.json`：§5.4 只允许改 `srd_combat_core.json`，物品目录不在白名单；§5.6 直接写「需要新增物品…时停止，不伪造事实」。
- 用现有工具顶替（如 `herbalism_kit` 或 `thieves_tools`）：等于用命名冒充资格审查，Poison 的"携带工具"从一条可验证前提退化成一条注释。

另外，即便有物品，`_actor_view` 目前只投影 `equipment_refs`（`combat/view.py:192`、`:464`），没有"随身工具"的独立概念。§4.2.1 不要求熟练，但要求"on your person"，这与 `equipment_refs` 是否等价需要另行确认——那本身也是一个白名单外的判断。

## 3. 停止项二：目标生物尺寸无权威来源

### 3.1 事实

- **没有怪物目录**：`content/` 的 17 个子目录里没有 `monsters` 或 `encounters`。敌人数据由 `combat.start` 的 intent 内联提交，`combat/view.py:97` 就是从 `enemy.get("armor_class")` 这样的字段直接读的。
- **view 不投影尺寸**：`src/rulesets/dnd2024/combat/view.py` 里 `size` 零命中。`combat/view.py:97-105` 装配敌人时只取 `armor_class`、`hp`、`creature_type` 等。
- **只有玩家有尺寸**：`character/derivation.py:786` 把 `selected_size` 写进 `derived`，来源是 species 的 `size_options`（`species/dragonborn.json:7` 等）。这是玩家角色自身的尺寸，不是攻击目标的尺寸。
- **内容侧无 size**：`grep -rn '"size"' templates/rulesets/dnd2024_srd/content/` 只命中 species 的 `size_options`。

### 3.2 为什么不能将就

§4.2.2 要求「仅 Large 或更小目标；Huge 或尺寸未知不可选」，§6.8 要求「Huge/未知尺寸 fail closed」，§6.21 要求「客户端伪造…尺寸…均无效」。

如果尺寸从 `combat.start` 的 enemy dict 读，那么"目标是不是 Large"就由发起战斗的客户端决定——正是 §6.21 禁止的伪造。如果按 `creature_type` 或名字推断（goblin → Small），就是按名称猜测，§7 非目标明确禁止。

值得注意的是：这条缺口会让 **Trip 在所有目标上 fail closed**。按 §4.2.2 的字面要求，尺寸未知即不可选，所以 Trip 不是"部分可用"，是"永远不可用"。这也是为什么它不能靠"先实现，尺寸以后补"来解决。

## 4. 停止项三：Cover 没有模型

### 4.1 事实

`grep -rn "cover" src/rulesets/dnd2024/ --include=*.py -i` 的全部命中都是 `# pragma: no cover`（覆盖率指令）或英文散文里的 "covers"（如 `check_modes.py:87` "``attack`` covers every attack roll"）。没有任何掩蔽等级、掩蔽几何或 `position → cover` 推导。

`combat/view.py` 的 `_actor_view` 没有 cover 字段；`resolution.py::_movement_events` 只处理位置与距离。

### 4.2 为什么不能将就

两个特性都直接依赖它：

- **Stealth Attack**（§4.2.7）："if you end the turn behind Three-Quarters Cover or Total Cover"——回合末的判定对象是掩蔽等级。
- **Supreme Sneak**（§4.2 引 SRD p64 的 Thief 9 级）："you end the turn behind Three-Quarters Cover or Total Cover"。§7 非目标明确禁止"通过普通 Invisible 或距离阈值冒充 Supreme Sneak 的 Hide/Cover 条件"。

没有掩蔽模型时，"是否在掩蔽后"只剩距离可用，而距离被任务书点名为禁止的替身。§5.6 也写明「需要新增…掩蔽系统…时停止」。

## 5. 附带缺口：Hide 的 invisible 没有来源标记

这一条不单独构成停止项（在白名单内可修），但即使前三项补齐，Stealth Attack 仍需它：

`resolution.py::_hide_events`（`resolution.py:3184` 起）成功时施加：

```python
{"type": "condition.applied", "target_id": actor_id,
 "condition": "invisible", "duration": "combat",
 "source_actor_id": actor_id,
 "ends_on": ["attack_roll", "spell_cast"]}
```

两处与 §4.2.7 冲突：

1. 没有 `source_action: "hide"` 这类来源标记，`_attack_state_options` 无法区分"Hide 得到的 Invisible"与"法术/特性给的 Invisible"。
2. `ends_on` 含 `attack_roll`，即任何一次攻击掷骰都会结束它；而 Stealth Attack 的效果恰恰是"这次攻击不结束该条件"。要支持它就得让终止从"攻击掷骰"改成"攻击掷骰且本效果未被使用"，这是对既有 `ends_on` 语义的扩展，会影响所有依赖 `invisible` 的测试（`test_dnd2024_invisibility.py`）。

## 6. 逐项评估

| 项 | 状态 | 依据 |
| --- | --- | --- |
| `cunning_strike` 授予与骰池 | 未执行 | 机制上可行：`_sneak_attack_dice` 返回 dice 字符串（如 `"3d6"`），可在 `formula_node_from_dice_formula` 之前改骰数，不需要先掷后扣（§7.3 不成立） |
| Poison（1d6） | 停止 | 无 Poisoner's Kit（§2） |
| Trip（1d6） | 停止 | 无目标尺寸（§3） |
| Withdraw（1d6） | 未执行 | 无豁免 + 半速移动 + 免 OA，`_movement_events` 与 F15 的 `brutal_forceful` 同形状，机制可行 |
| Daze（2d6） | 未执行 | 需要"下一回合只能在 move/action/bonus 中实际使用一类"的状态与拦截点，现有 `economy` 无此三选一语义；`incapacitated` 不能替代（§7 非目标明确禁止） |
| Knock Out（6d6） | 未执行 | `conditions` 已有 `unconscious`，但"来源化终止 + 受伤只移除该来源"需要条件带来源并能单独移除，现有 `condition.applied/removed` 未见来源级移除 |
| Obscure（3d6） | 未执行 | `conditions` 注册表无 `blinded`；新增它属 `srd_combat_core.json`（白名单内 §5.4），可行 |
| Stealth Attack（1d6） | 停止 | 无 Cover（§4）+ 无 Hide 来源标记（§5） |
| Supreme Sneak | 停止 | 无 Cover（§4） |
| Elusive | 未执行 | `check_modes.attack_sources` 已是共享来源聚合，按"目标持有 Elusive 且未 incapacitated"过滤 advantage 来源即可，机制可行 |

`conditions` 注册表当前 21 项：`blessed, blurred, charmed, dodging, faerie_fire, frightened, hamstrung, incapacitated, invisible, next_attack_advantage, next_attack_disadvantage, paralyzed, poison_resistant, prone, rage, reckless, slowed_10, staggered, stoneskinned, stunned, unconscious`。其中 **无 `poisoned`、无 `blinded`、无 `dazed`**，三项都要新增（`srd_combat_core.json` 在白名单内，所以这不是停止原因，只是工作量）。

## 7. 测试矩阵映射状态（§6 的 24 条）

全部**未执行**，且未执行不等于通过。

| # | 内容 | 状态 | 原因 |
| --- | --- | --- | --- |
| 1 | 五项特性等级/子职/14 级新选项/Thief 9 边界 | 未执行 | 特性未落地 |
| 2 | 只有合法 Sneak 命中开放选择 | 未执行 | 随切片停 |
| 3 | 七种效果各自扣骰与超预算拒绝 | 未执行 | 三种效果前提已停 |
| 4 | 掷前扣除、剩余骰精确、剩余 0 骰仍结算 | 未执行 | 机制可行（§6 首行），随切片停 |
| 5 | 5 级一个/11 级两个/第三个拒绝 | 未执行 | 随切片停 |
| 6 | save DC = 8 + Dex mod + PB | 未执行 | 随切片停 |
| 7 | Poison 工具前提与回合末重复豁免 | 未执行 | 停止项一 |
| 8 | Trip 仅 Large 或更小，Huge/未知 fail closed | 未执行 | 停止项二 |
| 9 | Withdraw 半速移动且不引发 OA | 未执行 | 机制可行，随切片停 |
| 10 | 多效果按顺序结算、非法组合整体拒绝 | 未执行 | 依赖 3 |
| 11 | Daze 三类行动互斥 | 未执行 | 缺三选一状态模型 |
| 12 | Daze 只持续其下一回合 | 未执行 | 同上 |
| 13 | Knock Out 来源化 Unconscious 与受伤终止 | 未执行 | 缺来源级条件移除 |
| 14 | Obscure Blinded 至下回合结束 | 未执行 | 缺 `blinded` 条件 |
| 15 | Stealth Attack 仅 Hide 来源可选 | 未执行 | 停止项三 + §5 |
| 16 | 回合末在 3/4 或全掩蔽后保留 | 未执行 | 停止项三 |
| 17 | 其他 Invisible 来源不被误删、Cover 服务端重验 | 未执行 | 停止项三 |
| 18 | Elusive 对全部来源移除 Advantage | 未执行 | 机制可行，随切片停 |
| 19 | Elusive 保留 Disadvantage，相抵变纯劣势 | 未执行 | 同上 |
| 20 | Elusive 持有者失能时过滤暂停 | 未执行 | 同上 |
| 21 | 客户端伪造工具/尺寸/Cover/成本/豁免均无效 | 未执行 | 停止项一、二、三本身即该风险的证据 |
| 22 | pending、过期 version、重放一致 | 未执行 | 依赖前置 |
| 23 | 条件与 Daze 在各回合路径不被绕过 | 未执行 | 缺 Daze 模型 |
| 24 | 既有 Sneak/Hide/Monk rider/Invisible/Hold Person 回归 | 未执行 | 无改动可回归 |

## 8. 白名单文件对照

| §5 条目 | 是否改动 |
| --- | --- |
| canonical class feature catalog 及 en / zh-CN locale | 未改 |
| `combat/resolution.py`、`validation.py`、`check_modes.py`、`reducer.py`、`engine.py`、`runtime.py` | 未改 |
| `features/resolver.py` | 未改 |
| `combat_catalogs/srd_combat_core.json` | 未改 |
| 新建 `tests/rulesets/test_dnd2024_cunning_strike.py` | 未建 |
| 白名单外文件 | 未改 |

`git diff --check` 无输出；本分支相对 `ac3e2aa6` 只有本文件。

## 9. 门禁

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 新增用例 | `pytest tests/rulesets/test_dnd2024_cunning_strike.py` | 未执行（文件未建） |
| 聚焦回归 | `sneak_attack / action_routing / hit_riders / invisibility / combat` | 未执行（无改动可回归） |
| 全量 | `pytest tests/rulesets` | 未执行 |
| ruff | `ruff check src/rulesets/dnd2024/combat ...` | 未执行 |
| `git diff --check` | — | 干净 |

零改动的切片跑回归没有归因价值。基线状态见 F15 报告 §6（`tests/rulesets` 1995 passed / 11 failed，11 条全是 `character_builder` 的 `ability:con in background:soldier`）。

## 10. 为后续切片留下的核实结果

1. **`§7.3` 不成立**：`_sneak_attack_dice` 返回的是 dice 字符串而不是已掷结果，`_attack_events` 在 `formula_node_from_dice_formula` 之后才 `roll_damage_node`。扣骰只需要改字符串里的骰数，"先掷后扣"不是必需路径。
2. **`§7.4` 有一半成立**：`conditions` 注册表可以直接加 `poisoned` / `blinded` / `dazed`，属白名单内的 `srd_combat_core.json`；真正的缺口是 `dazed` 的"三类行动互斥"需要一个拦截点，`economy` 目前只有 `action` / `bonus_action` 两个计数，没有"本回合只能用其中一类"的语义。
3. **Withdraw 与 F15 的 Forceful 同形状**：都是"伤害后给一段带方向的移动额度 + 免 OA"。F15 已经建立了 `movement.granted` → `economy["brutal_move"]` → `position.changed{brutal_move}` 这条链，Withdraw 可以直接复用形状（免 OA 是无条件的，不像 Forceful 要校验方向）。
4. **Elusive 的落点是 `check_modes.attack_sources`**：任务书 §3 已经点名，且 F15 的 Reckless 走的就是同一处来源聚合，过滤 advantage 不需要新规则层。

## 11. 偏差与未决

1. **偏差**：无。零改动。
2. **未决（一）**：`equipment_refs` 与"on your person"是否等价尚未确认。若 Poisoner's Kit 补齐，还需要决定它是 `equipment_refs` 里的一项，还是需要一个独立的"随身工具"投影。
3. **未决（二）**：`invisible` 的 `ends_on` 目前是 `["attack_roll", "spell_cast"]`，Stealth Attack 要求"这次攻击不结束它"。改动这条语义会影响所有依赖 `invisible` 的既有断言，需在解除停工后单独评估。
4. **未决（三）**：`unconscious` 条件存在，但"来源化终止、受伤只移除该来源"需要条件级来源标识。F15 的 `hamstrung` 只做到了"一目标一条件"，没有做到"来源级并存"，Knock Out 会比它更难。
5. **系统性观察**：F16 与 F17 连续停工出于同一原因——任务书假设的祖先基线（`integration/dnd2024-srd@35653f81`）比当前 main 多出若干前置层：区域几何（F16）、物品目录扩充与怪物尺寸/Cover（F17）。这不是两份任务书写错，而是切片顺序把"模型前置"排在了消费者之后。建议在继续 F18–F29 之前先确认这些前置是否已被别的切片覆盖，否则后续切片可能重复遇到同一类停止。
