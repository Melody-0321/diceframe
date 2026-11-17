"""Combat capability projection for D&D 2024 class features.

The combat engine consumes a *capability id*, its action/resource cost, whether
it needs a hostile target, and the underlying canonical actions it performs.
Which class grants that capability, and from which level, is answered here --
never by the combat engine, and never by the frontend.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import (
    ClassFeatureDefinition,
    CombatCapabilityView,
    Dnd2024ClassFeatureCatalog,
    CapabilityCostView,
    FeatureCapability,
    TargetFilter,
)
from .resources import ResourceDefinition


_DICE_FORMULA_RE = re.compile(r"^(\d+)d(\d+)(?:\+(\d+))?$")
_FLAT_FORMULA_RE = re.compile(r"^(\d+)$")


def damage_mean(formula: str) -> float | None:
    """Expected value of a canonical damage formula, or ``None`` if unparsed."""

    text = str(formula or "").strip()
    match = _DICE_FORMULA_RE.fullmatch(text)
    if match is not None:
        count, sides = int(match.group(1)), int(match.group(2))
        return count * (sides + 1) / 2 + int(match.group(3) or 0)
    match = _FLAT_FORMULA_RE.fullmatch(text)
    if match is not None:
        return float(match.group(1))
    return None


def martial_arts_die_is_better(candidate: str, current: str) -> bool:
    """Whether the feature die improves on the profile's own damage formula.

    V1 deterministic automation must never *downgrade* a weapon: when the
    profile's own dice are at least as good, or cannot be compared at all, the
    weapon keeps its own damage formula and only the ability choice applies.
    """

    candidate_mean = damage_mean(candidate)
    current_mean = damage_mean(current)
    if candidate_mean is None or current_mean is None:
        return False
    return candidate_mean > current_mean


@dataclass(frozen=True, slots=True)
class CombatContext:
    """The action-economy budget a capability is evaluated against."""

    action: int = 0
    bonus_action: int = 0
    reaction: int = 0
    # 当前回合开始时开启的窗口是否属于正在评估的角色。窗口不花经济，所以
    # 它是一个独立布尔而不是第四种"剩余次数"：跳过之后它由 combat 层关闭，
    # 而不是被某种动作消耗。
    turn_start: bool = False

    @classmethod
    def from_economy(
        cls, economy: Mapping[str, Any] | None, actor_id: str = "",
    ) -> CombatContext:
        source: Mapping[str, Any] = economy if isinstance(economy, Mapping) else {}

        def budget(key: str) -> int:
            value = source.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, int):
                return 0
            return max(0, value)

        window = source.get("turn_start_window")
        window = window if isinstance(window, Mapping) else {}
        return cls(
            action=budget("action"),
            bonus_action=budget("bonus_action"),
            reaction=budget("reaction"),
            turn_start=bool(actor_id) and str(window.get("actor_id") or "") == actor_id,
        )

    def remaining(self, action: str) -> int:
        if action == "bonus_action":
            return self.bonus_action
        if action == "action":
            return self.action
        return 0


def _cost_views(
    catalog: Dnd2024ClassFeatureCatalog,
    capability: FeatureCapability,
    context: CombatContext,
    definitions: Mapping[str, ResourceDefinition],
) -> tuple[CapabilityCostView, ...]:
    views: list[CapabilityCostView] = []
    if capability.cost.turn_start:
        # 窗口本身就是这份成本的"剩余":1 表示还没被跳过也没被别的动作关掉。
        views.append(CapabilityCostView(
            kind="turn_start",
            name=catalog.label("turn_start", "turn start"),
            amount=1,
            current=1 if context.turn_start else 0,
            maximum=1,
        ))
    if capability.cost.action:
        views.append(CapabilityCostView(
            kind=capability.cost.action,
            name=catalog.label(capability.cost.action, capability.cost.action),
            amount=1,
            current=context.remaining(capability.cost.action),
            maximum=1,
        ))
    for resource_cost in capability.cost.resources:
        definition = definitions.get(resource_cost.resource_id)
        views.append(CapabilityCostView(
            kind="resource",
            name=catalog.label(resource_cost.resource_id, resource_cost.resource_id),
            amount=resource_cost.amount,
            current=int(definition.current) if definition is not None else 0,
            maximum=int(definition.maximum) if definition is not None else 0,
        ))
    return tuple(views)


def _blocked_reason(
    catalog: Dnd2024ClassFeatureCatalog,
    capability: FeatureCapability,
    context: CombatContext,
    definitions: Mapping[str, ResourceDefinition],
) -> str:
    for resource_cost in capability.cost.resources:
        definition = definitions.get(resource_cost.resource_id)
        name = catalog.label(resource_cost.resource_id, resource_cost.resource_id)
        if definition is None:
            return f"{name} is not available to this character"
        if int(definition.current) < resource_cost.amount:
            return (
                f"not enough {name}: this capability needs {resource_cost.amount}, "
                f"the character has {int(definition.current)}"
            )
    pool_id = capability.pool_resource_id
    if pool_id:
        # 池的支出额由意图决定，所以这里只回答"池里还有没有至少一点"：
        # 空池的能力照样要被列出来带着原因，而不是变成一个可点的按钮。
        pool = definitions.get(pool_id)
        name = catalog.label(pool_id, pool_id)
        if pool is None:
            return f"{name} is not available to this character"
        if int(pool.current) < 1:
            return f"{name} is empty"
    action = capability.cost.action
    if action and context.remaining(action) < 1:
        return f"the {action.replace('_', ' ')} has already been spent"
    if capability.cost.turn_start and not context.turn_start:
        # 窗口一旦被动作或跳过关掉，就不能回头再激活：这就是"at the start of
        # your turn"的可执行含义。
        return "the start of your turn has already passed"
    return ""


def combat_capabilities(
    catalog: Dnd2024ClassFeatureCatalog,
    owned: tuple[ClassFeatureDefinition, ...],
    context: CombatContext,
    definitions: Mapping[str, ResourceDefinition],
    *,
    include_unavailable: bool = False,
    ability_modifiers: Mapping[str, int] | None = None,
) -> tuple[CombatCapabilityView, ...]:
    """Project the capabilities the character may declare right now.

    Only capabilities the character actually owns are considered; a capability
    whose action or resource cost cannot be paid is returned with a reason when
    ``include_unavailable`` is set, and omitted otherwise.  The combat layer
    therefore never has to re-derive class level, feature ownership, or
    resource maxima.

    ``ability_modifiers`` is only used to turn an ability-derived ``target_cap``
    into a number (Abjure Foes: Charisma modifier).  The client never sees the
    ability name, so it can never compute a different ceiling than the server.
    """

    modifiers: Mapping[str, int] = (
        ability_modifiers if isinstance(ability_modifiers, Mapping) else {}
    )
    result: list[CombatCapabilityView] = []
    for definition in owned:
        for capability in definition.capabilities:
            blocked = _blocked_reason(catalog, capability, context, definitions)
            if blocked and not include_unavailable:
                continue
            result.append(CombatCapabilityView(
                id=capability.id,
                feature_id=definition.id,
                name=catalog.label(capability.id, capability.id),
                available=not blocked,
                blocked_reason=blocked,
                requires_hostile_target=capability.requires_hostile_target,
                costs=_cost_views(catalog, capability, context, definitions),
                target_kind=capability.target_kind,
                target_mode=capability.target_mode,
                target_cap=resolve_target_cap(capability, modifiers),
                target_filter=capability.target_filter,
                budget_split=capability.budget_split,
            ))
    return tuple(result)


def target_candidates(
    target_filter: TargetFilter,
    *,
    actor_id: str,
    rows: list[dict[str, Any]],
    range_ft: int | None,
    required_creature_type: str = "",
) -> list[dict[str, Any]]:
    """Which rows this capability admits, and why the others do not.

    This is the single answer to "can I pick this one".  Before S0-F39 the same
    question was answered by each validator inline and *again* by the frontend,
    so a creature could be offered in the list and then rejected on commit.

    ``rows`` are already-annotated actor rows: the combat layer supplies
    ``distance`` (the theater-mode scalar), ``visible``, ``creature_type`` and
    ``already_affected`` because only it can read the instance.  This function
    stays pure, so a projection can call it twice in one request and get
    identical output.
    """

    candidates: list[dict[str, Any]] = []
    for row in rows:
        target_id = str(row.get("actor_id") or "")
        if target_id == actor_id and not target_filter.allow_self:
            # 自己默认不是候选：这条规则以前写在每个校验函数里，前端看不到，
            # 于是"你自己"出现在下拉框里、点了才被拒。
            continue
        reason = _candidate_rejection(
            target_filter, row, range_ft, required_creature_type,
        )
        candidates.append({
            "actor_id": target_id,
            "name": str(row.get("name") or target_id),
            "legal": reason == "",
            "reason": reason,
        })
    return candidates


def _candidate_rejection(
    target_filter: TargetFilter, row: dict[str, Any], range_ft: int | None,
    required_creature_type: str = "",
) -> str:
    """The first reason this row is not selectable, or ``""`` when it is."""

    if bool(row.get("is_dead")) and not target_filter.allow_dead:
        return "dead"
    if required_creature_type:
        # target_kind 是另一层问题（"什么样的生物"），但它同样决定"能不能选"。
        # 不在这里筛，Turn Undead 就会把射程内的队友也列成"全部目标"。
        actual = str(row.get("creature_type") or "").lower()
        if required_creature_type not in actual:
            return "wrong_kind"
    side = target_filter.side
    if side != "any" and str(row.get("side") or "") != _side_code(side):
        return "wrong_side"
    if range_ft is not None:
        distance = row.get("distance")
        if isinstance(distance, int) and distance > range_ft:
            return "out_of_range"
    if target_filter.must_see and not bool(row.get("visible", True)):
        return "cannot_see"
    hp = row.get("hp")
    if isinstance(hp, int) and hp <= 0 and not target_filter.allow_zero_hp:
        return "zero_hp"
    if target_filter.required_condition:
        if not _holds_condition(target_filter.required_condition, row):
            return "not_bloodied"
    if bool(row.get("already_affected")):
        return "already_affected"
    return ""


def _side_code(side: str) -> str:
    """Map a declared side to the actor-row ``side`` value it admits."""

    if side == "ally":
        return "party"
    return "enemy"


def _holds_condition(condition: str, row: dict[str, Any]) -> bool:
    """Whether one row currently satisfies a declared ``required_condition``.

    ``bloodied`` is the only pseudo-condition in the vocabulary so far: it is a
    derived state (HP at or below half), not an entry in the condition map.
    Anything else is read from the row's real condition codes.
    """

    if condition == "bloodied":
        hp = row.get("hp")
        maximum = row.get("max_hp")
        if not isinstance(hp, int) or not isinstance(maximum, int) or maximum <= 0:
            return False
        return hp * 2 <= maximum
    conditions = row.get("conditions")
    return isinstance(conditions, Mapping) and condition in conditions


def resolve_target_cap(
    capability: FeatureCapability, modifiers: Mapping[str, int],
) -> int:
    """The integer ceiling of one capability for one character.

    S0-F39 §4.2 的裁决：**这个数是上界，不是必须选满**。规则原文对 Abjure Foes
    写的是 "a number of creatures equal to your Charisma modifier"，即恰好；
    但自动化战斗里常常凑不齐那么多合法目标，强制选满会让能力在多数场合直接
    不可用，所以产品上收为"最多 N、至少 1"。这是产品裁决，不是对规则的理解
    偏差 —— 不要把 ``len(targets) != cap`` 改回来。

    ``modifiers`` maps an ability id to its already-computed modifier: the
    character's ability scores are the character layer's business, and this
    module must not import it (``character.builder`` imports this package).
    """

    if capability.target_mode in {"self", "single"}:
        return 1
    if capability.target_mode == "all_in_range":
        # 候选集本身就是提交集，上界由投影时的合法候选数决定。
        return 0
    if capability.target_cap is not None:
        return max(1, int(capability.target_cap))
    ability = capability.target_cap_ability
    if ability:
        value = modifiers.get(ability)
        modifier = int(value) if isinstance(value, int) and not isinstance(value, bool) else 0
        return max(int(capability.target_cap_minimum), modifier)
    # 0 = 由服务端在投影时填：all_in_range 取合法候选数，budget_split 取预算余量。
    return 0


def martial_arts_profile(
    base: Mapping[str, Any],
    *,
    damage_die: str,
    ability_choice: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the actor-specific effective profile of a canonical attack.

    Used for the canonical Unarmed Strike and for a wielded Monk Weapon: the
    canonical identity, damage type, properties, range and proficiency still
    come from the combat catalog, and only the *effective* base damage and
    attack-ability choice are feature-derived.  No new attack identity is ever
    created here.

    V1 自动化是确定性的：属性取投影给出的选择中修正值更高者，伤害骰只在
    Martial Arts Die 更优时才替换，绝不把武器自己的伤害骰降级。
    """

    profile = deepcopy(dict(base))
    applied = False
    if damage_die and martial_arts_die_is_better(damage_die, str(base.get("damage") or "")):
        profile["damage"] = damage_die
        applied = True
    choice = [str(item) for item in ability_choice if str(item)]
    if choice:
        profile["ability_choice"] = choice
        applied = True
    if applied:
        profile["martial_arts"] = True
    return profile
