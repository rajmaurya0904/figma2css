"""Edge cases for the node walker, using small hand-built trees."""

from figma2css.core import extract, extract_tokens

RED = {"r": 1, "g": 0, "b": 0, "a": 1}
BLUE = {"r": 0, "g": 0, "b": 1, "a": 1}


def doc(*children, styles=None):
    return {
        "document": {"id": "0:0", "type": "DOCUMENT", "children": list(children)},
        "styles": styles or {},
    }


def rect(node_id, fills=None, **extra):
    node = {"id": node_id, "type": "RECTANGLE", "name": node_id, **extra}
    if fills is not None:
        node["fills"] = fills
    return node


def solid(color):
    return {"type": "SOLID", "color": color}


def test_very_deep_trees_do_not_hit_the_recursion_limit() -> None:
    node = rect("leaf", [solid(RED)])
    for depth in range(5000):
        node = {"id": f"f{depth}", "type": "FRAME", "children": [node]}
    assert extract_tokens(doc(node))["colors"] == {"--color-ff0000": "#ff0000"}


def test_a_style_used_by_many_nodes_is_emitted_once() -> None:
    styles = {"1:1": {"name": "Brand", "styleType": "FILL"}}
    nodes = [rect(f"n{i}", [solid(RED)], styles={"fill": "1:1"}) for i in range(5)]
    assert extract_tokens(doc(*nodes, styles=styles))["colors"] == {"--color-brand": "#ff0000"}


def test_plural_style_keys_are_understood() -> None:
    styles = {"1:1": {"name": "Brand", "styleType": "FILL"}}
    node = rect("n", [solid(RED)], styles={"fills": "1:1"})
    assert extract_tokens(doc(node, styles=styles))["colors"] == {"--color-brand": "#ff0000"}


def test_style_of_the_wrong_type_is_ignored() -> None:
    styles = {"1:1": {"name": "Heading", "styleType": "TEXT"}}
    node = rect("n", [solid(RED)], styles={"fill": "1:1"})
    assert extract_tokens(doc(node, styles=styles))["colors"] == {"--color-ff0000": "#ff0000"}


def test_stroke_styles_become_colours() -> None:
    styles = {"1:1": {"name": "Border/Subtle", "styleType": "FILL"}}
    node = rect("n", strokes=[solid(BLUE)], styles={"stroke": "1:1"})
    assert extract_tokens(doc(node, styles=styles))["colors"] == {
        "--color-border-subtle": "#0000ff"
    }


def test_unstyled_translucent_colours_get_an_alpha_suffix() -> None:
    node = rect("n", [{"type": "SOLID", "color": RED, "opacity": 0.25}])
    assert extract_tokens(doc(node))["colors"] == {"--color-ff0000-a25": "rgba(255, 0, 0, 0.25)"}


def test_hidden_paints_and_subtrees_are_ignored() -> None:
    hidden_fill = rect("a", [{"type": "SOLID", "color": RED, "visible": False}])
    hidden_node = {
        "id": "b",
        "type": "FRAME",
        "visible": False,
        "children": [rect("c", [solid(BLUE)])],
    }
    assert extract_tokens(doc(hidden_fill, hidden_node)) == {}


def test_space_between_layouts_ignore_item_spacing() -> None:
    frame = {
        "id": "f",
        "type": "FRAME",
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "SPACE_BETWEEN",
        "itemSpacing": 10,
        "paddingLeft": 20,
    }
    assert extract_tokens(doc(frame))["spacing"] == {"--spacing-20": "20px"}


def test_non_auto_layout_frames_contribute_no_spacing() -> None:
    frame = {"id": "f", "type": "FRAME", "layoutMode": "NONE", "itemSpacing": 10, "paddingTop": 4}
    assert extract_tokens(doc(frame)) == {}


def test_row_and_square_grid_styles() -> None:
    styles = {
        "1:1": {"name": "Rows", "styleType": "GRID"},
        "1:2": {"name": "Pixel", "styleType": "GRID"},
    }
    rows = {
        "id": "a",
        "type": "FRAME",
        "styles": {"grid": "1:1"},
        "layoutGrids": [{"pattern": "ROWS", "gutterSize": 8, "offset": 16, "count": 6}],
    }
    squares = {
        "id": "b",
        "type": "FRAME",
        "styles": {"grid": "1:2"},
        "layoutGrids": [{"pattern": "GRID", "sectionSize": 8}],
    }
    spacing = extract_tokens(doc(rows, squares, styles=styles))["spacing"]
    assert spacing == {
        "--grid-rows-row-gutter": "8px",
        "--grid-rows-row-margin": "16px",
        "--grid-rows-row-rows": "6",
        "--grid-pixel-size": "8px",
    }


def test_unstyled_effects_get_positional_names_and_dedupe() -> None:
    shadow = {
        "type": "DROP_SHADOW",
        "color": {"r": 0, "g": 0, "b": 0, "a": 0.2},
        "offset": {"x": 0, "y": 2},
        "radius": 4,
    }
    blur = {"type": "LAYER_BLUR", "radius": 6}
    a = rect("a", effects=[shadow])
    b = rect("b", effects=[shadow, blur])
    effects = extract_tokens(doc(a, b))["effects"]
    assert effects == {
        "--shadow-1": "0 2px 4px 0 rgba(0, 0, 0, 0.2)",
        "--blur-1": "blur(3px)",
    }


def test_effect_style_with_shadow_and_layer_blur_emits_both() -> None:
    styles = {"1:1": {"name": "Fancy", "styleType": "EFFECT"}}
    node = rect(
        "n",
        effects=[
            {
                "type": "INNER_SHADOW",
                "color": RED,
                "offset": {"x": 1, "y": 1},
                "radius": 2,
            },
            {"type": "LAYER_BLUR", "radius": 10},
        ],
        styles={"effect": "1:1"},
    )
    assert extract_tokens(doc(node, styles=styles))["effects"] == {
        "--shadow-fancy": "inset 1px 1px 2px 0 #ff0000",
        "--blur-fancy": "blur(5px)",
    }


def test_text_decoration_and_unstyled_weights() -> None:
    text = {
        "id": "t",
        "type": "TEXT",
        "style": {
            "fontFamily": "Georgia",
            "fontSize": 18,
            "fontWeight": 300,
            "textDecoration": "UNDERLINE",
        },
    }
    typo = extract_tokens(doc(text))["typography"]
    assert typo == {
        "--font-family-georgia": '"Georgia"',
        "--font-size-18": "18px",
        "--font-weight-300": "300",
    }


def test_radius_scale_collects_uniform_and_per_corner_values_sorted() -> None:
    frame = {"id": "f", "type": "FRAME", "cornerRadius": 12, "rectangleCornerRadii": [0, 4, 4, 0]}
    assert list(extract_tokens(doc(frame))["radii"]) == ["--radius-4", "--radius-12"]


def test_junk_children_and_styles_do_not_crash() -> None:
    data = doc(
        {"id": "a", "type": "FRAME", "children": [None, 3, "x", {"id": "b", "type": "FRAME"}]},
        "garbage",
    )
    data["styles"] = {"1:1": "not-a-dict"}
    assert extract(data).tokens == {}
