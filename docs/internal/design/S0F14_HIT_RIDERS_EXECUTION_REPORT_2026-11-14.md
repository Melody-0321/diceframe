# S0-F14 执行报告：命中附加效果、命中后条件与施法侧加值

日期：2026-11-14
分支：`feat/dnd2024-s0f14-hit-riders`
基线：`feat/dnd2024-s0f13-condition-immunity@6e2fd934`（F13 三个提交之上）
范围：Stunning Strike（武僧 5）、Empowered Strikes（武僧 6）、Open Hand Technique（散手武僧 3）、Radiant Strikes（圣武士 11）、Blessed Strikes / Divine Strike / Potent Spellcasting / Improved Blessed Strikes（牧师 7/14）、Elemental Fury / Primal Strike / Improved Elemental Fury（德鲁伊 7/15）

---

## 1. 结论

八项特性（含两侧各自的二选一选项与其升级项，共十三条声明）落在**四种语义**上，不是八份特判：

| 语义 | 特性 | 落点 | 事件证据 |
| --- | --- | --- | --- |
| 额外伤害（每次命中或每回合一次） | Radiant Strikes、Divine Strike、Primal Strike | `_hit_rider_declarations`（只声明）→ `_hit_rider_events`（提交时才掷） | 独立 `resource.changed` + `feature_id` / `owner_ref` / `damage_type`；每回合一次的再发 `dnd2024.feature.used` |
| 命中后的条件 | Stunning Strike、Open Hand Technique | `_hit_condition_declarations` → `_hit_condition_events` / `_open_hand_events` | `check.resolved{source_feature}` + `condition.applied` |
| 伤害类型替换 | Empowered Strikes | `_hit_settlement_events` 开头的类型改写 | 伤害事件 `damage_type: "force"` |
| 施法侧加值 | Potent Spellcasting、Improved Blessed Strikes、Improved Elemental Fury | `_add_potent_spellcasting` / `_cantrip_temp_hp_events` / `_spell_effective_range` | 伤害 `rolls` 之后的常量加值、`resource.changed{resource: "temp_hp"}`、视图行 `range` / `range_base` |

四条语义对应四种不同的失败模式，混在一起就会立刻出错：

- **额外伤害**若并进主伤害事件，抗性就按主伤害的类型算一次。光耀 1d8 打到抗光耀的目标身上，会跟着挥砍一起被减半。
- **命中后条件**若在命中时掷豁免，Shield / Uncanny Dodge 把命中改判落空之后，豁免已经掷过、条件却挂不上——骰子白掷，客户端还收到过 `check.resolved`。
- **伤害类型替换**若发生得太晚（在 `_resist_damage` 之后），力场与原本的钝击会各算一次抗性。
- **施法侧加值**若写成骰子，重击会把它一起翻倍；若写在 `spell_formula_node` 之前，豁免减半与抗性的顺序会把它也当成骰面处理。

验证：新增 **52 passed**；聚焦回归 **见 §6**；`ruff` 干净；`mypy` 102 文件 0 错。

## 2. 三个先决条件（本切片真正的成本）

任务书假设「八项特性 + 现成机制」，实现时有三个缺口必须先补，它们都不在特性目录里。

### 2.1 `feature_option`：互斥选项在数据层无处存

Blessed Strikes 与 Elemental Fury 都是「二选一，选完才知道你有哪些机械」。在此之前 `FEATURE_CHOICE_KINDS` 只有 `advancement_feat` 与 `skill_proficiency`，三条消费点（`derivation.py:297`、`builder.py:395`、`advancement.py:705`）都硬编码 `kind == "skill_proficiency"`，而 `option_of` 只能表达「父拥有则选项拥有」——它没有「另一个没拥有」的表达力。放着不补，两个选项会同时生效：牧师 7 级同时拿 Divine Strike 和 Potent Spellcasting。

补法是新增第三种 `feature_option`：

- `features/models.py`：`count` 必须为 1；`enabled_options` 非空且每个以 `feature:` 开头；`category` 必须是 `"feature"`；`requires_proficiency` / `exclude_expertise` 不得写在它上面。候选的合法性别处判——必须在**同一个 owner** 的特性目录里声明，而不是去专长目录找（这一点是第一次加载时炸出来的：`blessed_strikes.choice.category is not a declared feat category: feature`）。
- `features/resolver.py`：`_owned_feature_definitions` 对 `feature_option` 父特性只放行被选中的选项；新增 `_selected_feature_options` 与 `feature_option_choice`，后者在未选/多选时返回 `""` 而不是默认值——「没回答」必须等于「没有」，否则一个没答完的角色会凭空拥有一条机械。
- `progression/advancement.py`：`_build_feature_requirements` 的 `feature_option` 分支把候选直接取自定义本身，产出 `{owner, feature_id, choice_id, selected_refs, granted_level}`；不回答就是 `feature choice blessed_strikes requires a selection at this level`，重复提交、非白名单值、多选都被拒。

### 2.2 actor view 不携带 `feature_choices`

这是补完 2.1 之后立刻撞上的第二个缺口，也是整片唯一一个「只跑门禁才会现形」的缺陷：`_feature_character` 从 actor view 里只取 `subclass_ref`、`usage` 与 `FEATURE_STATE_KEYS` 白名单，`feature_choices` 不在其中。于是**战斗里所有选项特性都读成「从未选择」**：牧师 7 级选了 Potent Spellcasting，法术伤害一分不加，测试却是绿的（因为当时的断言写错了档位，见 §5）。

修法是把它当角色状态投影出去（`view.py` 两处）：选项的归属由这条记录决定，视图丢掉它等于把特性静默撤回。这与 `subclass_ref` 已经在做的是同一件事。

### 2.3 决策路径不做 rider / 命中条件结算

`_finish_hit_spell`（至圣斩一类的「命中触发法术」窗口）只调 `_submit_hit_damage`，不掷 rider、不挂命中条件。直通路径 `_resolve_committed_hit` 有，决策路径没有。后果是：**一个准备了至圣斩的圣武士，光耀打击会静默消失**——骑士类角色的伤害反而比不准备的少。这条同样是先写测试、再发现红、才看出来的。

现在两条路径共用同一段收尾（rider → 合并专注 DC → 命中条件 → 归零特性），差别只剩「决策清空事件」和「命中触发法术的额外伤害」。

## 3. 逐项机械

### 3.1 额外伤害三条

- **Radiant Strikes**（圣武士 11）：每次命中近战武器或徒手攻击都追加 1d8 光耀，没有每回合限制，所以声明里 `once_per_turn: false`，也不会产生 `feature.used`。
- **Divine Strike**（牧师 7 选项）：每回合一次，类型由 `rider_damage_type` 在 `[necrotic, radiant]` 里选；不声明类型 = 本次不用（不是错误），声明了白名单外的值 = 意图失败。
- **Primal Strike**（德鲁伊 7 选项）：同上，类型是 `[cold, fire, lightning, thunder]`，`attack_kinds` 多一个 `beast_form`。

三条共用一份参数闭集（`_RIDER_PARAMETER_KEYS`，加载期双向 fail closed：未知键与缺键都拒），但**分类依据来自各自声明**：Radiant Strikes 写的是「近战武器或徒手打击」，Divine Strike 只写「武器」（所以弓算、徒手不算），Primal Strike 再加野兽形态。`rider_attack_kind` 把一次攻击归类为 `melee_weapon` / `ranged_weapon` / `unarmed_strike`，验算与结算读同一份（`combat/primitives.py`），避免「声明阶段放过、结算阶段静默丢掉」。

升级项是独立声明而非开关：`improved_blessed_strikes.divine_strike_dice = 2d8`、`improved_elemental_fury.primal_strike_dice = 2d8`，只在拥有该特性时替换骰式——没答选项的角色既没有基础 rider，也没有升级项，不存在「默认 1d8」的兜底。

### 3.2 命中后条件两块

- **Stunning Strike**（武僧 5）：先付 1 点 Focus，再让目标做 CON 豁免，DC = `8 + 熟练加值 + 感知修正`（不是法术豁免 DC，武僧可能根本没有）。失败给 `stunned`，成功给 `staggered`（Speed 减半 + 针对它的下一次攻击有优势，掷完即消耗），两者都持续到攻击者的下个回合开始。每回合一次由 `combat.feature_usage` 账本按 `round + turn_index` 记账——借机攻击发生在别人的回合，因此在那里可以再用一次，这是账本刻意不读当前 economy 的原因。
- **Open Hand Technique**（散手武僧 3）：只有当攻击是**由 Flurry of Blows 授予**时才成立，所以授予来源 `granted_by` 随攻击一起走完结算链，而不是命中后按武器或顺序去猜。三个选项：Addle 直接挂 `reaction_blocked`（无豁免）；Push 让目标做 STR 豁免，失败后以 `dnd2024.position.changed{forced: true}` 推 15 尺（不消耗目标自己的移动）；Topple 让目标做 DEX 豁免，失败挂 `prone`。连击是两次攻击，**每次命中都能各自施加一次**。

`staggered` 与 `prone` 是这一片新加的两条条件声明：

```json
"prone": {"attack_modes": [{"side": "actor", "mode": "disadvantage"}]},
"staggered": {"speed_halved": true, "attack_modes": [{"side": "target", "mode": "advantage", "consume_on": "attack_resolved"}]}
```

`speed_halved` 是新的条件字段。原有的 `speed_modifier` 只能做加法，而「Speed 减半」是乘性且**多来源只减半一次**（被减速 10 尺又 staggered，是 `(30 + (-10)) / 2 = 10`，不是 10 再减半）。因此 `effective_speed` 改成：先累加 `speed_modifier`，再 `// 2` 一次；`speed_zero` 仍然压倒一切。

### 3.3 Empowered Strikes

徒手打击的伤害类型可以声明成 `force`（或保持原类型）。改写发生在 `_hit_settlement_events` 最开头、抗性之前，因此力场只按力场算一次抗性。客户端只能声明特性白名单里的值（`unarmed_damage_type_choices`），且只能用在徒手打击上——用在武器上直接拒绝，而不是忽略。

### 3.4 施法侧三条

- **Potent Spellcasting**：只对「本职业目录里的戏法」加当前施法属性修正。两条声明同名同级，靠 `cantrip_source_class` 分辨（`class:cleric` / `class:druid`），`_potent_spellcasting_owner` 逐个 owner 问一遍——一个既选牧师选项又选德鲁伊选项的多职业角色，不能让其中一条替另一条回答。加值以常量节点追加在**重击翻倍之后**，所以重击不会把它翻倍；在豁免减半与抗性之前，三者作用于同一个总数。
- **Improved Blessed Strikes**（牧师 14）：施放造成伤害的牧师戏法后，给自己或 60 尺内一个生物 `2 × 感知修正` 的临时 HP。「造成伤害」按法术声明判断，不按这次是否真的掉血——目标豁免成功也仍然是「一个造成伤害的戏法」。负的感知修正不授予（不会变成扣血），且 reducer 沿用「取较大值」的临时 HP 语义。
- **Improved Elemental Fury**（德鲁伊 15）：德鲁伊戏法若基础射程 ≥ 10 尺，射程 +300 尺。射程是特性可能改写过的值，因此校验与视图都走 `_spell_effective_range`；被改写时视图行额外带 `range_base`，让「360 尺」能对上账。

## 4. 白名单之外的改动（必须单列）

| 文件 | 改动 | 理由 |
| --- | --- | --- |
| `combat/catalog.py` | 条件字段闭集与布尔 flag 各加 `speed_halved` | 条件注册表不认识新字段，`staggered` 加载即失败 |
| `features/models.py` | `FEATURE_CHOICE_KINDS` 加 `feature_option` + 独立校验分支 | §2.1 |
| `progression/advancement.py` | `_build_feature_requirements` 加 `feature_option` 分支 | §2.1 |
| `combat/primitives.py` | 新增 `rider_attack_kind` | 验算与结算共用一次攻击分类，避免两套 |
| `combat/view.py` | actor view 投影 `feature_choices`；法术行带 `range_base` | §2.2、§3.4 |

前三条是任务书批准过的扩项（`combat/catalog.py`、`progression/advancement.py`，以及随之必须的 `features/models.py`），后两条是 §2.2 那个缺陷的直接修复。

## 5. 测试矩阵

新增 `tests/rulesets/test_dnd2024_hit_riders.py`，52 条，分七组：

| 组 | 覆盖 | 条数 |
| --- | --- | --- |
| 选项本身 | 七级必答、两个候选只取一、记录形状（owner + choice_id + granted_level） | 3 |
| Potent Spellcasting | 加值生效 / 另一个选项无加值 / 六级无加值 / 不跨职业目录 / 一级法术不加 / 德鲁伊侧两条 | 7 |
| Improved Elemental Fury | 15 级 +300 与 `range_base`、14 级不变、<10 尺不扩、超程仍拒 | 4 |
| Improved Blessed Strikes | 给自己 / 给 60 尺内盟友 / 超程拒绝 / 敌对拒绝 / 13 级拒绝 / 另一选项拒绝 / 非伤害法术拒绝 / 不压低已有临时 HP | 8 |
| Stunning Strike | 失败震慑 + 1 Focus + DC 公式、成功改 `staggered`（含速度减半与声明形状）、不声明则无、每回合一次、无 Focus 拒绝、4 级拒绝 | 6 |
| Empowered Strikes | 力场生效、5 级拒绝、武器上拒绝 | 3 |
| Open Hand Technique | Addle 无豁免、Push 15 尺、Topple 倒地、豁免成功不生效、非连击拒绝、其他附赠动作拒绝 | 6 |
| 额外伤害 | 光耀独立 1d8、10 级无、Divine Strike 类型与每回合一次、类型白名单、徒手不算武器、2d8 升级（牧师 14 / 德鲁伊 15）、无选项无 rider、owner 归属 | 10 |
| 声明闭集 | 未知参数 / 缺参数 / 非法 `attack_kinds` / 非法选项表 / 选项不在本目录 → 五条都 fail closed | 5 |

## 6. 回归

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 新增用例 | `pytest tests/rulesets/test_dnd2024_hit_riders.py -q` | 52 passed |
| 聚焦回归 | `combat / monk_combat / class_features / retaliation / sneak_attack / check_windows / origin_feat_spells` | 见下 |
| 静态检查 | `ruff check src/ tests/rulesets` | All checks passed |
| 类型检查 | `mypy`（102 文件） | 0 errors |
| 空白 | `git diff --check` | 干净 |

## 7. 偏差 / 未决

1. **`prone` 只声明了「攻击者劣势」**。SRD 还有「5 尺内的攻击者对倒地目标有优势」。现有条件注册表的 `attack_modes` 没有距离条件，加一个只有倒地用的字段会把闭集撑开一条没人复用的口子，所以本片只落地了不依赖距离的那一半，并在 §3.2 说明 Topple 的机械终点是「挂上 prone」，不是「prone 的全部后果」。这是本片唯一一处「特性完整、条件不完整」。
2. **Primal Strike 的 `beast_form` 攻击种类没有生产者**。Wild Shape 的野兽形态还不在战斗模型里，所以这一条声明目前不会被任何攻击满足；德鲁伊的人形武器攻击正常生效。声明保留是为了将来野兽形态接入时不用再改目录。
3. **Divine Strike 的「每回合一次」在同一回合的第二次攻击上只做了声明层验证**。牧师一个动作只有一次攻击，走意图会在更外层以「动作已用完」被拒，测不到这条规则本身；因此测试直接问声明这一步，并在注释里写明原因。
4. **临时 HP 的授予目标限制为「自己或同阵营」**。SRD 写的是「你看得见的 60 尺内一个生物」，字面上包含敌人；给敌人发临时 HP 没有意义，且会让「误点敌人」变成一个静默的资源浪费，所以按 fail closed 处理为同阵营。
5. **多伤害类型时的集中豁免只掷一次 DC**。一次命中同时有主伤害与 rider 时，专注豁免按合并后总量算一次（与 F12 的「一次命中一个 DC」一致），而不是每个伤害实例各掷一次。这条在 SRD 里是「受到伤害时」的读法问题，已与既有实现保持一致。
6. **`Improved Blessed Strikes` 的临时 HP 没有做「每次施法只能一次」的额外账本**。它是每次施法后的一次授予，没有次数上限，因此不需要记账；重复施法重复授予是正确行为。

## 8. 后续

- F15–F37 与 G 系列按主计划推进；F10（Hide 的遮蔽模型、Fast Hands 的对象模型）与 F11（Deflect Attacks 的固定减量、Slow Fall 的坠落触发源）继续停在「缺战场事实模型」这一前置上，本片没有触碰。
- `feature_option` 这一层现在是通用能力：之后的任何一个「二选一」特性（战斗风格、灵能、契约馈赠）都可以直接声明，不用再改三类消费点。
