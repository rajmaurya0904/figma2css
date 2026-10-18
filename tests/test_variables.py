"""Tests for figma2css.variables against a variables/local-shaped fixture."""

import pytest

from figma2css.core import extract
from figma2css.tokens import TokenBuilder
from figma2css.variables import VariableError, extract_variables


def _tokens(payload, **kw):
    return extract(None, payload, **kw)


def _make_cycle(payload) -> None:
    values = {
        "VariableID:20:2": "VariableID:20:3",
        "VariableID:20:3": "VariableID:20:2",
    }
    for var_id, target in values.items():
        alias = {"type": "VARIABLE_ALIAS", "id": target}
        payload["meta"]["variables"][var_id]["valuesByMode"]["20:0"] = alias


def test_colors_use_default_mode_and_strip_the_redundant_word(variables_response) -> None:
    colors = _tokens(variables_response).tokens["colors"]
    assert colors["--color-bg-page"] == "#ffffff"
    assert colors["--color-text-default"] == "#111724"
    assert "--color-color-bg-page" not in colors


def test_alias_becomes_var_reference(variables_response) -> None:
    colors = _tokens(variables_response).tokens["colors"]
    assert colors["--color-accent"] == "var(--color-blue-600)"
    assert colors["--color-blue-600"] == "#216bed"


def test_inline_aliases_resolve_to_the_final_value(variables_response) -> None:
    colors = _tokens(variables_response, inline_aliases=True).tokens["colors"]
    assert colors["--color-accent"] == "#216bed"


def test_other_modes_only_list_values_that_differ(variables_response) -> None:
    result = _tokens(variables_response)
    assert list(result.modes) == ["Dark"]
    assert result.modes["Dark"]["colors"] == {
        "--color-bg-page": "#0f131d",
        "--color-text-default": "#f5f6f8",
        "--color-accent": "var(--color-blue-400)",
    }


def test_inline_aliases_apply_in_mode_blocks_too(variables_response) -> None:
    result = _tokens(variables_response, inline_aliases=True)
    assert result.modes["Dark"]["colors"]["--color-accent"] == "#699ef7"


def test_choosing_a_mode_swaps_base_and_override(variables_response) -> None:
    result = _tokens(variables_response, mode="dark")
    assert result.tokens["colors"]["--color-bg-page"] == "#0f131d"
    assert result.modes["Light"]["colors"]["--color-bg-page"] == "#ffffff"
    assert result.tokens["colors"]["--color-accent"] == "var(--color-blue-400)"


def test_unknown_mode_warns_and_uses_defaults(variables_response) -> None:
    result = _tokens(variables_response, mode="sepia")
    assert result.tokens["colors"]["--color-bg-page"] == "#ffffff"
    assert any("sepia" in w for w in result.warnings)


def test_floats_are_classified_by_scope_and_name(variables_response) -> None:
    tokens = _tokens(variables_response).tokens
    assert tokens["spacing"] == {"--spacing-4": "16px"}
    assert tokens["radii"] == {"--radius-md": "8px"}
    assert tokens["typography"]["--font-size-lg"] == "20px"
    assert tokens["other"] == {"--number-z-index-modal": "1000"}


def test_string_font_family_is_quoted(variables_response) -> None:
    assert _tokens(variables_response).tokens["typography"]["--font-family-sans"] == '"Inter"'


def test_boolean_variables_are_skipped_with_a_warning(variables_response) -> None:
    result = _tokens(variables_response)
    assert result.warnings == ["skipped 1 boolean variable(s): they have no CSS value"]
    flat = {n for items in result.tokens.values() for n in items}
    assert not any("dark-surface" in n for n in flat)


def test_alias_to_a_variable_outside_the_response_is_skipped(variables_response) -> None:
    variables_response["meta"]["variables"]["VariableID:10:4"]["valuesByMode"]["10:0"] = {
        "type": "VARIABLE_ALIAS",
        "id": "VariableID:999:1",
    }
    result = _tokens(variables_response)
    assert "--color-accent" not in result.tokens["colors"]
    assert any("not in this response" in w for w in result.warnings)


def test_alias_cycle_is_detected(variables_response) -> None:
    _make_cycle(variables_response)
    result = _tokens(variables_response)
    assert "--color-blue-600" not in result.tokens["colors"]
    assert any("alias cycle" in w for w in result.warnings)
    assert "--color-accent" not in result.tokens["colors"]


def test_inline_alias_cycle_is_detected(variables_response) -> None:
    _make_cycle(variables_response)
    result = _tokens(variables_response, inline_aliases=True)
    assert any("alias cycle" in w for w in result.warnings)


def test_wrong_value_type_is_skipped(variables_response) -> None:
    v = variables_response["meta"]["variables"]
    v["VariableID:20:4"]["valuesByMode"]["20:0"] = "sixteen"
    result = _tokens(variables_response)
    assert "spacing" not in result.tokens
    assert any("not a valid FLOAT" in w for w in result.warnings)


def test_variable_names_are_made_unique_and_prefixed(variables_response) -> None:
    v = variables_response["meta"]["variables"]
    v["VariableID:20:3"]["name"] = "blue/600"
    tokens = _tokens(variables_response, prefix="ds").tokens["colors"]
    assert "--ds-color-blue-600" in tokens and "--ds-color-blue-600-2" in tokens
    assert tokens["--ds-color-accent"] == "var(--ds-color-blue-600)"


def test_payload_without_meta_wrapper_is_accepted(variables_response) -> None:
    tokens = extract(None, variables_response["meta"]).tokens
    assert "--color-bg-page" in tokens["colors"]


def test_error_payload_raises() -> None:
    with pytest.raises(VariableError, match="Forbidden"):
        extract_variables({"error": True, "message": "Forbidden"}, TokenBuilder())


@pytest.mark.parametrize("payload", [[], {"meta": {}}, {"variables": {}}, "x"])
def test_wrong_shape_raises(payload) -> None:
    with pytest.raises(VariableError):
        extract_variables(payload, TokenBuilder())


def test_variables_and_styles_share_one_namespace(file_response, variables_response) -> None:
    variables_response["meta"]["variables"]["VariableID:10:2"]["name"] = "color/brand/primary"
    result = extract(file_response, variables_response)
    colors = result.tokens["colors"]
    assert colors["--color-brand-primary"] == "#ffffff"
    assert colors["--color-brand-primary-2"] == "#216bed"
