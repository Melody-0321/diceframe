# 08 持久化与数据

> 核心文件：[persistence.py](../../src/engine/persistence.py) · [game_state_codec.py](../../src/engine/game_state_codec.py) · [migrations/instance.py](../../src/migrations/instance.py) · [lorebook/store.py](../../src/lorebook/store.py) · [memory/delta.py](../../src/memory/delta.py)

## 1. 数据目录

默认由 `TRPG_DATA_DIR` 决定，未设置时为仓库下 `data/`。路径解析见 [runtime_config.py](../../src/webui/runtime_config.py) 的 `RuntimePaths.from_root(...)`。

```text
data/
├─ config.json               # 运行时配置（AI provider 目录、路由、Web、默认值）
├─ secrets.json              # API key、口令哈希等敏感信息
├─ access_token.txt          # owner 登录 token（自动生成或环境变量）
├─ saves/                    # 对局存档
│  └─ <platform>#<target>#<account>/
│     ├─ state.json          # 核心持久态（GamePersistedState）
│     ├─ state.backup.json   # 上一次写入
│     └─ chatlog.jsonl       # 完整逐轮日志（增量追加）
├─ lorebook.db               # 世界书 SQLite（schema 12）
├─ memory.db                 # 长期记忆 SQLite
├─ templates/                # rules / worlds / adventures 同步副本
├─ generated-images/         # 生成图片资产
├─ tts-cache/                # TTS 缓存
├─ content-cache/            # 公共内容缓存
├─ plugins/                  # 已安装插件
└─ plugin-packages/          # 插件包缓存
```

> `game_key` 的每一段在拼路径前会做安全检查；包含空串、`/`、`\`、`.`、`..` 会直接拒绝。

---

## 2. 运行时配置

### 2.1 `config.json`

主要分组：

| 分组 | 示例键 |
|---|---|
| Web | `web_host`、`web_port`、`web_http_port`、`web_https_port`、`web_hosts` |
| 访问 | `access_password`、CORS、Hub 偏好 |
| AI Provider | `ai_providers`（共享服务商目录） |
| 模型路由 | `llm_provider_ref`、`model`、`fallbackN_*`、`check_*`、`embedding_*`、`tts_*`、`asr_*`、`imagegen_*` |
| 生成参数 | `narrative_max_tokens`、`character_gen_max_tokens`、`summary_max_tokens`、`brief_max_tokens`、`analysis_max_tokens`、`model_request_timeout_seconds`、`context_recent_rounds` |
| 游戏默认 | `game_defaults`（由 `src/game_preferences.py` 校验） |
| 代理 | `proxy_enabled`、`proxy_url` |

### 2.2 `secrets.json`

- `ai_provider_key_<id>`：共享服务商密钥；
- 访问口令哈希；
- 其他不应出现在公开配置中的凭据。

### 2.3 配置写入

`ConfigStore`：

- 读取失败时隔离损坏文件为 `*.corrupt-<timestamp>.json`；
- 原子写（临时文件 + replace）；
- 公开视图 `public_view(...)` 不泄露密钥；
- `/api/config` 是登录前唯一可匿名探测的端点，只返回公开字段与版本信息。

> AI 配置只支持新格式：`ai_providers` + `*_provider_ref`。旧字段更新返回 HTTP 400 `unsupported AI config fields`，不自动迁移。

---

## 3. 存档编解码

### 3.1 分层

```text
GameInstance
  → GameStateCodec.encode(instance)   # 稳定持久化投影
  → GamePersistedState (TypedDict)
  → JSON state.json

state.json
  → normalize_game_state_payload(...) # 迁移与归一
  → GameStateCodec.decode(...)
  → GameInstance
```

- [game_state_contracts.py](../../src/engine/game_state_contracts.py)：`GamePersistedState` 顶层契约；
- [game_state_codec.py](../../src/engine/game_state_codec.py)：encode / decode；
- [migrations/instance.py](../../src/migrations/instance.py)：schema 迁移与归一。

### 3.2 持久化的主要状态

| 类别 | 示例 |
|---|---|
| identity | `instance_schema_version`、`run_id`、`memory_namespace`、`game_key` |
| binding | `world_id`、`rule_id`、`adventure_binding`、`modules.ruleset_runtime.binding` |
| lifecycle | `state`、`round_number`（模块） |
| participants | `players`、`npcs`、`ready_players`、`away_players` |
| actions | `action_queue`、`pending_actions` |
| world | `world_state`（facts / clock / scheduled_events / revision） |
| ruleset | `modules.ruleset_runtime.state`、`event_ledger` |
| narrative | `log`（最多保留最近 100 条进 state）、`modules.narrative_notes.scene`、`summary`、`key_facts` |
| presentation | `language`、difficulty、GM style、偏好模块 |
| economy | proposals / transactions / effects / outbox |
| checks | `modules.checks`、manual roll requests |
| rollback safety | `modules.round_safety` 快照 |
| access | `modules.room_access`（GM、玩家访问、Bot 绑定、房间凭据） |
| media | `modules.media` 的 `scene_image` / `map_background` |
| health | `modules.health` |
| private channels | `modules.private_channels` |

不序列化：asyncio 锁、活动 task、计时器句柄、瞬时 in-flight 上下文。

### 3.3 存档写入

[persistence.save(...)](../../src/engine/persistence.py)：

```text
state.tmp.json 写入
  → 旧 state.json 改为 state.backup.json
  → tmp 替换为 state.json
```

聊天日志：

- `chatlog.jsonl` 按行追加，O(1)；
- `state.json` 只保留最近历史，避免大文件；
- rollback 导致 log 缩短时截断 chatlog；
- swipe 不改变长度，读取时用 core log 对齐修正；
- `run_id` 变化时重写整个 chatlog。

`GameRegistry.save(...)` 会拒绝“旧实例对象覆盖新 run”的 stale 写入。

---

## 4. Schema 迁移

### 4.1 当前版本

| 数据 | 当前版本 | 位置 |
|---|---|---|
| GameInstance persisted | **47** | [migrations/instance.py](../../src/migrations/instance.py#L31) |
| Lorebook SQLite | **12** | [migrations/lorebook.py](../../src/migrations/lorebook.py) |
| Memory SQLite | 见 `src/migrations/memory.py` |  |
| WorldState | 2 | [world/read.py](../../src/engine/world/read.py) |
| Currency | 2 | [currency/models.py](../../src/engine/currency/models.py) |

> 架构文档 §11.3 中的 `CURRENT_INSTANCE_SCHEMA_VERSION = 15` 是历史段落；以源码中的 `47` 为准。

### 4.2 迁移原则

1. **顺序执行**：`vN → vN+1 → ...`，不猜最新形状；
2. **先 deepcopy**：不修改调用方原对象；
3. **拒绝未来版本**：`version > CURRENT_INSTANCE_SCHEMA_VERSION` 直接失败；
4. **不猜语义**：金额、身份、权限、旧字段含义无法证明时不自动换算；
5. **fail closed**：无法证明安全时拒绝加载/导入，而不是写坏数据；
6. **保留不透明扩展字段**：未知但合法的扩展数据原样保留；
7. **兼容留在边界**：旧格式适配放在 `src/compat/` 与迁移层，不散回业务。

### 4.3 近期关键迁移

| 变化 | 说明 |
|---|---|
| 顶层字段 → `modules.*` | scene、adventure progress、ruleset runtime、checks、round safety、session stats 等逐步迁入模块槽 |
| legacy combat 退役 | 删除整个 `modules.legacy_combat` 槽，战斗视图改为规则投影 |
| current run 配置拆分 | `game_config` 成为内核配置槽 |
| resource recovery | 46→47 增加 reader fence，拒绝待处理资格跨 run 转移 |
| World identity | 旧 world/book ID 通过稳定哈希映射为 ASCII canonical ID，并重绑引用 |

迁移实现集中在：

- [migrations/instance.py](../../src/migrations/instance.py)：对局；
- [migrations/lorebook.py](../../src/migrations/lorebook.py)：世界书；
- [migrations/lorebook_content.py](../../src/migrations/lorebook_content.py)：内容结构；
- [migrations/memory.py](../../src/migrations/memory.py)：记忆；
- [migrations/world_identity.py](../../src/migrations/world_identity.py) / `world_identity_payload.py`：世界身份；
- [migrations/sqlite.py](../../src/migrations/sqlite.py)：SQLite 辅助。

### 4.4 World Identity 自动升级

`migrate_legacy_world_ids(...)` 在冷启动构建最前执行（`create_trpg_subsystems` 的 `reuse is None` 路径）：

- 支持旧资料册 SQLite v4 与 canonical v5～v12；
- 每个旧 identity 通过稳定哈希映射为 ASCII canonical world ID；
- 同名世界仍保持区分；
- 重绑 `templates`、`saves/state*.json` 与已知 JSON payload 中的 world/book 引用；
- 保留展示标题、entry ID、`game_key`、`memory_namespace` 与聊天文本；
- 使用 SQLite receipt 与持久 journal 支持中断后 roll-forward；
- 用户改动、目标冲突、非法或未来 schema 时 fail closed，不覆盖原数据。

---

## 5. SQLite 数据库

### 5.1 世界书（`lorebook.db`）

- WAL 模式；
- peewee 只用于查询构造，建表与迁移由 `LorebookStore.SCHEMA` / `src/migrations/lorebook.py` 负责；
- 外键级联由 schema 与 `PRAGMA foreign_keys=ON` 承担，模型层不声明关系，避免第二条删除路径。

表：`worlds`、`lorebooks`、`lorebook_bindings`、`lorebook_entries`、`lorebook_embeddings`。

### 5.2 记忆（`memory.db`）

- WAL 模式；
- `memory_entries`：实体、关系、值、置信度、状态、来源、可见性、embedding；
- `memory_economy_deliveries`：经济记忆投递的前后状态与反向状态。

### 5.3 并发

- `LorebookStore` 通过内部锁 + `transaction()` 保证写一致；
- `MemoryStore` 使用锁保护 delta 应用与 embedding 写入；
- 存档写有 per-game `_save_locks`。

---

## 6. 生命周期语义

### 6.1 reset（原地重置）

```text
preflight：
  progression / session_stats / checks / round_safety / ruleset_runtime
  module_hooks.preflight(NARRATIVE_VIEW)
  adventure_runtime_state / room_access
→ instance_lifecycle.reset_locked(keep_seed)
→ 轮换 run_id、清空运行时状态
→ 清理席位凭据
```

保留：

- 游戏配置与偏好；
- ruleset binding；
- play_mode；
- 死亡豁免缓存（按设计）；
- 手动骰请求。

清空：进度、场景、回合、日志、行动队列、本轮快照。

### 6.2 restart / 新 run

```text
source preflight
→ 构造 candidate
→ 初始化 candidate
→ registry.replace_current(expected, candidate)
```

旧对象仍可能被等待锁的 writer 持有，但写入会因 `run_id` / 对象身份不匹配被拒绝。

### 6.3 rollback / swipe

| 操作 | 语义 |
|---|---|
| `rollback_last_round` | 回滚已提交的上一轮，截断日志，反向经济/记忆 |
| `abort_round_processing` | 中止本轮判定，恢复到判定入口快照，仍在本轮 |
| `switch_swipe` / `finish_judgment_with_swipe` | 历史分支切换，保留旧分支数据供切换 |

回滚顺序要点：

```text
authority lock
→ 校验目标轮与 run
→ 恢复目标快照
→ 截断被丢弃分支
→ 反向经济/记忆 outbox
→ 发布新状态
```

### 6.4 导入存档

导入不是继续使用原 run identity：

```text
解析 zip
→ 校验状态 shape / schema
→ 重新生成 game_key / run identity（按导入入口）
→ 重绑 world / rule / adventure 引用
→ 恢复媒体引用
→ registry 注册
```

无法证明安全的待处理状态（如跨 run 的恢复资格）会被拒绝。

---

## 7. 跨存储一致性

### 7.1 Memory Outbox

```text
回合权威提交
  → memory delta 写入 GameInstance outbox
  → 后台投递 MemoryStore
  → 标记 delivered
```

失败可重试；回滚时生成 reversal 投递。这样避免“游戏已回滚但记忆已写入”的不一致。

### 7.2 经济 Effect Group

外部副作用（例如生成图片、修改资产）通过 effect group 记录：

- 先记录待执行；
- 执行后标记完成；
- 回滚时撤销或补偿；
- 不允许“权威状态已撤回但外部效果仍生效”。

### 7.3 Staged Transaction

[staged_transaction.py](../../src/engine/staged_transaction.py)：

```text
fork_domain_state(instance)          # 复制域状态，不带锁/计时器
→ 在 staged 上规划
→ matches(instance) 乐观校验
→ publish 或 rollback
```

适用于经济决策、规则事务等需要“全有或全无”的场景。

---

## 8. 数据修复与诊断

| 场景 | 处理 |
|---|---|
| `config.json` 损坏 | 隔离为 `*.corrupt-<ts>.json`，以空配置继续 |
| 存档损坏 | `state.backup.json` 回退；仍失败则记录健康事件 |
| 启动恢复 | `registry.recover_all()` 加载未结束对局 |
| 经济 outbox 未完成 | `recover_economy_outboxes(...)` |
| 记忆 embedding 缺失 | 后台 `embed_pending_memories(...)` |
| 世界 identity 冲突 | fail closed，保留原数据并报告 |
| 插件包损坏 | 安装前校验失败，不覆盖现有版本 |

健康事件通过 `modules.health` 记录，GM 可在健康面板查看。

---

## 9. 修改持久化的检查清单

- [ ] 新字段是否有明确 owner（GameInstance 还是模块）？
- [ ] 是否加入 `GamePersistedState` 与 codec？
- [ ] 是否需要新 schema 版本与顺序迁移？
- [ ] 迁移是否 deepcopy、拒绝未来版本、不猜语义？
- [ ] reset / restart / rollback / swipe 的语义是否明确？
- [ ] 是否需要 outbox / staged transaction？
- [ ] 是否覆盖旧存档、损坏存档、未来版本、导入冲突测试？
- [ ] 是否更新 [08 本章] 与架构文档？
