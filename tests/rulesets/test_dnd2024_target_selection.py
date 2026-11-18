"""S0-F39: one target-selection entry point for capabilities.

Before this slice, "who may I pick" was answered four different ways: the
projection looked at ``requires_hostile_target``, each validator re-checked
side/hp/range inline, the frontend guessed which list to offer, and the commit
shape differed per ability (``target_id`` here, ``target_ids`` there,
``allocations`` elsewhere).  Four answers to one question drift, and the drift
is what made Bardic Inspiration and Abjure Foes unreachable from the UI while
the server "supported" them.

These tests therefore drive the two halves that must agree: the projection
(``available_intents``) and the commit (``resolve_intent``).  A test that only
checks one half cannot see the bug this slice exists to fix.

The count rule under test is a *product* decision (S0-F39 §1.5), not the
rulebook's letter: the ceiling is an upper bound, and the player may always
pick fewer -- never zero.  See ``resolve_target_cap``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from src.rulesets.dnd2024.features import Dnd2024ClassFeatureResolver
from src.rulesets.dnd2024.features.models import ClassFeatureError
from src.rulesets.dnd2024.runtime import Dnd2024Runtime

from dnd2024_monk_common import SequenceRng
from test_dnd2024_channel_control import (  # noqa: F401 - fixtures/helpers reused
    _add_ally,
    _apply,
    _attack,
    _build,
    _capability,
    _cleric_sheet,
    _combat,
    _enemy,
    _hp,
    _inject,
    _intent,
    _of_type,
    _paladin_sheet,
    _pool,
    _positions,
    _setup,
    _start,
    _to_turn,
    _two_enemies,
)

LOCALE = "en"
BARD_ABILITIES = {"str": 8, "dex": 14, "con": 13, "int": 10, "wis": 12, "cha": 15}
# 侍僧背景给 insight/religion、物种给 animal_handling，职业选择不能与它们重复。
BARD_SKILLS = ["skill:arcana", "skill:deception", "skill:performance"]


@pytest.fixture(scope="module")
def bundle():
    return Dnd2024Runtime().load_bundle(LOCALE)


@pytest.fixture(scope="module")
def sheets(bundle) -> dict[str, dict]:
    return {
        "paladin9": _paladin_sheet(bundle, 9),
        "cleric5": _cleric_sheet(bundle, 5),
        "cleric9": _cleric_sheet(bundle, 9),
        "bard1": _build(
            Dnd2024Runtime(), bundle, "class:bard", 1,
            BARD_ABILITIES, BARD_SKILLS, "equipment_package:bard_a",
        ),
    }


def _three_enemies() -> list[dict]:
    return [
        _enemy(position=5, enemy_id="goblin-1"),
        _enemy(position=10, enemy_id="goblin-2"),
        _enemy(position=15, enemy_id="goblin-3"),
    ]


def _capability_entry(engine, instance, capability_id: str, viewer_uid: str = "gm") -> dict:
    """The projection row one capability produces for the current actor.

    ``available_intents`` takes the *viewer's* user id, not the actor id: the
    rows it returns already carry ``actor_id``.
    """

    for action in engine.available_intents(instance, viewer_uid):
        if action.get("type") == "class_capability" and \
                action.get("capability_id") == capability_id:
            return action
    raise AssertionError(f"{capability_id} is not projected for viewer {viewer_uid}")


# ---------------------------------------------------------------------------
# 1-5. up_to: the ceiling is an upper bound, and the floor is one
# ---------------------------------------------------------------------------


def test_up_to_accepts_the_full_ceiling(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_three_enemies())
    events = _apply(engine, instance, _capability(
        engine, instance, "abjure_foes", [3, 3, 3],
        target_ids=["enemy:goblin-1", "enemy:goblin-2"],
    ))
    assert len(_of_type(events, "check.resolved")) == 2


def test_up_to_accepts_fewer_targets_and_emits_one_event_each(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_three_enemies())
    events = _apply(engine, instance, _capability(
        engine, instance, "abjure_foes", [3, 3, 3],
        target_ids=["enemy:goblin-2"],
    ))
    # 少选不补偿：只结算选中的那一个，引导次数只扣一次。
    resolved_checks = _of_type(events, "check.resolved")
    assert len(resolved_checks) == 1
    assert [row["amount"] for row in _of_type(events, "dnd2024.class_resource.spent")] == [1]


def test_zero_targets_and_over_the_ceiling_are_refused_without_state_change(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_three_enemies())
    before_version = int(_combat(instance)["economy"].get("version", 0) or 0)
    before_pool = int(_pool(instance)["current"])

    for targets in ([], ["enemy:goblin-1", "enemy:goblin-2", "enemy:goblin-3"]):
        resolved = _capability(
            engine, instance, "abjure_foes", [3, 3, 3], target_ids=targets,
        )
        assert resolved["ok"] is False, targets
    # 拒绝必须是整条的：版本与资源都不动。
    assert int(_pool(instance)["current"]) == before_pool
    assert int(_combat(instance)["economy"].get("version", 0) or 0) == before_version


def test_a_target_resolves_the_same_alone_or_alongside_another(sheets) -> None:
    """少选不改变"单个目标会怎样"：只是少结算几个，不是换个算法。"""

    alone_engine, alone = _setup(sheets["paladin9"])
    _start(alone_engine, alone, enemies=_two_enemies())
    alone_events = _apply(alone_engine, alone, _capability(
        alone_engine, alone, "abjure_foes", [3, 3], target_ids=["enemy:goblin-1"],
    ))

    pair_engine, pair = _setup(sheets["paladin9"])
    _start(pair_engine, pair, enemies=_two_enemies())
    pair_events = _apply(pair_engine, pair, _capability(
        pair_engine, pair, "abjure_foes", [3, 3],
        target_ids=["enemy:goblin-1", "enemy:goblin-2"],
    ))

    def goblin_one(events: list[dict]) -> list[tuple]:
        return [
            (row.get("target_id"), row.get("total"), row.get("success"))
            for row in _of_type(events, "check.resolved")
            if row.get("target_id") == "enemy:goblin-1"
        ]

    assert goblin_one(alone_events) == goblin_one(pair_events)


def test_a_ceiling_above_one_still_accepts_a_single_target(sheets) -> None:
    """本切片的回归点：上界不止 1 时，选 1 个必须合法（§6.5）。

    标准数组 + 侍僧背景给到魅力 15（+2），所以这个圣武士的上界是 2 而不是
    任务书举例的 3；被验证的命题不变 —— 少选是允许的，只要至少一个。
    """

    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_three_enemies())
    _to_turn(engine, instance, "player:gm")
    entry = _capability_entry(engine, instance, "abjure_foes")
    assert entry["target_mode"] == "up_to"
    assert entry["target_cap"] == 2
    assert len(entry["candidates"]) >= 3

    resolved = _capability(
        engine, instance, "abjure_foes", [3, 3, 3], target_ids=["enemy:goblin-3"],
    )
    assert resolved["ok"] is True, resolved


# ---------------------------------------------------------------------------
# 6-7. single never takes two; all_in_range refuses a hand-picked subset
# ---------------------------------------------------------------------------


def test_single_refuses_two_targets(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _add_ally(instance, sheets["paladin9"])
    resolved = _capability(
        engine, instance, "lay_on_hands", [],
        target_ids=["player:gm", "player:ally"],
    )
    assert resolved["ok"] is False
    assert "exactly one" in resolved["error"]


def test_all_in_range_refuses_a_subset_of_the_candidates(sheets) -> None:
    engine, instance = _setup(sheets["cleric5"])
    undead = [
        _enemy(creature_type="undead", position=5, enemy_id="skeleton-1"),
        _enemy(creature_type="undead", position=10, enemy_id="skeleton-2"),
        # 活人不属于 Turn Undead 的候选：target_kind 也是"能不能选"的一部分，
        # 漏掉它，前端就会把队友列进"射程内全部"。
        _enemy(creature_type="humanoid", position=15, enemy_id="brigand-1"),
    ]
    _start(engine, instance, enemies=undead)
    entry = _capability_entry(engine, instance, "turn_undead")
    assert entry["target_mode"] == "all_in_range"
    assert entry["target_cap"] == 2
    assert [row["actor_id"] for row in entry["candidates"] if row["legal"]] == [
        "enemy:skeleton-1", "enemy:skeleton-2",
    ]
    reasons = {row["actor_id"]: row["reason"] for row in entry["candidates"]}
    assert reasons["enemy:brigand-1"] == "wrong_kind"

    subset = _capability(
        engine, instance, "turn_undead", [3, 3], target_ids=["enemy:skeleton-1"],
    )
    assert subset["ok"] is False
    assert "whole set" in subset["error"]

    whole = _capability(
        engine, instance, "turn_undead", [3, 3],
        target_ids=["enemy:skeleton-1", "enemy:skeleton-2"],
    )
    assert whole["ok"] is True, whole


# ---------------------------------------------------------------------------
# 8-9. the projection states legality and its reasons
# ---------------------------------------------------------------------------


def test_empty_candidate_set_marks_the_capability_unavailable(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _positions(instance, **{"enemy:goblin-1": 200, "enemy:goblin-2": 205})
    entry = _capability_entry(engine, instance, "abjure_foes")
    assert entry["available"] is False
    assert entry["blocked_reason"]
    assert entry["targets"] == []
    assert all(row["legal"] is False for row in entry["candidates"])


def test_every_illegal_candidate_carries_its_own_reason(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _positions(instance, **{"enemy:goblin-2": 200})
    entry = _capability_entry(engine, instance, "abjure_foes")
    reasons = {row["actor_id"]: row["reason"] for row in entry["candidates"]}
    assert "enemy:goblin-2" not in reasons or reasons["enemy:goblin-2"] == "out_of_range"
    assert all(
        row["reason"] for row in entry["candidates"] if not row["legal"]
    )
    # 自己从来不是候选：这条以前只写在每个校验函数里，前端看不到。
    assert "player:gm" not in reasons


def test_a_dead_creature_is_not_a_legal_target(sheets) -> None:
    """死亡状态由 condition 表达，不是 hp<=0：候选集必须读前者。"""

    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _inject(engine, instance, [{
        "type": "condition.applied", "target_id": "enemy:goblin-1",
        "condition": "dead", "source": "test",
    }])
    entry = _capability_entry(engine, instance, "abjure_foes")
    rows = {row["actor_id"]: row for row in entry["candidates"]}
    assert rows["enemy:goblin-1"]["legal"] is False
    assert rows["enemy:goblin-1"]["reason"] == "dead"


# ---------------------------------------------------------------------------
# 10-11. commit shape: one array, no duplicates, allocations must agree
# ---------------------------------------------------------------------------


def test_duplicate_targets_are_refused(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    resolved = _capability(
        engine, instance, "abjure_foes", [3, 3],
        target_ids=["enemy:goblin-1", "enemy:goblin-1"],
    )
    assert resolved["ok"] is False
    assert "must not repeat" in resolved["error"]


def test_budget_split_allocations_must_match_the_target_array(sheets) -> None:
    engine, instance = _setup(sheets["cleric9"])
    _add_ally(instance, sheets["cleric9"], uid="ally")
    _start(engine, instance, enemies=[_enemy()])
    _to_turn(engine, instance, "player:gm")
    # 两个候选都必须 bloodied，否则先撞上的是"只治 bloodied"而不是本用例要
    # 验证的一致性检查。
    _set_hp(instance, "player:gm", 5)
    _set_hp(instance, "player:ally", 5)

    mismatched = _capability(
        engine, instance, "preserve_life", [],
        target_ids=["player:ally"],
        allocations=[{"target_id": "player:gm", "amount": 3}],
    )
    assert mismatched["ok"] is False
    assert "same creatures" in mismatched["error"]

    matched = _capability(
        engine, instance, "preserve_life", [],
        target_ids=["player:ally"],
        allocations=[{"target_id": "player:ally", "amount": 3}],
    )
    assert matched["ok"] is True, matched


# ---------------------------------------------------------------------------
# 12. declarations fail closed at load time
# ---------------------------------------------------------------------------


def _mutated_resolver(mutate) -> Dnd2024ClassFeatureResolver:
    runtime = Dnd2024Runtime()
    bundle = runtime.load_bundle(LOCALE)
    entities = deepcopy(bundle.entities)
    features = entities["class_feature_catalog"]["srd_class_features"]["classes"]
    mutate(features)
    return Dnd2024ClassFeatureResolver(replace(bundle, entities=entities))


def _find_capability(features: dict, feature_id: str, capability_id: str) -> dict:
    for class_features in features.values():
        for feature in class_features["features"]:
            if feature["id"] != feature_id:
                continue
            for capability in feature["capabilities"]:
                if capability["id"] == capability_id:
                    return capability
    raise AssertionError(f"{capability_id} not found")


def _drop_target_mode(features: dict) -> None:
    _find_capability(features, "abjure_foes", "abjure_foes").pop("target_mode")


def _unknown_target_mode(features: dict) -> None:
    _find_capability(features, "abjure_foes", "abjure_foes")["target_mode"] = "exactly"


def _negative_target_cap(features: dict) -> None:
    capability = _find_capability(features, "abjure_foes", "abjure_foes")
    capability["target_count_ability"] = None
    capability["target_cap"] = -1


def _budget_split_on_self(features: dict) -> None:
    capability = _find_capability(features, "preserve_life", "preserve_life")
    capability["target_mode"] = "self"
    capability["budget_split"] = True


@pytest.mark.parametrize(
    "mutate",
    [_drop_target_mode, _unknown_target_mode, _negative_target_cap, _budget_split_on_self],
)
def test_broken_target_declarations_fail_closed_at_load(mutate) -> None:
    with pytest.raises(ClassFeatureError):
        _mutated_resolver(mutate)


# ---------------------------------------------------------------------------
# 13-15. the two halves agree
# ---------------------------------------------------------------------------


def test_bardic_inspiration_is_reachable_from_the_projection(sheets) -> None:
    """诗人激励以前在界面上点不出来：声明缺目标类型，投影说"不用选目标"。

    补齐声明后它必须同时满足三件事：投影说要选、上界是 1、候选集里有盟友。
    """

    engine, instance = _setup(sheets["bard1"])
    _add_ally(instance, sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _to_turn(engine, instance, "player:gm")
    entry = _capability_entry(engine, instance, "bardic_inspiration")
    assert entry["requires_target"] is True
    assert entry["target_mode"] == "single"
    assert entry["target_cap"] == 1
    legal = [row["actor_id"] for row in entry["candidates"] if row["legal"]]
    assert legal == ["player:ally"]

    resolved = _capability(
        engine, instance, "bardic_inspiration", [], target_ids=["player:ally"],
    )
    assert resolved["ok"] is True, resolved


def test_the_projection_is_a_pure_read(sheets) -> None:
    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    before_version = int(_combat(instance)["economy"].get("version", 0) or 0)
    first = engine.available_intents(instance, "player:gm")
    second = engine.available_intents(instance, "player:gm")
    assert first == second
    assert int(_combat(instance)["economy"].get("version", 0) or 0) == before_version


def test_a_single_target_capability_accepts_an_array(sheets) -> None:
    """新前端只发数组，单目标能力也一样（§4.4.1）。"""

    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _set_hp(instance, "player:gm", 5)

    array_resolved = _capability(
        engine, instance, "lay_on_hands", [], target_ids=["player:gm"],
        healing_amount=3,
    )
    assert array_resolved["ok"] is True, array_resolved


def _set_hp(instance, actor_id: str, value: int) -> None:
    _kind, uid = actor_id.split(":", 1)
    sheet = deepcopy(instance.get_character_sheet(uid))
    sheet["ruleset_character"]["resources"]["hp"] = value
    instance.players[uid]["character_sheet"] = sheet


def test_legacy_scalar_target_still_resolves(sheets) -> None:
    """旧意图（以及旧存档重放）仍发标量 target_id：保留一个版本的兼容读取。"""

    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _set_hp(instance, "player:gm", 5)
    resolved = engine.resolve_intent(instance, _intent(
        instance, type="class_capability", capability_id="lay_on_hands",
        target_id="player:gm", healing_amount=3,
    ), SequenceRng([]))
    assert resolved["ok"] is True, resolved


def test_a_zero_hp_ally_is_offered_and_accepted(sheets) -> None:
    """§4.4.3：服务端接受的目标，界面必须也提供。

    Divine Spark 的契约写的是"你能看见的另一生物"，倒地队友正是最需要这一发的
    时候。校验侧早就允了 0 HP，但 ``target_filter`` 漏了 ``allow_zero_hp``，
    候选集把队友判成 ``zero_hp`` 非法 —— 于是服务端能结算、界面永远不给选。
    """

    engine, instance = _setup(sheets["cleric5"])
    _start(engine, instance, enemies=[_enemy()])
    _add_ally(instance, sheets["paladin9"])
    _set_hp(instance, "player:ally", 0)
    _to_turn(engine, instance, "player:gm")

    entry = _capability_entry(engine, instance, "divine_spark")
    legal = {row["actor_id"] for row in entry["candidates"] if row["legal"]}
    assert "player:ally" in legal, entry["candidates"]

    resolved = _capability(
        engine, instance, "divine_spark", dice=[6],
        target_ids=["player:ally"], spark_mode="heal",
    )
    assert resolved["ok"] is True, resolved


def test_lay_on_hands_offers_a_zero_hp_ally(sheets) -> None:
    """圣疗是"把队友从死亡豁免里拉起来"的那只手，0 HP 必须在候选集里。

    与 Divine Spark 同因：校验只拦 ``dead``，候选集却按 ``allow_zero_hp`` 默认假
    把 0 HP 判非法。区别是圣疗没有法术可见性路径，界面连"为什么不能选"都看不到。
    """

    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=[_enemy()])
    _add_ally(instance, sheets["paladin9"])
    _set_hp(instance, "player:ally", 0)

    entry = _capability_entry(engine, instance, "lay_on_hands")
    legal = {row["actor_id"] for row in entry["candidates"] if row["legal"]}
    assert "player:ally" in legal, entry["candidates"]

    resolved = _capability(
        engine, instance, "lay_on_hands", [], target_ids=["player:ally"],
        healing_amount=3,
    )
    assert resolved["ok"] is True, resolved


def test_a_dead_creature_is_refused_by_the_validator_too(sheets) -> None:
    """``allow_dead`` 没声明：候选集排除尸体，校验也必须排除。

    只改一侧会留下"服务端接受、界面不提供"的分叉，正是本切片要消灭的形态。
    """

    engine, instance = _setup(sheets["cleric5"])
    _start(engine, instance, enemies=[_enemy()])
    _add_ally(instance, sheets["paladin9"])
    sheet = instance.players["ally"]["character_sheet"]
    sheet["ruleset_character"].setdefault("conditions", {})["dead"] = {"source": "test"}
    _to_turn(engine, instance, "player:gm")

    entry = _capability_entry(engine, instance, "divine_spark")
    legal = {row["actor_id"] for row in entry["candidates"] if row["legal"]}
    assert "player:ally" not in legal

    resolved = _capability(
        engine, instance, "divine_spark", dice=[6],
        target_ids=["player:ally"], spark_mode="heal",
    )
    assert resolved["ok"] is False
    assert "dead" in resolved["error"]


def test_turn_undead_ignores_a_dead_undead_in_range(sheets) -> None:
    """``all_in_range`` 的"候选集即提交集"必须用同一份"谁算合法"。

    候选集按 ``allow_dead=False`` 排除带 ``dead`` 条件的行；校验侧的
    ``_is_living_undead`` 若只看 HP，这只 hp>0 的尸体会进 ``in_reach`` 而不进
    候选集，集合恒不相等 —— 能力不是拒绝这只，而是整条永远提交不了。
    """

    engine, instance = _setup(sheets["cleric5"])
    _start(engine, instance, enemies=[
        _enemy(creature_type="undead", hp=80, position=5),
        _enemy(creature_type="undead", hp=80, position=10, enemy_id="goblin-2"),
    ])
    _combat(instance)["enemies"]["goblin-2"]["conditions"] = {"dead": {"source": "test"}}
    _to_turn(engine, instance, "player:gm")

    entry = _capability_entry(engine, instance, "turn_undead")
    legal = {row["actor_id"] for row in entry["candidates"] if row["legal"]}
    assert legal == {"enemy:goblin-1"}

    resolved = _capability(
        engine, instance, "turn_undead", [3, 7], target_ids=["enemy:goblin-1"],
    )
    assert resolved["ok"] is True, resolved


def test_a_legacy_scalar_target_reaches_the_resolution(sheets) -> None:
    """旧意图只带标量时，校验与结算必须读到同一批目标。

    ``_declared_target_ids`` 两种形状都读，所以校验会放行一个只带 ``target_id``
    的 Abjure Foes（旧客户端就是这么发的）；结算侧的 Turn Undead / Abjure 分支
    过去只认 ``target_ids``，同一份意图于是"校验通过、结算 0 个目标"—— 一次
    Channel 花掉，一张豁免都不掷。
    """

    engine, instance = _setup(sheets["paladin9"])
    _start(engine, instance, enemies=_two_enemies())
    _to_turn(engine, instance, "player:gm")
    resolved = engine.resolve_intent(instance, _intent(
        instance, type="class_capability", capability_id="abjure_foes",
        target_id="enemy:goblin-1",
    ), SequenceRng([3, 3]))
    assert resolved["ok"] is True, resolved
    events = resolved["event_batch"]["events"]
    assert len(_of_type(events, "check.resolved")) == 1
    assert [row["amount"] for row in _of_type(
        events, "dnd2024.class_resource.spent",
    )] == [1]


def test_a_budget_split_capability_without_candidates_is_unavailable(sheets) -> None:
    """§4.5.3 不为预算型开口子：池子还在，但没人可治时同样标不可用。

    Preserve Life 的候选人必须 Bloodied。全员满血的遭遇里候选集为空，而它的
    ``budget_split`` 曾让投影跳过"候选为空即不可用"这条 —— 界面于是给出一个
    点了必然被拒的能力：上界 0、提交必失败。
    """

    engine, instance = _setup(sheets["cleric9"])
    _start(engine, instance, enemies=[_enemy()])
    _to_turn(engine, instance, "player:gm")

    entry = _capability_entry(engine, instance, "preserve_life")
    assert entry["candidates"], "全员满血也应有行，只是每条都非法"
    assert all(row["legal"] is False for row in entry["candidates"])
    assert entry["available"] is False
    assert entry["blocked_reason"]


def test_a_shape_key_without_a_mode_fails_closed() -> None:
    """§4.5.1：只写 ``target_cap`` 却不写 ``target_mode``，不能当 self 静默放行。

    射程参数走的是 ``parameters``，但 ``target_cap`` / ``target_filter`` 是能力
    自身的键；只看前者，一份"写了上界没写形状"的声明会被当成 self，上界被丢掉。
    """

    from src.rulesets.dnd2024.features.models import _parse_target_shape

    with pytest.raises(ClassFeatureError):
        _parse_target_shape(
            "demo", {"target_cap": 2}, {}, target_kind="none",
            requires_hostile_target=False, actions=(), budget_split=False,
        )


def test_side_self_admits_only_the_actor() -> None:
    """§4.1.3 的 ``side: "self"`` 是"只有本人"，不是一次阵营比较。

    actor 行自己的 ``side`` 是 ``party``；若把它交给 ``_side_code`` 去比，本人
    也会被判成非法，能力永远没有候选（"能表达、界面不可达"的另一种写法）。
    """

    from src.rulesets.dnd2024.features.combat import target_candidates
    from src.rulesets.dnd2024.features.models import TargetFilter

    rows = [
        {"actor_id": "player:gm", "name": "Bo", "side": "party", "hp": 10},
        {"actor_id": "player:ally", "name": "Al", "side": "party", "hp": 10},
        {"actor_id": "enemy:goblin-1", "name": "Brute", "side": "enemy", "hp": 10},
    ]
    candidates = target_candidates(
        TargetFilter(side="self"), actor_id="player:gm", rows=rows, range_ft=None,
    )
    legal = [row["actor_id"] for row in candidates if row["legal"]]
    assert legal == ["player:gm"]
    reasons = {row["actor_id"]: row["reason"] for row in candidates}
    assert reasons["player:ally"] == "wrong_side"
    assert reasons["enemy:goblin-1"] == "wrong_side"


def test_known_gaps(sheets) -> None:
    """Preserve Life 的前端预算分配仍未实现 —— 本切片只保证服务端可表达。

    记录在此是为了让下一切片有据可查，而不是让这个缺口沉在 issue 里。
    """

    engine, instance = _setup(sheets["cleric9"])
    _start(engine, instance, enemies=[_enemy()])
    _to_turn(engine, instance, "player:gm")
    entry = _capability_entry(engine, instance, "preserve_life")
    assert entry["budget_split"] is True
    assert entry["budget"]["total"] == 45
