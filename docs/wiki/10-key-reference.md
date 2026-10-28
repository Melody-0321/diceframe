# 10 关键类与接口速查

> 本页用于日常查代码。符号较多时优先看“位置”列，再到源码确认签名。

## 1. 后端模块与关键符号

### 1.1 启动 / Web

| 符号 | 位置 | 说明 |
|---|---|---|
| `web_server` 模块级启动 | [web_server.py](../../web_server.py) | 配置、监听、优雅关闭 |
| `create_app` | [src/webui/application.py](../../src/webui/application.py) | aiohttp app 工厂 |
| `ApplicationDependencies` | 同上 | app 显式依赖 |
| `register_routes` | 同上 | 路由注册 |
| `RuntimeComposition` | [src/webui/composition.py](../../src/webui/composition.py) | 依赖图装配 |
| `RuntimePaths` / `RuntimeConfig` / `ConfigStore` | [src/webui/runtime_config.py](../../src/webui/runtime_config.py) | 路径与配置 |
| `WebUIBootstrap` | [src/webui/bootstrap.py](../../src/webui/bootstrap.py) | 启动/恢复/后台任务 |
| `ConfigController` | [src/webui/config_controller.py](../../src/webui/config_controller.py) | 热重载/重启 |
| `WebAPI` | [src/webui/api.py](../../src/webui/api.py) | 业务 facade |
| `WebAccessControl` | [src/webui/access_control.py](../../src/webui/access_control.py) | 身份/中间件 |
| `SessionManager` | [src/webui/session.py](../../src/webui/session.py) | 会话 |
| `DeviceTokenStore` | [src/webui/device_tokens.py](../../src/webui/device_tokens.py) | 设备令牌 |
| `PairingService` | [src/webui/pairing.py](../../src/webui/pairing.py) | 扫码配对 |
| `SseTicketStore` | [src/webui/sse_ticket.py](../../src/webui/sse_ticket.py) | SSE ticket |
| `AbuseGuard` | [src/webui/abuse_guard.py](../../src/webui/abuse_guard.py) | 限流/滥用防护 |
| `ServerTransport` | [src/web_transport/transport.py](../../src/web_transport/transport.py) | 监听语义 |
| `build_listener_plan` / `start_listeners` | [src/web_transport/listeners.py](../../src/web_transport/listeners.py) | 监听拓扑 |

### 1.2 对局与回合

| 符号 | 位置 | 说明 |
|---|---|---|
| `GameInstance` | [src/engine/game_instance.py](../../src/engine/game_instance.py) | 单局聚合 |
| `GameRegistry` | 同上 | 槽位/存档 |
| `GameState` | [src/engine/game_state.py](../../src/engine/game_state.py) | 生命周期枚举 |
| `instance_lifecycle` | [src/engine/instance_lifecycle.py](../../src/engine/instance_lifecycle.py) | activate/pause/resume/end/reset |
| `GameHandler` | [src/commands/game_handler.py](../../src/commands/game_handler.py) | 编排 |
| `RoundProcessor` | [src/commands/round_processor.py](../../src/commands/round_processor.py) | 单轮 |
| `turns.submit_action` | [src/webui/services/turns.py](../../src/webui/services/turns.py) | 行动入口 |
| `turns.resume_after_control_change` | 同上 | 控制权切换后继续 |
| `plan_round_checks` | [src/commands/check_planner.py](../../src/commands/check_planner.py) | 检定规划 |
| `normalize_check_specs` | 同上 | 检定规范化 |
| `build_check_request` / `roll_check_request` / `resolve_check_request` | [src/engine/checks.py](../../src/engine/checks.py) | 检定与掷骰 |
| `StateUpdateApplier` | [src/commands/state_update_applier.py](../../src/commands/state_update_applier.py) | 状态应用 |
| `fill_ai_player_actions` | [src/commands/ai_player.py](../../src/commands/ai_player.py) | AI 托管 |
| `CombatResolver` | [src/commands/combat_resolver.py](../../src/commands/combat_resolver.py) | Legacy 战斗 |
| `DiceResolver` | [src/commands/dice_resolver.py](../../src/commands/dice_resolver.py) | 骰子 |
| `PuzzleProcessor` | [src/commands/puzzle_processor.py](../../src/commands/puzzle_processor.py) | 谜题 |
| `ProgressionResolver` | [src/commands/progression_resolver.py](../../src/commands/progression_resolver.py) | 成长 |
| `PromptComposer` | [src/commands/prompt_composer.py](../../src/commands/prompt_composer.py) | 提示词 |
| `call_llm_with_tag_retry` | [src/commands/round_llm.py](../../src/commands/round_llm.py) | LLM 调用与重试 |
| `apply_parsed_data_to_response` | 同上 | 解析结果落地 |

### 1.3 引擎核心

| 符号 | 位置 | 说明 |
|---|---|---|
| `GameStateCodec` | [src/engine/game_state_codec.py](../../src/engine/game_state_codec.py) | 存档编解码 |
| `GamePersistedState` | [src/engine/game_state_contracts.py](../../src/engine/game_state_contracts.py) | 存档契约 |
| `persistence.save` / `load` / `recover_all` | [src/engine/persistence.py](../../src/engine/persistence.py) | 存档 IO |
| `StagedGameTransaction` | [src/engine/staged_transaction.py](../../src/engine/staged_transaction.py) | 原子规划发布 |
| `apply_world_ops` | [src/engine/world_state.py](../../src/engine/world_state.py) | WorldState 写入口 |
| `world_legality` | [src/engine/world_legality.py](../../src/engine/world_legality.py) | 行动合法性 |
| `world_events` | [src/engine/world_events.py](../../src/engine/world_events.py) | 定时事件 |
| `queue_proposal` / `resolve_proposal` | [src/engine/economy.py](../../src/engine/economy.py) | 经济 |
| `reverse_round_economy` | 同上 | 整轮回滚 |
| `queue_memory_delivery` | [src/engine/memory_outbox.py](../../src/engine/memory_outbox.py) | 记忆投递 |
| `module_hooks` | [src/engine/module_hooks.py](../../src/engine/module_hooks.py) | 生命周期钩子 |
| `module_state` | [src/engine/module_state.py](../../src/engine/module_state.py) | 模块槽校验 |
| `PlayerControl` 函数族 | [src/engine/player_control.py](../../src/engine/player_control.py) | 席位控制 |
| `check_decisions` | [src/engine/check_decisions.py](../../src/engine/check_decisions.py) | Push/决策 |
| `luck_resolver` | [src/engine/luck_resolver.py](../../src/engine/luck_resolver.py) | 幸运 |
| `round_snapshots` | [src/engine/round_snapshots.py](../../src/engine/round_snapshots.py) | 回合快照 |
| `round_recovery` | [src/engine/round_recovery.py](../../src/engine/round_recovery.py) | 回合恢复 |
| `visibility_rules` | [src/engine/visibility_rules.py](../../src/engine/visibility_rules.py) | 可见性 |
| `participant_view` | [src/engine/participant_view.py](../../src/engine/participant_view.py) | 参与者视图 |
| `game_context_projector` | [src/engine/game_context_projector.py](../../src/engine/game_context_projector.py) | LLM 上下文投影 |

### 1.4 规则与内容

| 符号 | 位置 | 说明 |
|---|---|---|
| `RuleSystem` | [src/rules/rule_system.py](../../src/rules/rule_system.py) | Legacy 规则 |
| `RuleBundleLoader` | [src/rules/loader.py](../../src/rules/loader.py) | 规则模板加载 |
| `RulesetRuntimeRegistry` | [src/rulesets/registry.py](../../src/rulesets/registry.py) | runtime 注册 |
| `RulesetRuntime` / `RulesetCapabilities` / `RulesetBinding` | [src/rulesets/contracts.py](../../src/rulesets/contracts.py) | 契约 |
| `build_default_ruleset_registry` | [src/rulesets/builtin.py](../../src/rulesets/builtin.py) | 默认注册 |
| `LegacyRulesetAdapter` | [src/rulesets/legacy_adapter.py](../../src/rulesets/legacy_adapter.py) | 旧规则适配 |
| `Dnd2024Runtime` | [src/rulesets/dnd2024/runtime.py](../../src/rulesets/dnd2024/runtime.py) | D&D 2024 |
| `apply_event_batch` | [src/rulesets/events.py](../../src/rulesets/events.py) | 事件批次 |
| `RulesetBundleLoader` | [src/rulesets/bundle.py](../../src/rulesets/bundle.py) | bundle |
| `AdventureResolver` | [src/adventures/resolver.py](../../src/adventures/resolver.py) | 冒险解析 |
| `AdventureBundleLoader` | [src/adventures/bundle.py](../../src/adventures/bundle.py) | 冒险包 |
| `AdventureSourceRegistry` | [src/adventures/registry.py](../../src/adventures/registry.py) | 冒险来源 |
| `LorebookStore` | [src/lorebook/store.py](../../src/lorebook/store.py) | 世界书存储 |
| `KeywordMatcher` | [src/lorebook/matcher.py](../../src/lorebook/matcher.py) | 关键词 |
| `LoreRetriever` | [src/lorebook/retrieval.py](../../src/lorebook/retrieval.py) | Hybrid 检索 |
| `LorebookSyncImporter/Exporter` | [src/lorebook/sync.py](../../src/lorebook/sync.py) | 同步 |
| `MemoryStore` | [src/memory/delta.py](../../src/memory/delta.py) | 记忆 |
| `EmbeddingClient` | [src/memory/embedding.py](../../src/memory/embedding.py) | 向量 |
| `ContentProjectionService` | [src/content_modules/projection.py](../../src/content_modules/projection.py) | 内容投影 |

### 1.5 LLM 与插件

| 符号 | 位置 | 说明 |
|---|---|---|
| `LLMClient` | [src/llm/client.py](../../src/llm/client.py) | 多供应商 |
| `ProviderConfig` / `LLMResponse` / `LLMToolResponse` | 同上 | 数据结构 |
| `build_context` | [src/llm/context_builder.py](../../src/llm/context_builder.py) | 上下文 |
| `parse_llm_response` | [src/llm/parser.py](../../src/llm/parser.py) | 解析 |
| `sanitize_narration` | 同上 | 叙事清理 |
| `protocol` | [src/llm/protocol.py](../../src/llm/protocol.py) | 标签协议 |
| `DICE_CHECKS_TOOL` | [src/llm/tools.py](../../src/llm/tools.py) | 检定工具 schema |
| `HostedCombatChooser` | [src/llm/combat_choice.py](../../src/llm/combat_choice.py) | 托管战斗选择 |
| `PluginHost` | [src/plugin_host/host.py](../../src/plugin_host/host.py) | 插件 |
| `PluginRuntime` | [src/plugin_host/models.py](../../src/plugin_host/models.py) | 运行时 |
| `PLUGIN_TYPE_SUPPORT` | [src/plugin_host/support.py](../../src/plugin_host/support.py) | 插件类型 |
| `JsonRpcStdioClient` | [src/plugin_host/runtime_protocol.py](../../src/plugin_host/runtime_protocol.py) | RPC |
| `ToolRuntime` / `ProviderRuntime` / `BridgeExtensionRuntime` | [src/plugin_sdk/](../../src/plugin_sdk/) | SDK |
| `DiceFrameBridgeService` | [src/bots/bridge_core/service.py](../../src/bots/bridge_core/service.py) | Bot |
| `DiceFrameClient` | [src/bots/bridge_core/client.py](../../src/bots/bridge_core/client.py) | Bot HTTP |
| `card_renderer` | [src/bots/bridge_core/card_renderer.py](../../src/bots/bridge_core/card_renderer.py) | 卡片 |
| `AgentRuntime` | [src/webui/services/assistant_agent.py](../../src/webui/services/assistant_agent.py) | DF Agent |

---

## 2. HTTP 路由分组

> 路由注册文件位于 [src/webui/routes/](../../src/webui/routes/)。下列为高频端点，完整列表以 `register_*` 为准。

### 2.1 认证与会话

```text
POST /api/login
GET  /api/login-history
GET  /api/me
GET  /api/config
POST /api/config
POST /api/config/bot-token
POST /api/config/providers/models
POST /api/test-connection
POST /api/test-embedding
POST /api/test-proxy
```

### 2.2 对局

```text
GET    /api/games
POST   /api/games/create
POST   /api/games/create-from-seed
POST   /api/games/import
POST   /api/games/batch-delete
GET    /api/games/{game_key}
GET    /api/games/{game_key}/log
GET    /api/games/{game_key}/characters
GET    /api/games/{game_key}/player-context
POST   /api/games/{game_key}/reset
POST   /api/games/{game_key}/restart
POST   /api/games/{game_key}/switch-world
POST   /api/games/{game_key}/room-password
POST   /api/games/{game_key}/player-access
```

### 2.3 行动 / 回合 / 规则玩法

```text
POST /api/games/{game_key}/action
POST /api/games/{game_key}/advance
POST /api/games/{game_key}/rollback
POST /api/games/{game_key}/gm-command
POST /api/games/{game_key}/swipe/{round}
PUT  /api/games/{game_key}/swipe/{round}
POST /api/games/{game_key}/intents
POST /api/games/{game_key}/combat/action
POST /api/games/{game_key}/combat/scheduler/advance
POST /api/games/{game_key}/checks/{check_id}/push/{operation}
GET  /api/games/{game_key}/check-modes
POST /api/games/{game_key}/check-modes/seats/{user_id}/{operation}
POST /api/games/{game_key}/checks/{check_id}/luck
POST /api/games/{game_key}/payments
POST /api/games/{game_key}/payments/{payment_id}
```

### 2.4 SSE 与实时

```text
POST /api/games/{game_key}/sse-ticket
GET  /api/games/{game_key}/sse
GET  /api/games/{game_key}/private-log
GET  /api/games/{game_key}/table-talk
```

### 2.5 玩家控制 / AI 席位

```text
GET  /api/games/{game_key}/multiplayer
POST /api/games/{game_key}/players
POST /api/games/{game_key}/players/{user_id}/control
POST /api/games/{game_key}/players/{user_id}/away
POST /api/games/{game_key}/settings/away-control-policy
POST /api/games/{game_key}/players/{uid}/seat-token
POST /api/games/{game_key}/seat-token/claim
GET  /api/games/{game_key}/ai-seats
PUT  /api/games/{game_key}/ai-seats/defaults
PUT  /api/games/{game_key}/ai-seats/seats/{user_id}
POST /api/games/{game_key}/ai-seats/seats/{user_id}/retry
```

> 实际路径以 [games.py](../../src/webui/routes/games.py) 与 `game_*_routes.py` 为准；部分路径包含 `{user_id}` 占位。

### 2.6 角色 / 世界书 / 内容

```text
GET/POST /api/character-cards
POST     /api/character-cards/import
POST     /api/character-cards/import/preview
POST     /api/character-cards/export
GET/POST /api/lorebooks
GET      /api/games/{game_key}/lorebooks
POST     /api/content/import/preview
POST     /api/content/import/commit
POST     /api/content/export
POST     /api/content/status
POST     /api/content/list
POST     /api/content-review/{preview|review|commit}
GET/POST /api/adventures
POST     /api/adventures/import
POST     /api/adventures/script/{preview|review|commit|ai}
GET/POST /api/worlds
GET/POST /api/rules
```

### 2.7 图像 / 语音 / 地图

```text
GET  /api/image-generation
POST /api/generated-images
GET  /api/generated-images/{asset_id}
POST /api/games/{game_key}/generated-images/current-round
GET  /api/games/{game_key}/generated-images/storyboard
POST /api/games/{game_key}/generated-images/storyboard/analyze
POST /api/games/{game_key}/transcription
POST /api/asr/test
GET  /api/avatars
POST /api/avatars
GET  /api/games/{game_key}/map
POST /api/map-backgrounds
POST /api/games/{game_key}/map-background
```

### 2.8 插件 / Bot / 系统

```text
GET  /api/plugins
POST /api/plugins/install
POST /api/plugins/{plugin_id}/{start|stop|restart}
GET  /api/plugins/marketplace
POST /api/plugins/marketplace/install
GET  /api/plugins/mirrors
POST /api/plugins/mirrors
GET  /api/bot/ping
POST /api/bot/bind-game
POST /api/games/{game_key}/bot-bind-token
GET  /api/system/network
GET  /api/system/update-check
GET  /api/system/runtime-logs
POST /api/system/runtime-logs/clear
GET  /api/system/update/status
POST /api/system/update/apply
POST /api/system/restart
GET  /api/announcements
GET  /api/legal/{document}
```

> 插件与系统端点会随版本扩展；以 [plugins.py](../../src/webui/routes/plugins.py)、[system.py](../../src/webui/routes/system.py)、[updater.py](../../src/webui/routes/updater.py) 为准。

---

## 3. Module Hooks 与状态 Kind

### 3.1 钩子点

```text
round.reset
round.processing.begin
instance.reset.preflight
instance.reset.begin
instance.reset
instance.new_run.preflight
instance.new_run
round.recovery.preflight
round.abort
round.rewind.begin
round.rewind.restore
round.commit
npc.admission
authority.write.allowed
checks.skill_use.settled
seat.preflight
seat.acted
seat.forgotten
seat.has_acted
module.state.record
module.state.read
module.state.write.preflight
combat_view
```

### 3.2 状态 Kind

```text
overreach
world_legality
world_events
quick_actions
gm_directives
combat_results
state_update
token_budget_bump
lorebook_timers
health_events
health_status
check_reveals
away_control_policy
private_log
table_talk
combat_view
scene_image
map_background
combat_extension
combat_extension_snapshot
```

### 3.3 内核模块

```text
adventure_runtime_state
checks
content_binding
progression_state
round_safety
ruleset_runtime
session_stats
```

另有 `room_access`、`economy_state`、`game_config` 属于建局内核；`resource_recovery` 是 authority 例外。

---

## 4. 引擎模块目录

`src/engine/modules/`：

| 模块 | 作用 |
|---|---|
| `adventure_runtime_state` | 冒险进度与 play_mode |
| `ai_seats` | AI 席位设置 |
| `checks` | 本轮检定 / 手动骰请求 |
| `check_modes` | 检定模式 |
| `check_policy` | Push 开关 |
| `check_presentation` | 检定展示 |
| `check_reveals` | 检定揭示 |
| `combat_extension_state` | 通用战斗扩展载荷与快照 |
| `content_binding` | 内容绑定 |
| `economy_state` | 经济账本 |
| `game_config` | 本局内核配置 |
| `health` | 健康事件 |
| `legacy_combat` | 只读战斗视图 |
| `lorebook_runtime` | 世界书计时器 |
| `media` | 场景图/地图背景引用 |
| `narration_preferences` | 叙事偏好 |
| `narrative_notes` | scene（v2） |
| `player_control_state` | 暂离策略 |
| `private_channels` | 私聊与桌边交流 |
| `profile_progression` / `profile_run` | 剧本档案 |
| `progression_state` | 回合/进度 |
| `resource_recovery` | 一次性恢复权威 |
| `room_access` | GM/玩家访问/房间凭据 |
| `round_presentation` | 快捷行动/GM 指令等展示 |
| `round_safety` | 回合快照/死亡豁免 |
| `ruleset_runtime` | binding/state/event_ledger |
| `run_finale` | 结团 |
| `run_story` | 跑团计划 |
| `seat_activity` | 席位行动锁 |
| `session_stats` | 调用/token/时间统计 |
| `skill_growth` | 技能成长 |
| `storytelling` | 叙事呈现设置 |
| `world_reports` | 越权/世界报告 |

---

## 5. 前端关键符号

| 符号 | 位置 | 说明 |
|---|---|---|
| `createApp` 启动 | [main.ts](../../frontend-v2/src/main.ts) | 挂载、视口、运行时恢复 |
| `router` | [router/index.ts](../../frontend-v2/src/router/index.ts) | 路由 |
| `requireOwnerAccess` | 同上 | owner 守卫 |
| `api<T>` | [api/client.ts](../../frontend-v2/src/api/client.ts) | 请求 |
| `ApiError` | 同上 | 错误 |
| `gameEventSource` | 同上 | SSE |
| `useGame` | [composables/useGame.ts](../../frontend-v2/src/composables/useGame.ts) | 对局状态 |
| `useAssistant` | [composables/useAssistant.ts](../../frontend-v2/src/composables/useAssistant.ts) | DF Agent |
| `ActionComposer` | [components/ActionComposer.vue](../../frontend-v2/src/components/ActionComposer.vue) | 行动输入 |
| `GameTimeline` | [components/GameTimeline.vue](../../frontend-v2/src/components/GameTimeline.vue) | 时间线 |
| `PlayView` | [features/play/PlayView.vue](../../frontend-v2/src/features/play/PlayView.vue) | 游玩主页 |
| `CreateView` | [features/create/CreateView.vue](../../frontend-v2/src/features/create/CreateView.vue) | 创建 |
| `appNavigation` | [navigation/appNavigation.ts](../../frontend-v2/src/navigation/appNavigation.ts) | 导航 |

---

## 6. 常见错误类型

| 错误 | 位置 | 含义 |
|---|---|---|
| `RoundNotProcessed` | [round_processor.py](../../src/commands/round_processor.py) | 本轮未处理 |
| `RoundProcessingFailure` | 同上 | 处理失败（可能已回滚） |
| `CheckModelNotConfigured` | 同上 | 独立检定模型未配置 |
| `RoundProcessingError` | [turns.py](../../src/webui/services/turns.py) | 回合推进错误 |
| `RulesetRuntimeError` 家族 | [rulesets/registry.py](../../src/rulesets/registry.py) | 注册/绑定/版本错误 |
| `RulesetBundleError` | [rulesets/bundle.py](../../src/rulesets/bundle.py) | bundle 校验失败 |
| `ModuleStateError` | [engine/module_state.py](../../src/engine/module_state.py) | 模块槽非法 |
| `WorldStateError` | [engine/world_state.py](../../src/engine/world_state.py) | 世界状态非法 |
| `LorebookIdentityConflict` | [lorebook/store.py](../../src/lorebook/store.py) | 世界书身份冲突 |
| `CatalogLoadError` | [dnd2024/content/catalog.py](../../src/rulesets/dnd2024/content/catalog.py) | 内容目录加载失败 |
| `AgentExecutionStopped` | [assistant_agent.py](../../src/webui/services/assistant_agent.py) | Agent 执行中止 |
| `ApiError`（前端） | [api/client.ts](../../frontend-v2/src/api/client.ts) | HTTP 错误 |

---

## 7. 常用命令速查

```bash
# 后端
python web_server.py
python -m pytest -q
python -m pytest -q tests/architecture/
python -m ruff check src/
python -m mypy

# 前端
cd frontend-v2
npm run dev
npm run build
npm run typecheck
npm run lint
npm test
npm run test:e2e:smoke

# 内容与插件
python scripts/validate_content_module.py path/to/plugin --json
python scripts/package_plugin.py path/to/plugin

# 审计
python scripts/audit_architecture.py
python scripts/audit_module_pluggability.py
```

---

## 8. 术语补充

| 术语 | 说明 |
|---|---|
| `binding` | 对局对规则/冒险/内容的不可变引用 |
| `slot` | 持久化中按域拆分的状态槽，如 `modules.checks` |
| `projection` | 给 UI/LLM 的只读派生数据 |
| `intent` | 规则感知的结构化行动 |
| `EventBatch` | 规则运行时的一次权威事件集合 |
| `reducer` | 把事件写入 canonical state 的函数 |
| `capability` | 规则集/插件显式声明的能力 |
| `outbox` | 跨存储副作用待投递记录 |
| `effect group` | 需要原子完成或补偿的外部效果组 |
| `seat` | 一个玩家席位，带控制模式与凭据 |
| `lore` | 世界书条目及其检索结果 |
| `canonical ID` | 稳定身份，不随显示名/locale 改变 |
