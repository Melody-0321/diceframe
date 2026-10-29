"""Validated compact combat mechanics from the SRD bundle."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from src.rulesets.bundle import LoadedRulesetBundle


DICE_RE = re.compile(r"^[1-9]\d*d(?:4|6|8|10|12|20)(?:\+[1-9]\d*)?$")
# 固定伤害（例如徒手打击的 1 点基础伤害）：没有骰子，因此重击不翻倍。
FLAT_DAMAGE_RE = re.compile(r"^[1-9]\d{0,3}$")
SPELL_MODES = frozenset({
    "spell_attack", "saving_throw", "healing", "automatic_damage", "buff", "debuff", "triggered_damage",
    "stabilize", "reaction_defense",
})


class CombatCatalogError(ValueError):
    """Raised when compact combat data cannot be used authoritatively."""


@dataclass(frozen=True, slots=True)
class Dnd2024CombatCatalog:
    source_ref: str
    weapons: dict[str, dict[str, Any]]
    spell_effects: dict[str, dict[str, Any]]
    # 徒手打击是每个 player-like actor 的天然攻击能力，不是捆绑物品；
    # 因此它有自己的 compact 档案，而不是混进 weapons（weapons 全部必须是 item）。
    unarmed_strike: dict[str, Any] | None = None
    # condition -> 攻击掷骰模式注册表：condition 自己声明它挂在攻击者还是
    # 受击者身上、贡献优势还是劣势、被哪些感官 condition 抵消、何时消耗。
    conditions: dict[str, dict[str, Any]] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_bundle(cls, bundle: LoadedRulesetBundle) -> Dnd2024CombatCatalog:
        raw = bundle.get("combat_catalog", "srd_combat_core")
        if raw is None:
            raise CombatCatalogError("D&D 2024 combat catalog is missing")
        weapons = raw.get("weapons")
        effects = raw.get("spell_effects")
        if not isinstance(weapons, dict) or not isinstance(effects, dict):
            raise CombatCatalogError("combat weapons and spell effects must be objects")
        item_ids = {str(item["id"]) for item in bundle.list("item")}
        for weapon_id, weapon in weapons.items():
            if weapon_id not in item_ids or not isinstance(weapon, dict):
                raise CombatCatalogError(f"combat weapon is not a bundled item: {weapon_id}")
            if not DICE_RE.fullmatch(str(weapon.get("damage") or "")):
                raise CombatCatalogError(f"combat weapon damage is invalid: {weapon_id}")
            if not 5 <= int(weapon.get("range", 0) or 0) <= 600:
                raise CombatCatalogError(f"combat weapon range is invalid: {weapon_id}")
        spell_catalog = bundle.get("spell_catalog", "srd_spells") or {}
        spell_ids = {
            str(item.get("id") or "") for item in spell_catalog.get("spells", [])
            if isinstance(item, dict)
        }
        for spell_id, effect in effects.items():
            if spell_id not in spell_ids or not isinstance(effect, dict):
                raise CombatCatalogError(f"combat spell is not in the spell catalog: {spell_id}")
            if effect.get("mode") not in SPELL_MODES:
                raise CombatCatalogError(f"combat spell mode is invalid: {spell_id}")
            for dice_field in ("damage", "healing", "upcast_damage", "upcast_healing", "extra_damage"):
                dice = effect.get(dice_field)
                if dice is not None and not DICE_RE.fullmatch(str(dice)):
                    raise CombatCatalogError(
                        f"combat spell {dice_field} is invalid: {spell_id}"
                    )
            if effect["mode"] == "triggered_damage" and (effect.get("trigger") != "melee_hit" or not effect.get("damage")):
                raise CombatCatalogError(f"combat spell trigger is invalid: {spell_id}")
            if effect["mode"] == "reaction_defense" and (
                effect.get("trigger") != "hit_by_attack"
                or not 1 <= int(effect.get("armor_class_bonus", 0) or 0) <= 10
                or not effect.get("condition")
            ):
                raise CombatCatalogError(f"combat reaction spell is invalid: {spell_id}")
            if "extra_damage_creature_types" in effect and (
                not isinstance(effect["extra_damage_creature_types"], list)
                or any(not isinstance(kind, str) or kind not in {"fiend", "undead"} for kind in effect["extra_damage_creature_types"])
            ):
                raise CombatCatalogError(f"combat spell creature types are invalid: {spell_id}")
            upcast_targets = effect.get("upcast_target_count")
            if upcast_targets is not None and (
                isinstance(upcast_targets, bool)
                or not isinstance(upcast_targets, int)
                or not 0 < upcast_targets <= 10
            ):
                raise CombatCatalogError(f"combat spell upcast target count is invalid: {spell_id}")
            ends_on = effect.get("ends_on")
            if ends_on is not None and (
                not isinstance(ends_on, list)
                or any(code not in {"attack_roll", "damage_dealt", "spell_cast"} for code in ends_on)
            ):
                raise CombatCatalogError(f"combat spell end triggers are invalid: {spell_id}")
            if not 5 <= int(effect.get("range", 0) or 0) <= 600:
                raise CombatCatalogError(f"combat spell range is invalid: {spell_id}")
        conditions = cls._validated_conditions(raw.get("conditions"))
        labels = raw.get("labels") or {}
        if not isinstance(labels, dict):
            raise CombatCatalogError("combat catalog labels must be an object")
        return cls(
            source_ref=str(raw.get("source_ref") or ""),
            weapons=deepcopy(weapons),
            spell_effects=deepcopy(effects),
            unarmed_strike=deepcopy(cls._validated_unarmed_strike(raw.get("unarmed_strike"))),
            conditions=deepcopy(conditions),
            labels={str(key): str(value) for key, value in labels.items()},
        )

    @staticmethod
    def _validated_conditions(raw: Any) -> dict[str, dict[str, Any]]:
        """Validate the optional condition -> attack-mode registry.

        Missing data means "no condition declares attack modifiers"; the engine
        then simply has no registry sources instead of owning a hard-coded list.
        Every entry is checked here so combat code may trust the shape.
        """

        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise CombatCatalogError("combat conditions must be an object")
        result: dict[str, dict[str, Any]] = {}
        for condition_id, entry in raw.items():
            if not isinstance(entry, dict):
                raise CombatCatalogError(
                    f"combat condition must be an object: {condition_id}"
                )
            if set(entry) - {"attack_modes"}:
                raise CombatCatalogError(
                    f"combat condition has unknown fields: {condition_id}"
                )
            modes = entry.get("attack_modes")
            if not isinstance(modes, list):
                raise CombatCatalogError(
                    f"combat condition attack_modes must be an array: {condition_id}"
                )
            for declaration in modes:
                if not isinstance(declaration, dict):
                    raise CombatCatalogError(
                        f"combat condition attack mode must be an object: {condition_id}"
                    )
                if set(declaration) - {"side", "mode", "negated_by", "consume_on"}:
                    raise CombatCatalogError(
                        f"combat condition attack mode has unknown fields: {condition_id}"
                    )
                if (
                    declaration.get("side") not in {"actor", "target"}
                    or declaration.get("mode") not in {"advantage", "disadvantage"}
                ):
                    raise CombatCatalogError(
                        f"combat condition attack mode is invalid: {condition_id}"
                    )
                negated_by = declaration.get("negated_by")
                if negated_by is not None and (
                    not isinstance(negated_by, list)
                    or any(not isinstance(code, str) or not code for code in negated_by)
                ):
                    raise CombatCatalogError(
                        f"combat condition negated_by is invalid: {condition_id}"
                    )
                if "consume_on" in declaration and declaration["consume_on"] != "attack_resolved":
                    raise CombatCatalogError(
                        f"combat condition consume_on is invalid: {condition_id}"
                    )
            result[str(condition_id)] = deepcopy(entry)
        return result

    @staticmethod
    def _validated_unarmed_strike(raw: Any) -> dict[str, Any] | None:
        """Validate the optional canonical Unarmed Strike profile.

        Missing data means "this content does not declare unarmed strikes": the
        engine then exposes none, instead of inventing mechanics in code.
        """

        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise CombatCatalogError("combat unarmed strike profile must be an object")
        damage = str(raw.get("damage") or "")
        if not (DICE_RE.fullmatch(damage) or FLAT_DAMAGE_RE.fullmatch(damage)):
            raise CombatCatalogError("combat unarmed strike damage is invalid")
        if not str(raw.get("damage_type") or "").strip():
            raise CombatCatalogError("combat unarmed strike damage type is invalid")
        if not 5 <= int(raw.get("range", 0) or 0) <= 600:
            raise CombatCatalogError("combat unarmed strike range is invalid")
        return raw
