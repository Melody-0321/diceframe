"""S0-F14: the eight features that change what a hit or a cantrip actually does.

Every assertion runs through the same authoritative chain the web layer uses
(``resolve_intent`` -> ``apply_batch``), except where a rule is a projection
question rather than a combat question -- the effective spell range is read
from the actor view, because that is what a client has to act on.

The slice is one semantic family with four distinct answers:

* **extra damage** -- Radiant Strikes (always), Divine/Primal Strike (once per
  turn, with a damage-type choice), each settled as its own damage instance so
  resistance applies to the right type.
* **condition after the hit** -- Stunning Strike (a save, and the condition
  lasts until the attacker's next turn) and Open Hand Technique (three
  outcomes, two of which open a save).
* **damage type substitution** -- Empowered Strikes turns Unarmed Strike
  damage into Force.
* **spell-side bonuses** -- Potent Spellcasting (a flat Wisdom bonus on the
  class's own cantrips) and its two upgrades, Improved Blessed Strikes (temp
  HP) and Improved Elemental Fury (range).
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from src.engine.modules import ruleset_runtime
from src.rulesets.dnd2024.features import Dnd2024ClassFeatureResolver
from src.rulesets.dnd2024.features.models import ClassFeatureError
from src.rulesets.dnd2024.combat.check_modes import effective_speed
from src.rulesets.dnd2024.runtime import Dnd2024Runtime
from src.rulesets.dnd2024.spells.selection import Dnd2024SpellSelection

from dnd2024_monk_common import (
    SequenceRng,
    advancement_choices,
    capability_intent,
    goblin,
    monk_draft,
    monk_instance,
    with_equipment,
)


# --------------------------------------------------------------------------
# character construction
# --------------------------------------------------------------------------

_RUNTIME = Dnd2024Runtime()
_SHEETS: dict[tuple, dict] = {}


def _sheet_key(kind: str, level: int, option: str, subclass: str) -> tuple:
    return (kind, level, option, subclass)


def _spell_choices(
    runtime: Dnd2024Runtime, class_ref: str, level: int, *, keep: tuple[str, ...] = (),
) -> dict:
    """A legal full spell selection at ``level``, keeping ``keep`` cantrips."""

    options = Dnd2024SpellSelection(runtime.load_bundle("en")).options(class_ref, level)
    requirements = options["requirements"]
    pool = [str(spell["ref"]) for spell in options["cantrips"]]
    wanted = [ref for ref in keep if ref in pool]
    cantrips = (wanted + [ref for ref in pool if ref not in wanted])[
        : int(requirements["cantrip_count"])
    ]
    leveled = [str(spell["ref"]) for spell in options["leveled_spells"]]
    return {
        "cantrip_refs": cantrips,
        "prepared_spell_refs": leveled[: int(requirements["prepared_spell_count"])],
        "spellbook_refs": [],
    }


def _ability_increase(requirement: dict, sheet: dict) -> dict:
    """Raise the first allowed ability that still has room under 20."""

    total = int(requirement.get("total", 2) or 2)
    allowed = requirement.get("allowed", "any")
    order = ["wis", "str", "dex", "con", "int", "cha"] if allowed == "any" else list(allowed)
    abilities = sheet["ruleset_character"]["abilities"]
    for ability in order:
        if int(abilities.get(ability, 0) or 0) + total <= 20:
            return {ability: total}
    return {order[0]: total}


def _advance(
    runtime: Dnd2024Runtime, sheet: dict, target_level: int, *,
    class_ref: str, option: str = "", subclass: str = "",
    keep_cantrips: tuple[str, ...] = (),
) -> dict:
    """Advance through the real path, answering the F14 option where asked.

    ``option`` names the ``feature_option`` value the character commits to
    (``feature:potent_spellcasting`` or ``feature:divine_strike``).  Every other
    choice keeps the shared helper's first-legal answer.
    """

    while int(sheet["ruleset_character"]["build"]["level"]) < target_level:
        next_level = int(sheet["ruleset_character"]["build"]["level"]) + 1
        preview = runtime.preview_advancement(None, sheet, {})
        requirements = preview.get("requirements") or []
        choices = advancement_choices(preview)
        if subclass and any(
            requirement["id"] == "subclass_ref" for requirement in requirements
        ):
            choices["subclass_ref"] = subclass
        for row in choices.get("feature_choices") or []:
            if option and str(row["feature_id"]) in {"blessed_strikes", "elemental_fury"}:
                row["selected_refs"] = [option]
        for requirement in requirements:
            if requirement["id"] == "ability_score_increases":
                choices["ability_score_increases"] = _ability_increase(requirement, sheet)
            elif requirement["id"] == "class_spell_choices" and requirement.get("required"):
                # 升级只加不减：把当前戏法带过去，否则替换预算会把"重选了
                # 一遍同一个列表"读成"换掉了三个戏法"。
                current_cantrips = (
                    sheet["ruleset_character"]["spellcasting"]["class"]
                    .get("cantrip_refs") or []
                )
                choices["class_spell_choices"] = _spell_choices(
                    runtime, class_ref, next_level,
                    keep=keep_cantrips or tuple(str(ref) for ref in current_cantrips),
                )
        preview = runtime.preview_advancement(None, sheet, choices)
        assert preview["ok"] is True, (preview["errors"], choices)
        sheet = runtime.apply_advancement(None, sheet, choices)
    return sheet


_ABILITIES = {
    "class:cleric": {"str": 10, "dex": 12, "con": 13, "int": 8, "wis": 15, "cha": 14},
    "class:druid": {"str": 10, "dex": 13, "con": 12, "int": 8, "wis": 15, "cha": 14},
    "class:paladin": {"str": 15, "dex": 10, "con": 13, "int": 8, "wis": 12, "cha": 14},
    "class:monk": {"str": 12, "dex": 14, "con": 13, "int": 8, "wis": 15, "cha": 10},
}
_PACKAGES = {
    "class:cleric": "equipment_package:cleric_a",
    "class:druid": "equipment_package:druid_a",
    "class:paladin": "equipment_package:paladin_a",
}
_KEEP_CANTRIPS = {
    "class:cleric": ("spell:sacred_flame", "spell:guidance", "spell:thaumaturgy"),
    "class:druid": ("spell:produce_flame", "spell:poison_spray", "spell:starry_wisp"),
}


def _draft_for(class_ref: str) -> dict:
    """A level 1 draft for any class, built from the Monk one plus overrides.

    The Monk draft already answers the species and background questions the
    builder demands; only the class-owned choices (skills, tools, equipment,
    spells) have to be swapped, and they are read back from the builder so a
    catalog change cannot silently invalidate this fixture.
    """

    runtime = _RUNTIME
    draft = monk_draft(runtime)
    if class_ref == "class:monk":
        return draft
    options = runtime.builder_choices(None, {**draft, "class_ref": class_ref})
    class_skills = [str(item["ref"]) for item in options["class_skills"]][:2]
    species_skills = [
        str(item["ref"]) for item in options["species_skills"]
        if str(item["ref"]) not in class_skills
    ][: int(options["species_skill_count"])]
    draft.update(
        class_ref=class_ref,
        base_abilities=dict(_ABILITIES[class_ref]),
        class_tool_refs=[],
        class_skill_refs=class_skills,
        species_skill_refs=species_skills,
        equipment_package_ref=_PACKAGES[class_ref],
        class_spell_choices=_spell_choices(
            runtime, class_ref, 1, keep=_KEEP_CANTRIPS.get(class_ref, ()),
        ),
    )
    return draft


def character(
    class_ref: str, level: int, *, option: str = "", subclass: str = "",
) -> dict:
    """A cached, fully advanced character sheet for one F14 configuration."""

    key = _sheet_key(class_ref, level, option, subclass)
    if key in _SHEETS:
        return deepcopy(_SHEETS[key])
    draft = _draft_for(class_ref)
    sheet = _RUNTIME.finalize_character(None, draft)
    if level > 1:
        sheet = _advance(
            _RUNTIME, sheet, level, class_ref=class_ref,
            option=option, subclass=subclass,
            keep_cantrips=_KEEP_CANTRIPS.get(class_ref, ()),
        )
    _SHEETS[key] = sheet
    return deepcopy(sheet)


# --------------------------------------------------------------------------
# combat plumbing
# --------------------------------------------------------------------------

def combat(
    sheet: dict, *, allies: dict[str, dict] | None = None,
    enemy_position: int = 5, enemy_hp: int = 200,
) -> tuple[object, object]:
    runtime = _RUNTIME
    engine, instance = monk_instance(runtime, sheet)
    for uid, ally_sheet in (allies or {}).items():
        instance.players[uid] = {
            "character_name": uid.title(), "character_sheet": ally_sheet,
        }
    order = sorted(instance.players)
    rolls = [1 for _ in order]
    rolls[order.index("gm")] = 20
    resolved = engine.resolve_intent(instance, {
        "intent_id": "start-1", "type": "combat.start", "expected_version": 0,
        "submitted_by": "gm",
        "enemies": [goblin(position=enemy_position, hp=enemy_hp)],
    }, SequenceRng([*rolls, 1]))
    assert resolved["ok"] is True, resolved
    assert engine.apply_batch(instance, resolved["event_batch"])["applied"] is True
    assert ruleset_runtime.state(instance)["combat"]["initiative"][0] == "player:gm"
    return engine, instance


def place(instance, **positions: int) -> None:
    ruleset_runtime.state(instance)["combat"]["positions"].update(positions)


def apply(engine, instance, intent: dict, rolls=()) -> list[dict]:
    resolved = engine.resolve_intent(instance, intent, SequenceRng(list(rolls)))
    assert resolved["ok"] is True, resolved
    assert engine.apply_batch(instance, resolved["event_batch"])["applied"] is True
    return resolved["event_batch"]["events"]


def rejected(engine, instance, intent: dict) -> str:
    resolved = engine.resolve_intent(instance, intent, SequenceRng([]))
    assert resolved["ok"] is False, resolved
    return str(resolved.get("error") or "")


def attack_intent(
    engine, instance, *, weapon_ref: str = "", rolls=(), **extra,
) -> list[dict]:
    version = ruleset_runtime.state(instance)["version"]
    intent = {
        "intent_id": f"attack-{version}", "type": "attack",
        "expected_version": version, "submitted_by": "gm",
        "actor_id": "player:gm", "target_id": "enemy:goblin-1",
        **extra,
    }
    if weapon_ref:
        intent["weapon_ref"] = weapon_ref
    return apply(engine, instance, intent, rolls)


def cast_intent(
    engine, instance, spell_ref: str, *, target_id: str = "enemy:goblin-1",
    slot_level: int = 0, rolls=(), **extra,
) -> list[dict]:
    version = ruleset_runtime.state(instance)["version"]
    return apply(engine, instance, {
        "intent_id": f"cast-{version}", "type": "cast_spell",
        "expected_version": version, "submitted_by": "gm",
        "actor_id": "player:gm", "spell_ref": spell_ref,
        "target_id": target_id, "slot_level": slot_level, **extra,
    }, rolls)


def _run(engine, instance, intent: dict, rng) -> list[dict]:
    resolved = engine.resolve_intent(instance, intent, rng)
    assert resolved["ok"] is True, resolved
    assert engine.apply_batch(instance, resolved["event_batch"])["applied"] is True
    return resolved["event_batch"]["events"]


def decline_hit_spell(engine, instance, events: list[dict], rng) -> list[dict]:
    """Resolve a pending melee-hit spell decision as "no smite".

    A caster that has a smite prepared always gets that window, so a test about
    weapon damage has to answer it rather than pretend it is not there.  The
    dice source is shared with the attack on purpose: the riders are rolled when
    the hit commits, i.e. after this window.
    """

    events = list(events)
    pending = [event for event in events if event["type"] == "dnd2024.decision.pending"]
    while pending:
        decision = pending[0]
        resolved = _run(engine, instance, {
            "intent_id": f"decline-{decision['decision_id']}",
            "type": "decision.resolve",
            "expected_version": ruleset_runtime.state(instance)["version"],
            "submitted_by": "gm", "decision_id": decision["decision_id"],
            "option": "decline",
        }, rng)
        events.extend(resolved)
        pending = [
            event for event in resolved if event["type"] == "dnd2024.decision.pending"
        ]
    return events


def swing(engine, instance, *, weapon_ref: str = "", rolls=(), **extra) -> list[dict]:
    """One attack, with any hit-spell window declined, so damage has landed."""

    rng = SequenceRng(list(rolls))
    version = ruleset_runtime.state(instance)["version"]
    intent = {
        "intent_id": f"attack-{version}", "type": "attack",
        "expected_version": version, "submitted_by": "gm",
        "actor_id": "player:gm", "target_id": "enemy:goblin-1", **extra,
    }
    if weapon_ref:
        intent["weapon_ref"] = weapon_ref
    return decline_hit_spell(engine, instance, _run(engine, instance, intent, rng), rng)


def first_weapon(engine, instance) -> str:
    """The first wielded weapon that is a real weapon, not the Unarmed Strike."""

    action = next(
        item for item in engine.available_intents(instance, "gm") if item["type"] == "attack"
    )
    for weapon in action["weapons"]:
        if str(weapon["weapon_ref"]) != "unarmed_strike":
            return str(weapon["weapon_ref"])
    return str(action["weapons"][0]["weapon_ref"])


def damage_to(events: list[dict], target_id: str = "enemy:goblin-1") -> list[dict]:
    return [
        event for event in events
        if event["type"] == "resource.changed" and event.get("resource") == "hp"
        and event.get("target_id") == target_id
    ]


def player(instance, uid: str = "gm") -> dict:
    return instance.get_character_sheet(uid)["ruleset_character"]


def wis_modifier(sheet: dict) -> int:
    return (int(sheet["ruleset_character"]["abilities"]["wis"]) - 10) // 2


def spell_row(engine, instance, spell_ref: str) -> dict:
    """The cast action's row for one spell, exactly as a client receives it."""

    action = next(
        item for item in engine.available_intents(instance, "gm")
        if item["type"] == "cast_spell"
    )
    return next(item for item in action["spells"] if item["spell_ref"] == spell_ref)


# --------------------------------------------------------------------------
# the choice itself: a two-way option is answered, stored and owner-scoped
# --------------------------------------------------------------------------

def test_the_blessed_strikes_option_must_be_answered_at_seventh_level() -> None:
    runtime = _RUNTIME
    sheet = runtime.finalize_character(None, _draft_for("class:cleric"))
    sheet = _advance(runtime, sheet, 6, class_ref="class:cleric")

    preview = runtime.preview_advancement(None, sheet, {
        "class_spell_choices": _spell_choices(
            runtime, "class:cleric", 7, keep=_KEEP_CANTRIPS["class:cleric"],
        ),
    })

    assert preview["ok"] is False
    assert any(
        "blessed_strikes" in error and "requires a selection" in error
        for error in preview["errors"]
    ), preview["errors"]


def test_an_empty_option_selection_is_refused_not_silently_dropped() -> None:
    """Answering the slot with an empty list must fail, not pass un-answered.

    A silent pass would leave the character without a record, so every mechanic
    that hangs off the chosen option would read as "never chose" -- a legal
    character with a feature that does nothing.
    """

    runtime = _RUNTIME
    sheet = runtime.finalize_character(None, _draft_for("class:cleric"))
    sheet = _advance(runtime, sheet, 6, class_ref="class:cleric")

    preview = runtime.preview_advancement(None, sheet, {
        "class_spell_choices": _spell_choices(
            runtime, "class:cleric", 7, keep=_KEEP_CANTRIPS["class:cleric"],
        ),
        "feature_choices": [{
            "owner": "class:cleric", "feature_id": "blessed_strikes",
            "choice_id": "blessed_strikes_option", "selected_refs": [],
        }],
    })

    assert preview["ok"] is False
    assert any("must select exactly 1" in error for error in preview["errors"])


def test_an_option_outside_the_declared_pair_is_refused() -> None:
    runtime = _RUNTIME
    sheet = runtime.finalize_character(None, _draft_for("class:cleric"))
    sheet = _advance(runtime, sheet, 6, class_ref="class:cleric")

    preview = runtime.preview_advancement(None, sheet, {
        "class_spell_choices": _spell_choices(
            runtime, "class:cleric", 7, keep=_KEEP_CANTRIPS["class:cleric"],
        ),
        "feature_choices": [{
            "owner": "class:cleric", "feature_id": "blessed_strikes",
            "choice_id": "blessed_strikes_option",
            "selected_refs": ["feature:primal_strike"],
        }],
    })

    assert preview["ok"] is False
    assert any(
        "is not a declared option" in error for error in preview["errors"]
    )


def test_both_options_are_offered_and_only_one_may_be_taken() -> None:
    runtime = _RUNTIME
    sheet = runtime.finalize_character(None, _draft_for("class:cleric"))
    sheet = _advance(runtime, sheet, 6, class_ref="class:cleric")

    preview = runtime.preview_advancement(None, sheet, {})
    requirement = next(
        row for row in preview["requirements"] if row.get("kind") == "feature_choice"
    )

    assert requirement["feature_id"] == "blessed_strikes"
    assert requirement["count"] == 1
    assert [option["value"] for option in requirement["options"]] == [
        "feature:divine_strike", "feature:potent_spellcasting",
    ]


def test_the_committed_option_is_stored_with_its_owner_and_choice_id() -> None:
    sheet = character("class:cleric", 7, option="feature:potent_spellcasting")

    records = [
        record for record in sheet["ruleset_character"]["features"]["feature_choices"]
        if record["feature_id"] == "blessed_strikes"
    ]

    assert records == [{
        "owner": "class:cleric",
        "feature_id": "blessed_strikes",
        "choice_id": "blessed_strikes_option",
        "selected_refs": ["feature:potent_spellcasting"],
        "granted_level": 7,
    }]


# --------------------------------------------------------------------------
# Potent Spellcasting: a flat Wisdom bonus on the class's own cantrips
# --------------------------------------------------------------------------

def test_potent_spellcasting_adds_the_wisdom_modifier_to_a_cleric_cantrip() -> None:
    sheet = character("class:cleric", 7, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    wisdom = wis_modifier(sheet)  # 17 Wisdom -> +3

    events = cast_intent(engine, instance, "spell:sacred_flame", rolls=[1, 2, 3])

    damage = damage_to(events)[0]
    # Sacred Flame 在 5 级起是 2d8：两颗骰直接相加，再追加 Wisdom 修正。
    assert damage["rolls"] == [2, 3]
    assert damage["amount"] == 2 + 3 + wisdom


def test_the_other_option_of_blessed_strikes_gets_no_cantrip_bonus() -> None:
    sheet = character("class:cleric", 7, option="feature:divine_strike")
    engine, instance = combat(sheet)

    events = cast_intent(engine, instance, "spell:sacred_flame", rolls=[1, 2, 3])

    damage = damage_to(events)[0]
    assert damage["amount"] == sum(damage["rolls"]) == 5


def test_a_sixth_level_cleric_gets_no_cantrip_bonus() -> None:
    sheet = character("class:cleric", 6)
    engine, instance = combat(sheet)

    events = cast_intent(engine, instance, "spell:sacred_flame", rolls=[1, 2, 3])

    damage = damage_to(events)[0]
    assert damage["amount"] == sum(damage["rolls"]) == 5


def test_potent_spellcasting_stays_inside_its_own_class_list() -> None:
    """A Cleric's option must not boost the Druid cantrip Magic Initiate grants.

    Both declarations are called Potent Spellcasting and both use Wisdom, so the
    only thing that keeps them apart is the declaration's
    ``cantrip_source_class``.  A Cleric holding a Druid cantrip is exactly the
    case where a bare id lookup would leak the bonus across lists.
    """

    runtime = _RUNTIME
    draft = _draft_for("class:cleric")
    draft["species_feat_refs"] = ["feat:magic_initiate_druid"]
    draft["feat_choice_answers"]["feat:magic_initiate_druid"] = {
        "spellcasting_ability": ["wis"],
        "cantrips": ["produce_flame", "guidance"],
        "level_1_spell": ["cure_wounds"],
    }
    sheet = runtime.finalize_character(None, draft)
    sheet = _advance(
        runtime, sheet, 7, class_ref="class:cleric",
        option="feature:potent_spellcasting",
        keep_cantrips=_KEEP_CANTRIPS["class:cleric"],
    )
    engine, instance = combat(sheet)

    events = cast_intent(engine, instance, "spell:produce_flame", rolls=[15, 2, 3])

    damage = damage_to(events)[0]
    # 骰面之和就是全部伤害：这条戏法属于德鲁伊目录，牧师那条声明管不到它。
    assert damage["amount"] == sum(damage["rolls"]) == 5
    assert engine._potent_spellcasting_owner(
        engine._actor_view(instance, ruleset_runtime.state(instance)["combat"], "player:gm"),
        engine.spells.get("spell:produce_flame"),
    ) == ""


def test_potent_spellcasting_ignores_a_level_one_spell() -> None:
    sheet = character("class:cleric", 7, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)

    events = cast_intent(
        engine, instance, "spell:guiding_bolt", slot_level=1, rolls=[15, 2, 3, 4, 1],
    )

    damage = damage_to(events)[0]
    # 一级法术不是戏法：无论几颗骰，都不会多出那点 Wisdom。
    assert damage["amount"] == sum(damage["rolls"])

def test_druid_potent_spellcasting_adds_the_wisdom_modifier_to_a_spell_attack() -> None:
    sheet = character("class:druid", 7, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    wisdom = wis_modifier(sheet)

    events = cast_intent(engine, instance, "spell:produce_flame", rolls=[15, 3, 4])

    damage = damage_to(events)[0]
    assert damage["amount"] == 3 + 4 + wisdom


def test_a_druid_that_chose_primal_strike_gets_no_cantrip_bonus() -> None:
    sheet = character("class:druid", 7, option="feature:primal_strike")
    engine, instance = combat(sheet)

    events = cast_intent(engine, instance, "spell:produce_flame", rolls=[15, 3, 4])

    damage = damage_to(events)[0]
    assert damage["amount"] == sum(damage["rolls"]) == 7


# --------------------------------------------------------------------------
# Improved Elemental Fury: Druid cantrip range
# --------------------------------------------------------------------------

def test_improved_elemental_fury_extends_a_druid_cantrip_by_three_hundred_feet() -> None:
    sheet = character("class:druid", 15, option="feature:potent_spellcasting")
    engine, instance = combat(sheet, enemy_position=5)
    place(instance, **{"enemy:goblin-1": 200})

    row = spell_row(engine, instance, "spell:produce_flame")
    events = cast_intent(engine, instance, "spell:produce_flame", rolls=[15, 3, 4])

    assert row["range"] == 60 + 300
    assert row["range_base"] == 60
    assert damage_to(events)[0]["amount"] > 0


def test_a_fourteenth_level_druid_keeps_the_catalogue_range() -> None:
    sheet = character("class:druid", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)

    row = spell_row(engine, instance, "spell:produce_flame")

    assert row["range"] == 60
    assert "range_base" not in row


def test_the_range_extension_skips_a_cantrip_below_ten_feet() -> None:
    sheet = character("class:druid", 15, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    combat_state = ruleset_runtime.state(instance)["combat"]
    actor = engine._actor_view(instance, combat_state, "player:gm")
    spell = engine.spells.get("spell:produce_flame")
    effect = engine.catalog.spell_effects["produce_flame"]

    assert engine._spell_effective_range(actor, spell, {**effect, "range": 5}) == 5
    assert engine._spell_effective_range(actor, spell, {**effect, "range": 10}) == 310


def test_casting_beyond_the_extended_range_still_fails_outside_it() -> None:
    sheet = character("class:druid", 15, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    place(instance, **{"enemy:goblin-1": 400})

    error = rejected(engine, instance, {
        "intent_id": "far-1", "type": "cast_spell",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "spell_ref": "spell:produce_flame", "target_id": "enemy:goblin-1",
        "slot_level": 0,
    })

    assert "out of range" in error


# --------------------------------------------------------------------------
# Improved Blessed Strikes: temp HP after a damaging Cleric cantrip
# --------------------------------------------------------------------------

def test_improved_blessed_strikes_grants_twice_wisdom_as_temp_hp() -> None:
    sheet = character("class:cleric", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    wisdom = wis_modifier(sheet)

    events = cast_intent(
        engine, instance, "spell:sacred_flame", rolls=[1, 2, 3],
        cantrip_temp_hp_target_id="player:gm",
    )

    granted = next(
        event for event in events
        if event["type"] == "resource.changed" and event.get("resource") == "temp_hp"
    )
    assert granted["target_id"] == "player:gm"
    assert granted["amount"] == 2 * wisdom
    assert granted["granted_by_feature"] == "improved_blessed_strikes"
    assert int(player(instance)["resources"]["temp_hp"]) == 2 * wisdom


def test_improved_blessed_strikes_reaches_an_ally_within_sixty_feet() -> None:
    ally_sheet = character("class:paladin", 1)
    sheet = character("class:cleric", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet, allies={"ally": ally_sheet})
    place(instance, **{"player:ally": 40})

    events = cast_intent(
        engine, instance, "spell:sacred_flame", rolls=[1, 2, 3],
        cantrip_temp_hp_target_id="player:ally",
    )

    granted = next(
        event for event in events
        if event["type"] == "resource.changed" and event.get("resource") == "temp_hp"
    )
    assert granted["target_id"] == "player:ally"
    assert int(player(instance, "ally")["resources"]["temp_hp"]) == 2 * wis_modifier(sheet)


def test_an_ally_beyond_sixty_feet_cannot_receive_the_temp_hp() -> None:
    ally_sheet = character("class:paladin", 1)
    sheet = character("class:cleric", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet, allies={"ally": ally_sheet})
    place(instance, **{"player:ally": 80})

    error = rejected(engine, instance, {
        "intent_id": "far-1", "type": "cast_spell",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "spell_ref": "spell:sacred_flame", "target_id": "enemy:goblin-1",
        "slot_level": 0, "cantrip_temp_hp_target_id": "player:ally",
    })

    assert "out of range" in error


def test_improved_blessed_strikes_refuses_a_hostile_recipient() -> None:
    sheet = character("class:cleric", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "foe-1", "type": "cast_spell",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "spell_ref": "spell:sacred_flame", "target_id": "enemy:goblin-1",
        "slot_level": 0, "cantrip_temp_hp_target_id": "enemy:goblin-1",
    })

    assert "caster or an ally" in error


def test_a_thirteenth_level_cleric_cannot_grant_the_temp_hp() -> None:
    sheet = character("class:cleric", 13, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "early-1", "type": "cast_spell",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "spell_ref": "spell:sacred_flame", "target_id": "enemy:goblin-1",
        "slot_level": 0, "cantrip_temp_hp_target_id": "player:gm",
    })

    assert "improved blessed strikes" in error


def test_the_divine_strike_option_cannot_grant_the_temp_hp() -> None:
    sheet = character("class:cleric", 14, option="feature:divine_strike")
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "wrong-1", "type": "cast_spell",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "spell_ref": "spell:sacred_flame", "target_id": "enemy:goblin-1",
        "slot_level": 0, "cantrip_temp_hp_target_id": "player:gm",
    })

    assert "potent spellcasting" in error


def test_the_temp_hp_grant_needs_a_damaging_cantrip() -> None:
    sheet = character("class:cleric", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "heal-1", "type": "cast_spell",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "spell_ref": "spell:cure_wounds", "target_id": "player:gm",
        "slot_level": 1, "cantrip_temp_hp_target_id": "player:gm",
    })

    assert "damaging cantrip" in error


def test_a_grant_never_lowers_existing_temporary_hit_points() -> None:
    sheet = character("class:cleric", 14, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    player(instance)["resources"]["temp_hp"] = 30

    cast_intent(
        engine, instance, "spell:sacred_flame", rolls=[1, 2, 3],
        cantrip_temp_hp_target_id="player:gm",
    )

    assert int(player(instance)["resources"]["temp_hp"]) == 30


# --------------------------------------------------------------------------
# Stunning Strike
# --------------------------------------------------------------------------

def test_a_failed_stunning_strike_save_stuns_and_costs_one_focus() -> None:
    sheet = character("class:monk", 5)
    engine, instance = combat(sheet)

    events = attack_intent(
        engine, instance, weapon_ref="unarmed_strike", rolls=[15, 3, 1],
        stunning_strike=True,
    )

    check = next(
        event for event in events
        if event["type"] == "check.resolved" and event.get("source_feature") == "stunning_strike"
    )
    applied = next(
        event for event in events
        if event["type"] == "condition.applied" and event["condition"] == "stunned"
    )
    assert check["ability"] == "con"
    assert check["success"] is False
    assert check["target"] == 8 + 3 + wis_modifier(sheet)
    assert applied["duration"] == "attacker_next_turn_start"
    assert any(
        event["type"] == "dnd2024.class_resource.spent"
        and event["resource_id"] == "focus_points"
        for event in events
    )


def test_a_successful_stunning_strike_save_staggers_instead() -> None:
    sheet = character("class:monk", 5)
    engine, instance = combat(sheet)

    events = attack_intent(
        engine, instance, weapon_ref="unarmed_strike", rolls=[15, 3, 20],
        stunning_strike=True,
    )

    applied = [
        event for event in events
        if event["type"] == "condition.applied" and event["condition"] == "staggered"
    ]
    assert len(applied) == 1
    assert applied[0]["duration"] == "attacker_next_turn_start"
    assert not any(
        event["type"] == "condition.applied" and event["condition"] == "stunned"
        for event in events
    )
    # 成功豁免不是"没事发生"：Speed 减半、且针对它的下一次攻击有优势。
    combat_state = ruleset_runtime.state(instance)["combat"]
    target = engine._actor_view(instance, combat_state, "enemy:goblin-1")
    assert "staggered" in target["conditions"]
    assert effective_speed(
        engine.catalog.conditions, target["conditions"], target["speed"],
    ) == target["speed"] // 2
    declaration = engine.catalog.conditions["staggered"]
    assert declaration["speed_halved"] is True
    assert declaration["attack_modes"] == [{
        "side": "target", "mode": "advantage", "consume_on": "attack_resolved",
    }]


def test_stunning_strike_is_something_the_client_must_be_able_to_decline() -> None:
    """A plain unarmed strike declares nothing: the rider is opt-in."""

    sheet = character("class:monk", 5)
    engine, instance = combat(sheet)

    events = attack_intent(engine, instance, weapon_ref="unarmed_strike", rolls=[15, 3])

    assert not any(
        event["type"] == "check.resolved"
        and event.get("source_feature") == "stunning_strike"
        for event in events
    )


def test_stunning_strike_is_once_per_turn() -> None:
    sheet = character("class:monk", 5)
    engine, instance = combat(sheet)
    attack_intent(
        engine, instance, weapon_ref="unarmed_strike", rolls=[15, 3, 1],
        stunning_strike=True,
    )

    error = rejected(engine, instance, {
        "intent_id": "second-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": "unarmed_strike",
        "stunning_strike": True,
    })

    assert "already used this turn" in error


def test_stunning_strike_needs_a_focus_point() -> None:
    sheet = character("class:monk", 5)
    engine, instance = combat(sheet)
    player(instance)["resources"]["class"]["focus_points"]["current"] = 0

    error = rejected(engine, instance, {
        "intent_id": "broke-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": "unarmed_strike",
        "stunning_strike": True,
    })

    assert "focus" in error.lower()


def test_a_fourth_level_monk_has_no_stunning_strike() -> None:
    sheet = character("class:monk", 4)
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "early-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": "unarmed_strike",
        "stunning_strike": True,
    })

    assert "not available" in error


# --------------------------------------------------------------------------
# Empowered Strikes
# --------------------------------------------------------------------------

def test_empowered_strikes_turns_unarmed_damage_into_force() -> None:
    sheet = character("class:monk", 6)
    engine, instance = combat(sheet)

    events = attack_intent(
        engine, instance, weapon_ref="unarmed_strike", rolls=[15, 3],
        unarmed_damage_type="force",
    )

    assert damage_to(events)[0]["damage_type"] == "force"


def test_a_fifth_level_monk_cannot_declare_force() -> None:
    sheet = character("class:monk", 5)
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "early-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": "unarmed_strike",
        "unarmed_damage_type": "force",
    })

    assert "not available" in error


def test_empowered_strikes_applies_to_unarmed_strikes_only() -> None:
    sheet = with_equipment(_RUNTIME, character("class:monk", 6), "item:shortsword")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)
    assert weapon != "unarmed_strike"

    error = rejected(engine, instance, {
        "intent_id": "armed-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": weapon,
        "unarmed_damage_type": "force",
    })

    assert "Unarmed Strikes only" in error


# --------------------------------------------------------------------------
# Open Hand Technique (Warrior of the Open Hand 3)
# --------------------------------------------------------------------------

_OPEN_HAND = "subclass:warrior_of_the_open_hand"


def _flurry(engine, instance, *, rolls, **extra) -> list[dict]:
    return apply(engine, instance, capability_intent(
        engine, instance, "flurry_of_blows", intent_id="flurry-1", **extra,
    ), rolls)


def test_addle_blocks_the_targets_reactions_without_a_save() -> None:
    sheet = character("class:monk", 3, subclass=_OPEN_HAND)
    engine, instance = combat(sheet)

    events = _flurry(engine, instance, rolls=[15, 3, 15, 3], open_hand_choice="addle")

    applied = [
        event for event in events
        if event["type"] == "condition.applied"
    ]
    # 连击是两次攻击，两次命中各触发一次选择（RAW：每次命中都能施加一个效果）。
    assert [event["condition"] for event in applied] == [
        "reaction_blocked", "reaction_blocked",
    ]
    assert {event["source_feature"] for event in applied} == {"open_hand_technique"}
    assert not any(
        event["type"] == "check.resolved"
        and event.get("source_feature") == "open_hand_technique"
        for event in events
    )


def test_push_moves_the_target_fifteen_feet_when_the_save_fails() -> None:
    sheet = character("class:monk", 3, subclass=_OPEN_HAND)
    engine, instance = combat(sheet)

    events = _flurry(
        engine, instance, rolls=[15, 3, 1, 15, 3, 1], open_hand_choice="push",
    )

    pushes = [
        event for event in events if event["type"] == "dnd2024.position.changed"
    ]
    assert len(pushes) == 2
    assert {event["distance"] for event in pushes} == {15}
    assert all(event["forced"] is True for event in pushes)


def test_topple_knocks_the_target_prone_when_the_save_fails() -> None:
    sheet = character("class:monk", 3, subclass=_OPEN_HAND)
    engine, instance = combat(sheet)

    events = _flurry(
        engine, instance, rolls=[15, 3, 1, 15, 3, 1], open_hand_choice="topple",
    )

    applied = [
        event for event in events
        if event["type"] == "condition.applied" and event["condition"] == "prone"
    ]
    assert len(applied) == 2


def test_a_successful_save_leaves_the_target_in_place() -> None:
    sheet = character("class:monk", 3, subclass=_OPEN_HAND)
    engine, instance = combat(sheet)

    events = _flurry(
        engine, instance, rolls=[15, 3, 20, 15, 3, 20], open_hand_choice="push",
    )

    assert not any(
        event["type"] == "dnd2024.position.changed" for event in events
    )
    assert not any(event["type"] == "condition.applied" for event in events)


def test_open_hand_technique_needs_the_flurry_grant() -> None:
    sheet = character("class:monk", 3, subclass=_OPEN_HAND)
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "plain-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": "unarmed_strike",
        "open_hand_choice": "addle",
    })

    assert "Flurry of Blows" in error


def test_another_bonus_action_cannot_carry_the_open_hand_choice() -> None:
    sheet = character("class:monk", 3, subclass=_OPEN_HAND)
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "bonus-1", "type": "class_capability",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "capability_id": "bonus_unarmed_strike", "target_id": "enemy:goblin-1",
        "open_hand_choice": "addle",
    })

    assert "Flurry of Blows" in error


# --------------------------------------------------------------------------
# Radiant Strikes (Paladin 11)
# --------------------------------------------------------------------------

def test_radiant_strikes_adds_its_own_d8_of_radiant_damage() -> None:
    sheet = character("class:paladin", 11)
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    events = swing(engine, instance, weapon_ref=weapon, rolls=[15, 3, 5])

    hits = damage_to(events)
    assert len(hits) == 2
    assert hits[0]["damage_type"] != "radiant"
    assert hits[1]["damage_type"] == "radiant"
    assert hits[1]["feature_id"] == "radiant_strikes"
    assert hits[1]["amount"] == 5


def test_a_tenth_level_paladin_has_no_radiant_strikes() -> None:
    sheet = character("class:paladin", 10)
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    events = swing(engine, instance, weapon_ref=weapon, rolls=[15, 3])

    assert len(damage_to(events)) == 1


# --------------------------------------------------------------------------
# Divine Strike / Primal Strike: once per turn, chosen damage type
# --------------------------------------------------------------------------

def test_divine_strike_adds_a_chosen_type_once_per_turn() -> None:
    sheet = character("class:cleric", 7, option="feature:divine_strike")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    events = swing(
        engine, instance, weapon_ref=weapon, rolls=[15, 3, 5],
        rider_damage_type="necrotic",
    )

    riders = [
        event for event in damage_to(events) if event.get("feature_id") == "divine_strike"
    ]
    assert len(riders) == 1
    assert riders[0]["damage_type"] == "necrotic"
    assert riders[0]["amount"] == 5
    assert any(
        event["type"] == "dnd2024.feature.used"
        and event["feature_id"] == "divine_strike"
        for event in events
    )

    # 牧师一个动作只有一次攻击，所以"同一回合的第二次"只能问声明这一步：
    # 走意图会在更外层就以"动作已用完"被拒，测不到这条规则本身。
    combat_state = ruleset_runtime.state(instance)["combat"]
    actor = engine._actor_view(instance, combat_state, "player:gm")
    assert engine._hit_rider_declarations(
        actor,
        engine._declared_attack(actor, {"weapon_ref": weapon}),
        {"rider_damage_type": "necrotic"},
        combat_state,
    ) == []


def test_divine_strike_refuses_a_type_it_does_not_declare() -> None:
    sheet = character("class:cleric", 7, option="feature:divine_strike")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    error = rejected(engine, instance, {
        "intent_id": "bad-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": weapon,
        "rider_damage_type": "fire",
    })

    assert "rider damage type" in error


def test_divine_strike_does_not_ride_an_unarmed_strike() -> None:
    """Divine Strike names "a weapon": an Unarmed Strike is not one."""

    sheet = character("class:cleric", 7, option="feature:divine_strike")
    engine, instance = combat(sheet)

    error = rejected(engine, instance, {
        "intent_id": "fist-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": "unarmed_strike",
        "rider_damage_type": "radiant",
    })

    assert "rider damage type" in error


def test_improved_blessed_strikes_upgrades_divine_strike_to_two_d8() -> None:
    sheet = character("class:cleric", 14, option="feature:divine_strike")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    events = swing(
        engine, instance, weapon_ref=weapon, rolls=[15, 3, 5, 6],
        rider_damage_type="radiant",
    )

    rider = next(
        event for event in damage_to(events) if event.get("feature_id") == "divine_strike"
    )
    assert rider["amount"] == 5 + 6


def test_improved_elemental_fury_upgrades_primal_strike_to_two_d8() -> None:
    sheet = character("class:druid", 15, option="feature:primal_strike")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    events = swing(
        engine, instance, weapon_ref=weapon, rolls=[15, 3, 5, 6],
        rider_damage_type="cold",
    )

    rider = next(
        event for event in damage_to(events) if event.get("feature_id") == "primal_strike"
    )
    assert rider["amount"] == 5 + 6


def test_a_druid_without_primal_strike_declares_no_rider() -> None:
    sheet = character("class:druid", 7, option="feature:potent_spellcasting")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    error = rejected(engine, instance, {
        "intent_id": "none-1", "type": "attack",
        "expected_version": ruleset_runtime.state(instance)["version"],
        "submitted_by": "gm", "actor_id": "player:gm",
        "target_id": "enemy:goblin-1", "weapon_ref": weapon,
        "rider_damage_type": "cold",
    })

    assert "rider damage type" in error


# --------------------------------------------------------------------------
# declaration contract: the parameter closed set fails closed
# --------------------------------------------------------------------------

def _mutated_resolver(mutate) -> object:
    """The real bundle with one class-feature-catalog edit applied."""

    bundle = _RUNTIME.load_bundle("en")
    entities = deepcopy(bundle.entities)
    mutate(entities["class_feature_catalog"]["srd_class_features"])
    return Dnd2024ClassFeatureResolver(replace(bundle, entities=entities))


def _feature_row(catalog: dict, class_id: str, feature_id: str) -> dict:
    return next(
        row for row in catalog["classes"][class_id]["features"]
        if row["id"] == feature_id
    )


def _unknown_rider_parameter(catalog: dict) -> None:
    _feature_row(catalog, "monk", "stunning_strike")["parameters"]["dc_bonus"] = 2


def _missing_rider_parameter(catalog: dict) -> None:
    _feature_row(catalog, "paladin", "radiant_strikes")["parameters"].pop(
        "extra_damage_type"
    )


def _wrong_rider_attack_kind(catalog: dict) -> None:
    _feature_row(catalog, "paladin", "radiant_strikes")["parameters"][
        "attack_kinds"
    ] = ["beam"]


def _wrong_open_hand_choice(catalog: dict) -> None:
    _feature_row(
        catalog, "monk", "open_hand_technique",
    )["parameters"]["flurry_hit_choices"] = ["addle", "shove"]


def _option_outside_the_owner(catalog: dict) -> None:
    _feature_row(catalog, "cleric", "blessed_strikes")["choice"]["enabled_options"] = [
        "feature:not_a_cleric_option",
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        _unknown_rider_parameter,
        _missing_rider_parameter,
        _wrong_rider_attack_kind,
        _wrong_open_hand_choice,
        _option_outside_the_owner,
    ],
)
def test_a_malformed_rider_declaration_fails_closed(mutate) -> None:
    with pytest.raises(ClassFeatureError):
        _mutated_resolver(mutate)


@pytest.mark.parametrize("feature_id", ["divine_strike", "primal_strike"])
def test_the_rider_is_declared_against_its_own_owner(feature_id: str) -> None:
    """The two riders share an envelope but never a declaration."""

    class_ref = {"divine_strike": "class:cleric", "primal_strike": "class:druid"}[feature_id]
    damage_type = "radiant" if feature_id == "divine_strike" else "cold"
    sheet = character(class_ref, 7, option=f"feature:{feature_id}")
    engine, instance = combat(sheet)
    weapon = first_weapon(engine, instance)

    events = swing(
        engine, instance, weapon_ref=weapon, rolls=[15, 3, 5],
        rider_damage_type=damage_type,
    )

    rider = next(
        event for event in damage_to(events) if event.get("feature_id") == feature_id
    )
    assert rider["owner_ref"] == class_ref
