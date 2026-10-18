"""Tests for figma2css.core against API-shaped fixtures."""

import pytest

from figma2css.core import FigmaDataError, extract, extract_tokens


def test_extract_tokens_empty() -> None:
    assert extract_tokens({}) == {}


def test_all_categories_present_for_the_full_fixture(file_response) -> None:
    tokens = extract_tokens(file_response)
    assert list(tokens) == ["colors", "typography", "spacing", "radii", "effects"]


def test_named_fill_styles_become_semantic_colours(file_response) -> None:
    colors = extract_tokens(file_response)["colors"]
    assert colors["--color-brand-primary"] == "#216bed"
    assert colors["--color-brand-surface"] == "#ffffff"
    assert colors["--color-neutral-text"] == "#111724"


def test_paint_opacity_is_kept_on_styled_colours(file_response) -> None:
    assert extract_tokens(file_response)["colors"]["--color-overlay-scrim"] == "rgba(0, 0, 0, 0.5)"


def test_gradient_fill_style_is_named_gradient(file_response) -> None:
    colors = extract_tokens(file_response)["colors"]
    assert colors["--gradient-hero"] == "linear-gradient(90deg, #216bed 0%, #7c3aed 100%)"


def test_unstyled_fills_are_named_by_hex_and_deduped(file_response) -> None:
    colors = extract_tokens(file_response)["colors"]
    assert colors["--color-ff5a1f"] == "#ff5a1f"
    # white and the text colour are already provided by named styles
    assert "--color-ffffff" not in colors
    assert "--color-111724" not in colors


def test_hidden_nodes_are_skipped(file_response) -> None:
    colors = extract_tokens(file_response)["colors"]
    assert "#123456" not in colors.values()


def test_text_styles_expand_into_typography_properties(file_response) -> None:
    typo = extract_tokens(file_response)["typography"]
    assert typo["--font-heading-h1-family"] == '"Inter"'
    assert typo["--font-heading-h1-size"] == "32px"
    assert typo["--font-heading-h1-weight"] == "700"
    assert typo["--font-heading-h1-line-height"] == "1.25"
    assert typo["--font-heading-h1-letter-spacing"] == "-0.64px"
    assert typo["--font-body-regular-line-height"] == "1.5"
    assert typo["--font-label-caps-text-transform"] == "uppercase"
    assert typo["--font-label-caps-line-height"] == "16px"


def test_unstyled_text_contributes_family_and_size_scales(file_response) -> None:
    typo = extract_tokens(file_response)["typography"]
    assert typo["--font-family-roboto-mono"] == '"Roboto Mono"'
    assert typo["--font-size-13"] == "13px"


def test_effect_styles_become_shadow_and_blur_tokens(file_response) -> None:
    effects = extract_tokens(file_response)["effects"]
    assert effects["--shadow-elevation-card"] == (
        "0 1px 2px 0 rgba(0, 0, 0, 0.08), 0 8px 24px -4px rgba(17, 23, 36, 0.16)"
    )
    assert effects["--backdrop-blur-glass-blur"] == "blur(10px)"


def test_grid_style_expands_into_gutter_margin_and_columns(file_response) -> None:
    spacing = extract_tokens(file_response)["spacing"]
    assert spacing["--grid-desktop-12-col-gutter"] == "24px"
    assert spacing["--grid-desktop-12-col-margin"] == "80px"
    assert spacing["--grid-desktop-12-col-columns"] == "12"


def test_auto_layout_spacing_scale_is_sorted_and_deduped(file_response) -> None:
    spacing = extract_tokens(file_response)["spacing"]
    scale = [name for name in spacing if name.startswith("--spacing-")]
    assert scale == ["--spacing-8", "--spacing-12", "--spacing-16", "--spacing-24"]
    assert spacing["--spacing-24"] == "24px"


def test_unstyled_grid_gutter_joins_the_spacing_scale() -> None:
    figma = {"document": {"layoutGrids": [{"gutterSize": 24}, {"gutterSize": 12.5}]}}
    spacing = extract_tokens(figma)["spacing"]
    assert spacing == {"--spacing-12-5": "12.5px", "--spacing-24": "24px"}


def test_corner_radii_include_per_corner_values(file_response) -> None:
    radii = extract_tokens(file_response)["radii"]
    assert radii == {"--radius-4": "4px", "--radius-8": "8px", "--radius-12": "12px"}


def test_styled_only_drops_unstyled_tokens_and_scales(file_response) -> None:
    tokens = extract_tokens(file_response, styled_only=True)
    assert "--color-ff5a1f" not in tokens["colors"]
    assert "radii" not in tokens
    assert not any(n.startswith("--spacing-") for n in tokens["spacing"])
    assert "--font-size-13" not in tokens["typography"]
    assert "--color-brand-primary" in tokens["colors"]


def test_prefix_namespaces_every_property(file_response) -> None:
    tokens = extract_tokens(file_response, prefix="ds")
    names = [n for items in tokens.values() for n in items]
    assert names and all(n.startswith("--ds-") for n in names)


def test_nodes_response_is_supported(nodes_response) -> None:
    result = extract(nodes_response)
    assert result.tokens["colors"]["--color-brand-surface"] == "#ffffff"
    assert result.tokens["typography"]["--font-heading-h1-line-height"] == "40px"
    assert result.tokens["spacing"]["--spacing-16"] == "16px"


def test_missing_node_in_nodes_response_warns() -> None:
    result = extract({"nodes": {"9:9": None}})
    assert result.tokens == {}
    assert result.warnings == ["node '9:9' was not found in the response"]


def test_bare_node_is_accepted() -> None:
    node = {"id": "1:1", "type": "RECTANGLE", "cornerRadius": 6}
    assert extract_tokens(node) == {"radii": {"--radius-6": "6px"}}


def test_figma_error_body_raises_with_the_message() -> None:
    with pytest.raises(FigmaDataError, match="403.*Invalid token"):
        extract({"status": 403, "err": "Invalid token"})


def test_unrecognised_object_raises() -> None:
    with pytest.raises(FigmaDataError, match="not a Figma file response"):
        extract({"hello": "world"})


def test_non_object_raises() -> None:
    with pytest.raises(FigmaDataError):
        extract([1, 2, 3])


def test_style_missing_from_styles_map_falls_back_to_unstyled(file_response) -> None:
    del file_response["styles"]["1:10"]
    colors = extract_tokens(file_response)["colors"]
    assert "--color-brand-primary" not in colors
    assert colors["--color-216bed"] == "#216bed"


def test_layered_fills_in_a_style_warn_and_use_the_top_layer(file_response) -> None:
    card = file_response["document"]["children"][0]["children"][1]
    card["fills"] = [
        {"type": "SOLID", "color": {"r": 1, "g": 0, "b": 0, "a": 1}},
        {"type": "SOLID", "color": {"r": 0, "g": 0, "b": 1, "a": 1}},
    ]
    result = extract(file_response)
    assert result.tokens["colors"]["--color-brand-surface"] == "#0000ff"
    assert any("stacked fills" in w for w in result.warnings)


def test_warnings_are_deduplicated(file_response, clone) -> None:
    card = file_response["document"]["children"][0]["children"][1]
    card["effects"].append({"type": "NOISE", "visible": True})
    other = clone(card)
    other["id"] = "9:9"
    file_response["document"]["children"][0]["children"].append(other)
    result = extract(file_response)
    assert result.warnings.count("effect type 'NOISE' has no CSS equivalent and was skipped") == 1
