# 05 规则集与内容系统

> 核心目录：[src/rules/](../../src/rules/) · [src/rulesets/](../../src/rulesets/) · [src/adventures/](../../src/adventures/) · [src/content/](../../src/content/) · [src/lorebook/](../../src/lorebook/) · [src/memory/](../../src/memory/)

## 1. 两套规则路径

DiceFrame 同时存在两套规则实现，二者不是替代关系：

| 路径 | 位置 | 适用 |
|---|---|---|
| Legacy `RuleSystem` | `src/rules/` | 自定义 d20 / d100 / 无骰叙事、轻量规则 |
| Versioned Ruleset Runtime | `src/rulesets/` | 需要 canonical identity、权威事件、确定性战斗的完整规则（D&D 2024） |

规则模板通过显式 binding 选择 runtime：

```json
{
  "runtime": { "id": "core:dnd2024", "minimum_version": 1 }
}
```

缺少 `runtime` 时默认 `core:legacy`。**不通过**规则名、显示语言、`dice_system == "d20"` 或 `rule_id` 前缀猜测 runtime。

---

## 2. Legacy RuleSystem

实现：[src/rules/rule_system.py](../../src/rules/rule_system.py)、[src/rules/loader.py](../../src/rules/loader.py)。

### 2.1 职责

- 加载规则模板 JSON（支持 `extends` 深合并）；
- 声明属性、技能、特殊属性；
- 声明骰子系统与检定机制；
- 声明意图（intent）与别名匹配；
- 声明 HP 公式、伤害、护甲、死亡、冲突与成长；
- 提供 GM prompt 的规则片段。

### 2.2 关键方法

| 方法 | 作用 |
|---|---|
| `RuleSystem.load(path)` | 加载模板 |
| `path_for(rules_dir, rule_id, language)` | 定位规则文件 |
| `intents()` / `find_intent(...)` | 意图识别 |
| `intent_skill_candidates(...)` | 意图对应技能 |
| `dice_system` / `check_mechanic` / `advantage_mechanic` | 骰子与检定参数 |
| `damage_mechanic` / `armor_model` / `death_mechanic` | 战斗参数 |
| `combat_model` / `conflict_model` | 战斗模型 |
| `growth_system` / `hp_formula` | 成长与 HP |
| `dc_table` / `dc_for_difficulty(...)` | DC 表 |
| `mechanics_snapshot()` | 规则摘要 |

公式求值使用 AST 白名单（`_safe_eval` / `_eval_node`），只允许受限变量与运算。

---

## 3. Ruleset Runtime

### 3.1 Registry

实现：[src/rulesets/registry.py](../../src/rulesets/registry.py)、[src/rulesets/builtin.py](../../src/rulesets/builtin.py)。

```text
RulesetRuntimeRegistry
├─ LegacyRulesetAdapter      (core:legacy)
└─ Dnd2024Runtime            (core:dnd2024)
```

关键方法：

| 方法 | 作用 |
|---|---|
| `register(runtime)` | 注册，校验 `runtime_id` 与正整数 `runtime_version` |
| `get(runtime_id, minimum_version=1)` | 解析并检查最低版本 |
| `resolve(template)` | 从模板 binding 解析 runtime |
| `describe(template)` | 返回 JSON-safe metadata |
| `runtime_ids()` | 已注册 ID |
| `set_adventure_resolver(resolver)` | 注入唯一冒险解析器 |
| `set_module_content_sources(provider)` | 注入模组内容来源 |

错误类型：`DuplicateRulesetRuntimeError`、`UnknownRulesetRuntimeError`、`IncompatibleRulesetRuntimeError`、`InvalidRulesetBindingError`。

### 3.2 主协议

[src/rulesets/contracts.py](../../src/rulesets/contracts.py)：

```python
class RulesetRuntime(Protocol):
    runtime_id: str
    runtime_version: int
    capabilities: RulesetCapabilities

    def describe_experience(rule, locale) -> dict
    def builder_choices(rule, draft) -> dict
    def validate_character(rule, draft) -> list[str]
    def derive_character(rule, draft) -> dict
    def finalize_character(rule, draft) -> dict
    def normalize_character_submission(rule, character, locale="") -> dict

    def available_intents(instance, actor_id) -> list[dict]
    def validate_intent(instance, intent) -> dict
    def resolve_intent(instance, intent, rng) -> dict
    def apply_event_batch(instance, batch) -> dict

    def gameplay_view(instance, viewer_id="", viewer_is_gm=False) -> dict
    def build_llm_view(instance) -> dict
    def project_legacy_character(character) -> dict
    def migrate_state(payload, from_version) -> dict
```

主协议偏宽，新增能力优先通过可选 Protocol 扩展：

```text
RunFinaleRuntime
CurrentSceneRuntime
CheckModePolicyRuntime
VersionedStateRuntime
AuthoritativeIntentHooks
NarrativeHealthRuntime
NarrativeStatePolicyRuntime
NarrativeCombatSignalRuntime
NarrativeCheckPolicyRuntime
NarrativeAdvancementRuntime
NarrativeDirectorRuntime
NarrativeDirectorAutomationRuntime
NarrativeDirectorPlanningRuntime
TemporaryEncounterPlannerRuntime
AutomaticIntentRuntime
HostedIntentChoiceRuntime
GameDetailProjectionRuntime
IntentResultProjectionRuntime
PlayerJoinRuntime
CharacterRevivalRuntime
CharacterDeathStateRuntime
LiveAdvancementPolicyRuntime
LiveAdvancementTransactionRuntime
AdventureBindingMigrationRuntime
RunLifecycleRuntime
PublicTimelineProjectionRuntime
CharacterStateReconciliationRuntime
CharacterItemPreparationRuntime
```

### 3.3 Capabilities

`RulesetCapabilities` 是 API 客户端可见的功能开关，不能让客户端推断“名字像 D&D 就会战斗”：

| 字段 | 含义 |
|---|---|
| `experience_profile` | 体验类型 |
| `character_builder` | `legacy` / `guided` / `professional` |
| `character_lifecycle` | `legacy` / `rules_aware` |
| `authoritative_intents` | 是否使用权威 intent |
| `deterministic_combat` | 是否确定性战斗 |
| `versioned_state` | 是否版本化状态（必须实现 `VersionedStateRuntime`） |
| `session_zero` | 是否支持 Session 0 |
| `tutorial_coach` | 是否支持教程引导 |
| `narrative_turns` | 是否支持叙事回合 |
| `adventure_formats` | 支持的冒险格式 |
| `combat_action_effects` | 通用战斗动作效果 |
| `combat_resource_pools` | 通用资源池 |
| `combat_scheduler` | `""` / `round_robin` / `initiative` / `threshold` |

### 3.4 Ruleset Bundle

实现：[src/rulesets/bundle.py](../../src/rulesets/bundle.py)。

- `RulesetBundleLoader` 读取 manifest、规则、内容与 locale；
- `LoadedRulesetBundle` / `RulesetBundleManifest` 是运行时只读对象；
- 校验禁止可执行内容（`_validate_no_executable_content`）与非法 effects；
- canonical ID 与显示名分离，locale 只翻译展示字段。

```text
ruleset bundle
├─ manifest
├─ rule
├─ content catalogs
└─ locales/<lang>/*
```

### 3.5 Legacy Adapter

[legacy_adapter.py](../../src/rulesets/legacy_adapter.py) 把旧 `RuleSystem` 包装成 `RulesetRuntime`，使旧规则也能进入统一 registry，但**不获得** D&D 专属能力。

---

## 4. D&D 2024 Runtime

入口：[src/rulesets/dnd2024/runtime.py](../../src/rulesets/dnd2024/runtime.py) 的 `Dnd2024Runtime`（约 1500 行），按领域拆分为子包。

| 子域 | 目录 | 职责 |
|---|---|---|
| 角色 | `character/` | builder、validation、derivation、reconciliation |
| 战斗 | `combat/` | validation、resolution、reducer、view、action_adapter、catalog、triggered/reaction spells |
| Campaign | `campaign/` | Session 0、campaign facts、事件 |
| 职业特性 | `features/` | 特性目录、资源、装备前提、战斗/装备解析 |
| 进阶 | `progression/` | 升级表、advancement |
| 休息 | `resting/` | 短休/长休规则 |
| 法术 | `spells/` | 法术目录、选择、专长法术 |
| 探索 | `exploration/` | 探索施法/行动 |
| Director | `director/` | 导演提案与上下文 |
| 叙事时间线 | `play/` | 公共里程碑、遭遇访问 |
| 结团 | `finale.py` | 最终结算 preflight / settle |
| 叙事 HP | `narrative_health.py` | 非战斗阶段 HP 变更 |
| 升级权限 | `advancement_access.py` | 成长模式、XP、授权 |

### 4.1 权威事件流

```text
Intent
  → validate_intent
  → resolve_intent (rng)
  → EventBatch
  → apply_event_batch
  → reducer
  → modules.ruleset_runtime.state / event_ledger
  → gameplay_view / LLM view
```

规则状态权威位于 `modules.ruleset_runtime`：

```text
binding
state
event_ledger
```

reset 保留 binding、重建 state、清空 ledger。

### 4.2 战斗

```text
combat/validation.py     校验动作合法性
combat/resolution.py     命中/伤害/豁免结算
combat/reducer.py        将事件写入 canonical combat state
combat/view.py           投影给前端
combat/engine.py         遭遇编排
```

要求：

- 先校验、再 resolve、最后 reduce；
- LLM 只叙述已确认结果；
- 没有正式遭遇权威时返回中立视图；
- `combat/` 不得依赖 `campaign/` 或 `webui/`。

### 4.3 角色生命周期

```text
builder_choices
  → validate_character
  → derive_character
  → finalize_character
  → normalize_character_submission
  → ruleset_character
```

升级、休息、复活、死亡状态通过可选 runtime 能力接入；叙事 HP 在非战斗阶段走版本化 EventBatch。

### 4.4 Class Feature Runtime v1

`features/` 提供：

- 参数化特性目录（`class_feature_catalog`）；
- 职业资源投影与 resize policy；
- 装备前提与 capability 投影；
- 复用既有 combat / rest / advancement authority。

新增特性通常只需扩 catalog 与 resolver，不改通用 engine。

### 4.5 Director 与临时遭遇

- `director/context.py` 构建上下文；
- `director/decision_resolver.py` 生成 `DirectorProposal`；
- `runtime.director_proposal(...)` / `director_automatic_intent(...)`；
- 临时遭遇通过 `TemporaryEncounterPlannerRuntime` 提案，仍需验证后落库。

---

## 5. 冒险包（Adventure Bundle）

目录：[src/adventures/](../../src/adventures/)。

| 文件 | 职责 |
|---|---|
| `bundle.py` | 冒险包加载与校验 |
| `registry.py` | 冒险来源注册（builtin / user / plugin） |
| `resolver.py` | 唯一 `AdventureResolver` |
| `graph_v2.py` | 节点图结构 |
| `progress.py` | 进度推进 |
| `gates.py` | 门控条件 |
| `outcomes.py` | 结果 |
| `materialization.py` | 世界种子物化 |
| `scene_context.py` | 场景上下文投影 |
| `runtime_validation.py` | 运行时校验 |
| `external_import.py` / `script_import.py` / `story_draft.py` | 外部导入与草稿 |
| `compatibility.py` | 旧格式兼容 |

### 5.1 不可变绑定

创建对局时写入 `adventure_binding`，包含冒险身份、版本与 runtime 要求。之后：

- 冒险内容更新不自动改写已绑定对局；
- 迁移必须显式、可验证；
- 无法证明安全时 fail closed。

### 5.2 冒险与世界书

冒险可以引用世界书条目；世界书内容属于 `LorebookStore`，冒险包只保存引用与展示信息。避免同一份设定存在两个权威副本。

---

## 6. Content V2 与内容模块

目录：[src/content/](../../src/content/)、[src/content_modules/](../../src/content_modules/)。

### 6.1 核心原则

- canonical identity 与 display name 分离；
- locale 只翻译展示字段，不改变 mechanics；
- 旧格式通过 `src/compat/` 与兼容管线进入新模型；
- 世界 identity 自动升级 fail closed，不覆盖用户改动。

### 6.2 主要模块

| 文件 | 职责 |
|---|---|
| `content/worlds.py` | 世界模板 |
| `content/rule_locale.py` / `locale.py` | 规则 locale |
| `content/gm_style.py` | GM 风格 |
| `content/contracts.py` | 内容契约 |
| `content_modules/refs.py` | 内容引用 |
| `content_modules/plan.py` | 导入计划 |
| `content_modules/projection.py` | 内容投影 |
| `content_modules/receipts.py` | 导入回执 |
| `content_modules/sync.py` | 内容同步 |

### 6.3 模板同步

启动时 `sync_builtin_templates()` 把仓库内 `templates/` 同步到 `data/templates/`。系统模板不得无条件覆盖用户数据；同步策略与冲突处理由 `src/template_catalog.py` 与内容恢复服务负责。

---

## 7. 世界书（Lorebook）

目录：[src/lorebook/](../../src/lorebook/)。

### 7.1 数据模型

SQLite schema 当前为 **12**。表模型见 [models.py](../../src/lorebook/models.py)：

| 表 | 含义 |
|---|---|
| `worlds` | 世界 |
| `lorebooks` | 世界书（多个 Book 可属于同一世界） |
| `lorebook_bindings` | 世界书与作用域绑定 |
| `lorebook_entries` | 条目（关键词、内容、激活模式、可见性等） |
| `lorebook_embeddings` | 语义检索派生缓存 |

### 7.2 存储 API

[store.py](../../src/lorebook/store.py) 的 `LorebookStore`：

- 世界：`create_world` / `get_world` / `update_world_metadata` / `delete_world_cascade`；
- 世界书：`create_lorebook` / `update_lorebook` / `delete_lorebook` / `list_lorebooks`；
- 绑定：`bind_lorebook` / `update_binding` / `list_bindings`；
- 条目：`add_entry` / `add_book_entry` / `update_entry` / `move_entry` / `delete_entry`；
- 检索：`search_entries` / `search_book_entries`；
- 缓存：`load_embedding_cache` / `save_embedding_cache`；
- 事务：`transaction()`；连接使用 WAL。

### 7.3 关键词匹配

[matcher.py](../../src/lorebook/matcher.py) 的 `KeywordMatcher` 负责：

- 关键词 / 正则匹配；
- 大小写与语言归一；
- 优先级、递归扫描；
- 触发条件。

### 7.4 Hybrid 检索

[retrieval.py](../../src/lorebook/retrieval.py) 的 `LoreRetriever`：

```text
action + scene + canonical location + present NPC
  → build_lore_retrieval_queries(...)
  → 关键词候选 (KeywordMatcher)
  → 可选语义候选 (EmbeddingClient)
  → _merge_and_sort(...)
  → 可见性过滤
  → token budget / book budget
  → timed state (sticky / cooldown / delay)
  → activation trace
```

关键行为：

- 所有标准 ruleset 共用同一 `LoreRetriever`；
- embedding 复用 `MemoryStore.embedding_client`，不新建第二套配置；
- 无 embedding 或 embedding 失败时自动 lexical fallback；
- WorldState / Ruleset authority 高于 Lorebook；
- 检索层不拥有 mechanics authority。

### 7.5 可见性

- 条目有 GM / player 可见范围；
- 玩家安全上下文使用 `filter_player_visible_lorebook_entries(...)`；
- 私密条目不得进入玩家投影或 Bot 输出。

### 7.6 导入 / 导出 / 同步

| 文件 | 职责 |
|---|---|
| `importer.py` / `import_plan.py` | 导入计划与执行 |
| `exporter.py` | 导出 v3 / native |
| `sync.py` | `LorebookSyncImporter` / `LorebookSyncExporter` |
| `bootstrap.py` | 内置世界种子 |
| `trace.py` | 激活轨迹 |

导入遵循“先计划、再预览、最后提交”，冲突时保留用户数据。

---

## 8. 长期记忆（Memory）

目录：[src/memory/](../../src/memory/)。

### 8.1 存储

[delta.py](../../src/memory/delta.py) 的 `MemoryStore`：

- SQLite，WAL；
- 表：`memory_entries`、`memory_economy_deliveries`；
- 字段包含 `memory_kind`（authoritative_world / soft / legacy_soft）、来源、世界 revision、可见性；
- 每个 run 使用独立 `memory_namespace`。

### 8.2 写入路径

```text
回合提交
  → memory delta
  → GameInstance memory outbox
  → MemoryStore.apply_delta(...)
  → 可选生成 embedding
```

`apply_economy_delta` / `reverse_economy_delta` 保证经济相关记忆可回滚。

### 8.3 召回

| 方法 | 作用 |
|---|---|
| `recall(...)` | 关键词召回 |
| `recall_by_text(...)` | 文本召回 |
| `recall_by_vector(...)` | 向量召回 |
| `list_entries(...)` / `count_entries(...)` | 管理页面 |
| `flush_pending_embeddings()` / `embed_all_pending(...)` | 补 embedding |

[summarizer.py](../../src/memory/summarizer.py) 负责长会话摘要；[recall.py](../../src/memory/recall.py) 负责召回编排。

> 旧记忆保持 `legacy_soft`，不会自动升级为世界权威。

---

## 9. 关键类与函数速查

| 符号 | 位置 | 说明 |
|---|---|---|
| `RuleSystem` | [rule_system.py](../../src/rules/rule_system.py) | Legacy 规则 |
| `RulesetRuntimeRegistry` | [rulesets/registry.py](../../src/rulesets/registry.py) | runtime 注册与解析 |
| `RulesetRuntime` | [rulesets/contracts.py](../../src/rulesets/contracts.py) | 主协议 |
| `RulesetCapabilities` | 同上 | 能力开关 |
| `RulesetBundleLoader` | [rulesets/bundle.py](../../src/rulesets/bundle.py) | bundle 加载 |
| `Dnd2024Runtime` | [dnd2024/runtime.py](../../src/rulesets/dnd2024/runtime.py) | D&D 2024 权威 |
| `AdventureResolver` | [adventures/resolver.py](../../src/adventures/resolver.py) | 唯一冒险解析器 |
| `AdventureBundleLoader` | [adventures/bundle.py](../../src/adventures/bundle.py) | 冒险包加载 |
| `LorebookStore` | [lorebook/store.py](../../src/lorebook/store.py) | 世界书存储 |
| `KeywordMatcher` | [lorebook/matcher.py](../../src/lorebook/matcher.py) | 关键词匹配 |
| `LoreRetriever` | [lorebook/retrieval.py](../../src/lorebook/retrieval.py) | Hybrid 检索编排 |
| `MemoryStore` | [memory/delta.py](../../src/memory/delta.py) | 长期记忆 |
| `EmbeddingClient` | [memory/embedding.py](../../src/memory/embedding.py) | 向量客户端 |

---

## 10. 新增规则的检查清单

- [ ] 是 legacy 轻量规则，还是需要完整 runtime？
- [ ] 是否声明了显式 `runtime.id` 与 `minimum_version`？
- [ ] 是否只通过 capability 暴露能力，而不是让前端猜？
- [ ] canonical ID / display name / locale 是否分离？
- [ ] 是否违反 ruleset 隔离（例如在 generic engine 加分支）？
- [ ] 是否补充 bundle、角色、战斗、迁移测试？
- [ ] 是否更新 `docs/rulesets/` 对应文档？
