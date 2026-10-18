"""Tests for figma2css.paint."""

import pytest

from figma2css.paint import (
    linear_gradient_css,
    node_size,
    paint_css,
    radial_gradient_css,
    solid_css,
    visible_paints,
)

BLUE = {"r": 0.1294, "g": 0.4196, "b": 0.9294, "a": 1}
PURPLE = {"r": 0.4863, "g": 0.2275, "b": 0.9294, "a": 1}


def _linear(handles, stops=((BLUE, 0), (PURPLE, 1))):
    return {
        "type": "GRADIENT_LINEAR",
        "gradientHandlePositions": [{"x": x, "y": y} for x, y in handles],
        "gradientStops": [{"color": c, "position": p} for c, p in stops],
    }


def test_solid_css() -> None:
    assert solid_css({"type": "SOLID", "color": BLUE}) == "#216bed"


def test_solid_css_applies_paint_opacity() -> None:
    assert solid_css({"type": "SOLID", "color": BLUE, "opacity": 0.5}) == "rgba(33, 107, 237, 0.5)"


def test_solid_css_rejects_other_types_and_bad_colours() -> None:
    assert solid_css({"type": "IMAGE"}) is None
    assert solid_css({"type": "SOLID"}) is None
    assert solid_css({"type": "SOLID", "color": "red"}) is None


def test_visible_paints_filters_hidden_and_junk() -> None:
    paints = [{"type": "SOLID"}, {"type": "SOLID", "visible": False}, "x", None]
    assert visible_paints(paints) == [{"type": "SOLID"}]
    assert visible_paints(None) == []
    assert visible_paints("abc") == []


def test_node_size_prefers_bounding_box() -> None:
    assert node_size({"absoluteBoundingBox": {"width": 10, "height": 20}}) == (10.0, 20.0)
    assert node_size({"size": {"x": 5, "y": 6}}) == (5.0, 6.0)
    assert node_size({}) is None


def test_linear_gradient_left_to_right_on_wide_box() -> None:
    paint = _linear([(0, 0.5), (1, 0.5), (0, 1)])
    css = linear_gradient_css(paint, (1440, 480))
    assert css == "linear-gradient(90deg, #216bed 0%, #7c3aed 100%)"


def test_linear_gradient_top_to_bottom() -> None:
    paint = _linear([(0.5, 0), (0.5, 1), (1, 0)])
    assert linear_gradient_css(paint, (200, 400)).startswith("linear-gradient(180deg,")


def test_linear_gradient_corner_to_corner_spans_full_line() -> None:
    paint = _linear([(0, 0), (1, 1), (0, 1)])
    css = linear_gradient_css(paint, (200, 100))
    assert css == "linear-gradient(116.57deg, #216bed 0%, #7c3aed 100%)"


def test_linear_gradient_skewed_handles_are_remapped_to_css_line() -> None:
    # Handles end at (1, 0.5) of a 200x100 box: the Figma line is shorter than the CSS
    # gradient line at that angle, so the last stop lands short of 100%
    paint = _linear([(0, 0), (1, 0.5), (0, 1)])
    css = linear_gradient_css(paint, (200, 100))
    assert css is not None and css.startswith("linear-gradient(104.04deg,")
    last = float(css.rsplit(" ", 1)[1].rstrip("%)"))
    assert last == pytest.approx(94.46, abs=0.1)


def test_linear_gradient_shortened_handles_shift_stops() -> None:
    paint = _linear([(0.25, 0.5), (0.75, 0.5), (0.25, 1)])
    css = linear_gradient_css(paint, (100, 100))
    assert css == "linear-gradient(90deg, #216bed 25%, #7c3aed 75%)"


def test_linear_gradient_without_size_assumes_square() -> None:
    paint = _linear([(0, 0.5), (1, 0.5), (0, 1)])
    assert linear_gradient_css(paint).startswith("linear-gradient(90deg,")


def test_linear_gradient_rejects_degenerate_input() -> None:
    assert linear_gradient_css(_linear([(0, 0), (0, 0), (1, 1)])) is None
    assert linear_gradient_css({"type": "GRADIENT_LINEAR"}) is None
    assert linear_gradient_css(_linear([(0, 0), (1, 1)], stops=[(BLUE, 0)])) is None


def test_radial_gradient() -> None:
    paint = {
        "type": "GRADIENT_RADIAL",
        "gradientHandlePositions": [{"x": 0.5, "y": 0.5}, {"x": 1, "y": 0.5}, {"x": 0.5, "y": 1}],
        "gradientStops": [{"color": BLUE, "position": 0}, {"color": PURPLE, "position": 1}],
    }
    assert radial_gradient_css(paint, (200, 100)) == (
        "radial-gradient(ellipse 100px 50px at 50% 50%, #216bed 0%, #7c3aed 100%)"
    )
    assert radial_gradient_css(paint).startswith("radial-gradient(circle at 50% 50%")


def test_paint_css_dispatch() -> None:
    assert paint_css({"type": "SOLID", "color": BLUE}) == "#216bed"
    assert paint_css({"type": "IMAGE"}) is None
    assert paint_css({"type": "GRADIENT_ANGULAR"}) is None


@pytest.mark.parametrize("bad", [None, "x", 3])
def test_solid_css_tolerates_garbage_color(bad) -> None:
    assert solid_css({"type": "SOLID", "color": bad}) is None
