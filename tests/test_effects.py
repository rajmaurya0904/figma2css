"""Tests for figma2css.effects."""

from figma2css.effects import blur_css, effect_values, shadow_css

DROP = {
    "type": "DROP_SHADOW",
    "visible": True,
    "color": {"r": 0, "g": 0, "b": 0, "a": 0.25},
    "offset": {"x": 0, "y": 4},
    "radius": 8,
    "spread": 2,
}


def test_drop_shadow() -> None:
    assert shadow_css(DROP) == "0 4px 8px 2px rgba(0, 0, 0, 0.25)"


def test_inner_shadow_is_inset_and_spread_defaults_to_zero() -> None:
    effect = {**DROP, "type": "INNER_SHADOW"}
    del effect["spread"]
    assert shadow_css(effect) == "inset 0 4px 8px 0 rgba(0, 0, 0, 0.25)"


def test_shadow_requires_a_colour_and_a_shadow_type() -> None:
    assert shadow_css({"type": "DROP_SHADOW"}) is None
    assert shadow_css({"type": "LAYER_BLUR", "radius": 4}) is None


def test_negative_radius_is_clamped_and_negative_offsets_kept() -> None:
    effect = {**DROP, "offset": {"x": -2, "y": -3}, "radius": -5}
    assert shadow_css(effect) == "-2px -3px 0 2px rgba(0, 0, 0, 0.25)"


def test_blur_radius_is_halved_for_css() -> None:
    assert blur_css({"type": "LAYER_BLUR", "radius": 20}) == "blur(10px)"
    assert blur_css({"type": "BACKGROUND_BLUR", "radius": 5}) == "blur(2.5px)"
    assert blur_css(DROP) is None


def test_effect_values_groups_by_kind() -> None:
    effects = [
        DROP,
        {**DROP, "offset": {"x": 0, "y": 1}, "radius": 2, "spread": 0},
        {"type": "LAYER_BLUR", "radius": 8},
        {"type": "BACKGROUND_BLUR", "radius": 20},
    ]
    values = effect_values(effects)
    assert values["shadow"] == (
        "0 4px 8px 2px rgba(0, 0, 0, 0.25), 0 1px 2px 0 rgba(0, 0, 0, 0.25)"
    )
    assert values["blur"] == "blur(4px)"
    assert values["backdrop-blur"] == "blur(10px)"


def test_effect_values_skips_hidden_and_reports_unknown() -> None:
    warnings: list[str] = []
    effects = [{**DROP, "visible": False}, {"type": "NOISE"}, "junk"]
    assert effect_values(effects, warnings) == {}
    assert warnings == ["effect type 'NOISE' has no CSS equivalent and was skipped"]


def test_effect_values_tolerates_non_lists() -> None:
    assert effect_values(None) == {}
    assert effect_values("shadow") == {}
